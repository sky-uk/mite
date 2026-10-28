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
from mite.scenario import ScenarioManager, StopVolumeModel
from mite.utils import pack_msg, unpack_msg

TESTNAME = "unit_test_name"


def test_controller_hello():
    scenario_manager = ScenarioManager()
    config_manager = ConfigManager()
    controller = Controller(TESTNAME, scenario_manager, config_manager)
    ids = []
    for _ in range(5):
        runner_id, test_name, config_list = controller.hello()
        assert test_name == controller._testname
        assert runner_id not in ids
        assert 0 <= runner_id < 2**64
        assert (
            unpack_msg(pack_msg((2, [runner_id, {}, [], 0])))[1][0]
            == runner_id
        )
        ids.append(runner_id)


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


@pytest.mark.asyncio
async def test_controller_ignores_previous_session_runner(caplog):
    scenario = mock.Mock()
    scenario.checkin_data = mock.AsyncMock()
    scenario.get_work = mock.AsyncMock(return_value=([], {}))
    old = Controller(TESTNAME, scenario, ConfigManager())
    old_id, _, _ = old.hello()
    current = Controller(TESTNAME, scenario, ConfigManager())
    current_id, _, _ = current.hello()
    assert current_id != old_id
    assert await current.request_work(old_id, {1: 3}, [(1, 4)], 1) == ([], [], True)
    assert current._runner_tracker.get_active() == []
    assert not current._work_tracker._all_work
    scenario.checkin_data.assert_not_awaited()
    scenario.get_work.assert_not_awaited()
    assert "unknown runner" in caplog.text
    current.bye(old_id)
    current.bye(old_id)
    assert current_id in current._registered_runners
    await current.request_work(current_id, {}, [], 0)
    scenario.get_work.assert_awaited_once()
    current.bye(current_id)
    current.bye(current_id)
    assert not current._registered_runners


@pytest.mark.asyncio
async def test_controller_rejects_runner_after_goodbye():
    scenario = mock.Mock()
    scenario.checkin_data = mock.AsyncMock()
    controller = Controller(TESTNAME, scenario, ConfigManager())
    runner_id, _, _ = controller.hello()
    controller.bye(runner_id)
    assert await controller.request_work(runner_id, {}, [], 0) == ([], [], True)
    scenario.checkin_data.assert_not_awaited()
