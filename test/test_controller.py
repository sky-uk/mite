from mite.controller import Controller
from mite.scenario import ScenarioManager
from mite.config import ConfigManager
from werkzeug.wrappers import Response
import ujson
from mite.__main__ import _controller_log_start, _controller_log_end
from pytest_httpserver.httpserver import HandlerType


TESTNAME = "unit_test_name"


def test_controller_hello():
    scenario_manager = ScenarioManager()
    config_manager = ConfigManager()
    controller = Controller(TESTNAME, scenario_manager, config_manager)
    for i in range(5):
        runner_id, test_name, config_list = controller.hello()
        assert test_name == controller._testname
        assert runner_id == i + 1


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
