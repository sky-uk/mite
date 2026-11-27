import json
from multiprocessing import Process
from unittest import mock

import pytest
import ujson
from pytest_httpserver.httpserver import HandlerType
from werkzeug.wrappers import Response

from mite.__main__ import _controller_log_end, _controller_log_start
from mite.__main__ import controller as main_controller
from mite.__main__ import duplicator as main_duplicator
from mite.__main__ import runner as main_runner
from mite.config import ConfigManager
from mite.controller import Controller
from mite.datapools import RecyclableIterableDataPool
from mite.scenario import ScenarioManager, StopVolumeModel

TESTNAME = "unit_test_name"


@pytest.fixture
def scenario():
    s = mock.Mock()
    s.checkin_data = mock.AsyncMock()
    s.get_work = mock.AsyncMock(return_value=([], {}))
    s.is_active.return_value = True
    return s


@pytest.fixture
def controller(scenario):
    return Controller(TESTNAME, scenario, ConfigManager())


def test_controller_hello():
    scenario_manager = ScenarioManager()
    config_manager = ConfigManager()
    controller = Controller(TESTNAME, scenario_manager, config_manager)
    for _ in range(5):
        runner_id, test_name, config_list = controller.hello()
        assert test_name == controller._testname


def test_hello_returns_unique_ids(controller):
    ids = {controller.hello()[0] for _ in range(100)}
    assert len(ids) == 100


def test_hello_ids_differ_across_controllers(scenario):
    first = Controller(TESTNAME, scenario, ConfigManager()).hello()[0]
    second = Controller(TESTNAME, scenario, ConfigManager()).hello()[0]
    assert first != second


def test_hello_retries_on_id_collision(controller):
    with mock.patch("mite.controller.random.getrandbits", side_effect=[7, 7, 8]):
        assert controller.hello()[0] == 7
        assert controller.hello()[0] == 8


def _work_item(scenario_id, data_id):
    return (scenario_id, data_id, "module:journey", ("data",))


@pytest.mark.asyncio
async def test_issued_data_is_checked_in(controller, scenario):
    scenario.get_work.return_value = ([_work_item(1, 4)], {1: 1})
    runner_id, _, _ = controller.hello()
    await controller.request_work(runner_id, {}, [], 1)
    await controller.request_work(runner_id, {1: 1}, [(1, 4)], 0)
    assert scenario.checkin_data.await_args == mock.call([(1, 4)])


@pytest.mark.asyncio
async def test_issued_data_is_only_checked_in_once(controller, scenario):
    scenario.get_work.return_value = ([_work_item(1, 4)], {1: 1})
    runner_id, _, _ = controller.hello()
    await controller.request_work(runner_id, {}, [], 1)
    scenario.get_work.return_value = ([], {})
    await controller.request_work(runner_id, {}, [(1, 4)], 0)
    await controller.request_work(runner_id, {}, [(1, 4)], 0)
    assert scenario.checkin_data.await_args_list[-1] == mock.call([])


@pytest.mark.asyncio
async def test_data_without_id_is_not_tracked(controller, scenario):
    scenario.get_work.return_value = ([_work_item(1, None)], {1: 1})
    runner_id, _, _ = controller.hello()
    await controller.request_work(runner_id, {}, [], 1)
    assert not controller._issued_data[runner_id]


@pytest.mark.asyncio
async def test_data_issued_to_another_runner_is_not_checked_in(controller, scenario):
    scenario.get_work.return_value = ([_work_item(1, 4)], {1: 1})
    owner, _, _ = controller.hello()
    other, _, _ = controller.hello()
    await controller.request_work(owner, {}, [], 1)
    await controller.request_work(other, {}, [(1, 4)], 0)
    assert scenario.checkin_data.await_args == mock.call([])


@pytest.mark.asyncio
async def test_unknown_runner_is_adopted(controller, scenario):
    work, _, stop = await controller.request_work(12345, {1: 3}, [], 1)
    assert stop is False
    scenario.get_work.assert_awaited_once()
    assert controller._runner_tracker.get_active_count() == 1


@pytest.mark.asyncio
async def test_adopted_runner_stale_data_is_dropped(controller, scenario):
    await controller.request_work(12345, {1: 3}, [(1, 4)], 1)
    await controller.request_work(12345, {1: 2}, [(1, 5)], 1)
    await controller.request_work(12345, {1: 1}, [(1, 6)], 1)
    for call in scenario.checkin_data.await_args_list:
        assert call == mock.call([])


