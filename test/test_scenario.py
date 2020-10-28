from collections import defaultdict, namedtuple

import pytest

from mite.scenario import ScenarioManager


def baseline_rampup_mock(peak, ramp_over=5, sustain=60):
    def volumemodel(start, end):
        return peak

    return volumemodel


Scenario = namedtuple('Scenario', 'journey_spec datapool volumemodel'.split())

test_scenarios = [
    ("test_scenario_01", None, baseline_rampup_mock(1)),
    ("test_scenario_02", None, baseline_rampup_mock(2)),
    ("test_scenario_03", None, baseline_rampup_mock(3)),
    ("test_scenario_04", None, baseline_rampup_mock(4)),
    ("test_scenario_05", None, baseline_rampup_mock(5)),
]

test_scenario_manager_scenarios = {
    1: Scenario(
        journey_spec='test_scenario_01',
        datapool=None,
        volumemodel=baseline_rampup_mock(1),
    ),
    2: Scenario(
        journey_spec='test_scenario_02',
        datapool=None,
        volumemodel=baseline_rampup_mock(2),
    ),
    3: Scenario(
        journey_spec='test_scenario_03',
        datapool=None,
        volumemodel=baseline_rampup_mock(3),
    ),
    4: Scenario(
        journey_spec='test_scenario_04',
        datapool=None,
        volumemodel=baseline_rampup_mock(4),
    ),
    5: Scenario(
        journey_spec='test_scenario_05',
        datapool=None,
        volumemodel=baseline_rampup_mock(5),
    ),
}

test_scenario_manager_required = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}

test_current_work = defaultdict(int, {2: 2, 3: 3, 5: 5})
test_num_runner_current_work = 10
test_num_runners = 1


def test_add_scenario():
    scenario_manager = ScenarioManager()
    for row in test_scenarios:
        scenario_manager.add_scenario(row[0], row[1], row[2])
    for i in scenario_manager._scenarios:
        assert scenario_manager._scenarios[i] == test_scenarios[i - 1]


def test_upadate_required_work():
    scenario_manager = ScenarioManager()
    for row in test_scenarios:
        scenario_manager.add_scenario(row[0], row[1], row[2])
    scenario_manager._update_required_and_period(5, 10)
    for k in scenario_manager._required.keys():
        assert scenario_manager._required[k] == k


@pytest.mark.asyncio
async def test_get_work():
    scenario_manager = ScenarioManager()
    for row in test_scenarios:
        scenario_manager.add_scenario(row[0], row[1], row[2])
    scenario_manager._update_required_and_period(5, 10)
    scenario_manager._required = test_scenario_manager_required
    work, scenario_volume_map = await scenario_manager.get_work(
        test_current_work, test_num_runner_current_work, test_num_runners, None, 0.2
    )

    assert work.count((4, None, 'test_scenario_04', None)) == 4
    assert work.count((1, None, 'test_scenario_01', None)) == 1
