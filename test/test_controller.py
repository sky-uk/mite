from mite.controller import Controller
from mite.scenario import ScenarioManager
from mite.config import ConfigManager

TESTNAME = "unit_test_name"


def test_controller_hello():
    scenario_manager = ScenarioManager()
    config_manager = ConfigManager()
    controller = Controller(TESTNAME, scenario_manager, config_manager)
    for i in range(5):
        runner_id, test_name, config_list = controller.hello()
        assert test_name == controller._testname
        assert runner_id == i + 1