@pytest.mark.asyncio
async def test_adopted_runner_new_data_is_checked_in(controller, scenario):
    scenario.get_work.return_value = ([_work_item(1, 9)], {1: 1})
    await controller.request_work(12345, {1: 1}, [(1, 4)], 1)
    await controller.request_work(12345, {1: 1}, [(1, 5), (1, 9)], 0)
    assert scenario.checkin_data.await_args == mock.call([(1, 9)])


@pytest.mark.asyncio
async def test_stale_ids_do_not_duplicate_recyclable_pool_items():
    pool = RecyclableIterableDataPool(["a", "b", "c"])
    scenario_manager = ScenarioManager()
    scenario_manager.add_scenario("module:journey", pool, lambda start, end: 1)
    controller = Controller(TESTNAME, scenario_manager, ConfigManager())

    # Adopted runner reports items 1 and 2, checked out from the old controller
    work, _, _ = await controller.request_work(12345, {}, [(1, 1), (1, 2)], 1)
    assert [data_id for _, data_id, _, _ in work] == [0]
    assert list(pool._available) == [1, 2]

    # Stale IDs arriving later must still be dropped
    await controller.request_work(12345, {1: 1}, [(1, 1), (1, 2)], 0)
    assert list(pool._available) == [1, 2]

    await controller.request_work(12345, {}, [(1, 0)], 0)
    assert 0 in pool._available
    assert len(pool._available) == len(set(pool._available))


@pytest.mark.asyncio
async def test_bye_clears_issued_data(controller, scenario):
    scenario.get_work.return_value = ([_work_item(1, 4)], {1: 1})
    runner_id, _, _ = controller.hello()
    await controller.request_work(runner_id, {}, [], 1)
    controller.bye(runner_id)
    assert runner_id not in controller._issued_data


@pytest.mark.asyncio
async def test_bye_is_idempotent(controller):
    runner_id, _, _ = controller.hello()
    await controller.request_work(runner_id, {1: 2}, [], 0)
    controller.bye(runner_id)
    controller.bye(runner_id)
    assert controller._runner_tracker.get_active_count() == 0


def test_bye_from_unknown_runner(controller):
    controller.bye(12345)


def test_controller_log_start(httpserver):
    def handler(req):
        assert req.data == json.dumps({'id': "testing"}).encode("utf-8")
        return

    httpserver.expect_request(
        "/start",
        "POST",
        data=ujson.dumps({'testname': "testing"}),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json({'newid': "testing-id"})

    with httpserver.wait(raise_assertions=True, stop_on_nohandler=True, timeout=5):
        _controller_log_start("testing", httpserver.url_for("/"))


def test_controller_log_end(httpserver):
    httpserver.expect_request(
        "/end",
        "POST",
        data=ujson.dumps({'id': "testing-id"}),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_response(Response(status=204))

    with httpserver.wait(raise_assertions=True, stop_on_nohandler=True, timeout=5):
        _controller_log_end("testing-id", httpserver.url_for("/"))


# TODO: a proper mini-integration test for the logging webhook (to assure it's
# called at both beginning and end).  I haven't yet figured out how to get the
# controller stuff in __main__.py to work properly without hanging, which is
# a prerequisite of this


class DummySender:
    def __init__(self, *args, **kwargs):
        self._received = []

    def send(self, msg):
        self._received.append(msg)


def dummy_vm(s, e):
    if s > 10:
        raise StopVolumeModel
    return 1


async def dummy_journey(ctx):
    pass


def dummy_scenario():
    return [("test_controller:dummy_journey", None, dummy_vm)]


@pytest.mark.slow
@pytest.mark.skip(reason="it causes the whole process to abort! :(")
def test_controller_report():
    # breakpoint()
    ds = DummySender()
    opts = {
        "SCENARIO_SPEC": "test_controller:dummy_scenario",
        '--delay-start-seconds': 0,
        '--min-loop-delay': 0,
        '--max-loop-delay': 0,
        '--spawn-rate': 2000,
        "--message-backend": "ZMQ",
        "--config": "mite.config:default_config_loader",
        "--add-to-config": (),
        "--controller-socket": "tcp://127.0.0.1:14301",
        "--logging-webhook": None,
        "--message-socket": "tcp://127.0.0.1:14302",
        "--runner-max-journeys": None,
        "--debugging": None,
        "OUT_SOCKET": (),
    }
    runner = Process(target=main_runner, args=(opts,))
    runner.start()
    duplicator = Process(target=main_duplicator, args=(opts,))
    duplicator.start()
    with mock.patch("mite.__main__._create_sender", return_value=ds):
        main_controller(opts)
    runner.terminate()
    duplicator.terminate()
    # Even in a broken condition, we get one controller report.  So we check
    # that we have more than that...
    assert sum(x["type"] == "controller_report" for x in ds._received) > 1
