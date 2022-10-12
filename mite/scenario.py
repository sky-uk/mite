import logging
import random
import time
from collections import namedtuple
from itertools import count

from .datapools import DataPoolExhausted

logger = logging.getLogger(__name__)


Scenario = namedtuple("Scenario", "journey_spec datapool volumemodel".split())


class StopVolumeModel(Exception):
    pass


def _volume_dicts_remove_a_from_b(a, b):
    diff = dict(b)
    for scenario_id, current_num in a.items():
        if scenario_id in diff:
            diff[scenario_id] -= current_num
            if diff[scenario_id] < 1:
                del diff[scenario_id]
    return diff


class ScenarioManager:
    def __init__(self, start_delay=0, period=1, spawn_rate=None, config_manager=None):
        self._period = period
        self._scenario_id_gen = count(1)
        self._in_start = start_delay > 0
        self._start_delay = start_delay
        self._start_time = time.time()
        self._current_period_end = 0
        self._spawn_rate = spawn_rate
        self._required = {}
        self._scenarios = {}
        self._config_manager = config_manager

    def _now(self):
        return time.time() - self._start_time

    def add_scenario(self, journey_spec, datapool, volumemodel):
        scenario_id = next(self._scenario_id_gen)
        self._scenarios[scenario_id] = Scenario(journey_spec, datapool, volumemodel)
        logger.info(
            "Added scenario id=%d journey_spec=%r datapool=%r volumemodel=%r",
            scenario_id,
            journey_spec,
            datapool,
            volumemodel,
        )

    def _update_required_and_period(self, start_of_period, end_of_period):
        required = {}
        for scenario_id, scenario in list(self._scenarios.items()):
            try:
                number = int(scenario.volumemodel(start_of_period, end_of_period))
            except StopVolumeModel:
                logger.info(
                    "Removed scenario %d because volume model raised StopVolumeModel",
                    scenario_id,
                )
                del self._scenarios[scenario_id]
                if len(self._scenarios) == 0:
                    logger.info("All scenarios have been removed from scenario tracker")
            else:
                required[scenario_id] = number
        self._current_period_end = end_of_period
        self._required = required

    def get_required_work(self):
        if self._in_start:
            if self._now() <= self._start_delay:
                return self._required
            self._in_start = False
            self._start_time = time.time()
        now = self._now()
        if now >= self._current_period_end:
            self._update_required_and_period(
                self._current_period_end, int(now + self._period)
            )
        return self._required

    async def get_work(
        self,
        current_work,
        num_runner_current_work,
        num_runners,
        runner_self_limit,
        hit_rate,
    ):
        required = self.get_required_work()
        diff = _volume_dicts_remove_a_from_b(current_work, required)
        total = sum(required.values())
        runners_share_limit = total / num_runners - num_runner_current_work
        limit = max(0, runners_share_limit)
        if runner_self_limit is not None:
            limit = min(limit, runners_share_limit)
        spawn_limit = None
        if self._spawn_rate is not None and hit_rate > 1:
            spawn_limit = self._spawn_rate / hit_rate
            limit = min(limit, spawn_limit)
        if limit % 1:
            if limit % 1 > random.random():
                limit += 1
        limit = int(limit)

        def _yield(diff):
            for k, v in diff.items():
                for _ in range(v):
                    yield k

        scenario_ids = list(_yield(diff))
        random.shuffle(scenario_ids)
        work = []
        scenario_volume_map = {}
        for scenario_id in scenario_ids:
            if len(work) >= limit:
                break
            if scenario_id in self._scenarios:
                scenario = self._scenarios[scenario_id]
                if scenario.datapool is None:
                    work.append((scenario_id, None, scenario.journey_spec, None))
                else:
                    try:
                        dpi = await scenario.datapool.checkout(
                            config=self._config_manager
                        )
                    except DataPoolExhausted:
                        logger.info(
                            "Removed scenario %d because data pool exhausted", scenario_id
                        )
                        del self._scenarios[scenario_id]
                        if len(self._scenarios) == 0:
                            logger.info("All scenarios removed from scenario tracker")
                        continue
                    else:
                        if dpi is None:
                            continue
                        work.append(
                            (scenario_id, dpi.id, scenario.journey_spec, dpi.data)
                        )
                if scenario_id in scenario_volume_map:
                    scenario_volume_map[scenario_id] += 1
                else:
                    scenario_volume_map[scenario_id] = 1
        logger.debug(
            "current=%r required=%r diff=%r limit=%r runners_share_limit=%r spawn_limit=%r runner_self_limit=%r"
            "num_runners=%r spawn_rate=%r hit_rate=%r num_runner_current_work=%r len_work=%r",
            sum(current_work.values()),
            sum(required.values()),
            sum(diff.values()),
            limit,
            runners_share_limit,
            spawn_limit,
            runner_self_limit,
            num_runners,
            self._spawn_rate,
            hit_rate,
            num_runner_current_work,
            len(work),
        )

        return work, scenario_volume_map

    def is_active(self):
        return self._in_start or bool(self._scenarios)

    async def checkin_data(self, ids):
        for scenario_id, scenario_data_id in ids:
            if scenario_id in self._scenarios:
                await self._scenarios[scenario_id].datapool.checkin(scenario_data_id)
