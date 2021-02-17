import logging
import random
import time
from collections import defaultdict, namedtuple
from itertools import count, repeat
from math import ceil, floor

from .datapools import DataPoolExhausted

logger = logging.getLogger(__name__)


Scenario = namedtuple("Scenario", "journey_spec datapool volumemodel".split())


class StopScenario(Exception):
    pass


def _volume_dicts_remove_a_from_b(a, b):
    diff = defaultdict(int, b)
    for scenario_id, current_num in a.items():
        diff[scenario_id] -= current_num
    return {k: v for k, v in diff.items() if v > 0}


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
        self._required.clear()
        for scenario_id, scenario in list(self._scenarios.items()):
            try:
                self._required[scenario_id] = int(
                    scenario.volumemodel(start_of_period, end_of_period)
                )
            except StopScenario:
                logger.info(
                    "Removed scenario %d because volume model raised StopScenario",
                    scenario_id,
                )
                del self._scenarios[scenario_id]
        self._current_period_end = end_of_period

    def get_required_work(self):
        if self._in_start:
            if self._now() > self._start_delay:
                self._in_start = False
                self._start_time = time.time()
            else:
                return self._required
        now = self._now()
        if now >= self._current_period_end:
            self._update_required_and_period(
                self._current_period_end, int(now + self._period)
            )
        return self._required

    async def get_work(
        self,
        all_current_work,
        this_runner_current_work,
        num_runners,
        runner_self_limit,
        hit_rate,
    ):
        required_work = self.get_required_work()
        diff = _volume_dicts_remove_a_from_b(all_current_work, required_work)
        total = sum(required_work.values())
        runners_share_limit = total / num_runners - this_runner_current_work
        limit = max(0, runners_share_limit)
        if runner_self_limit is not None:
            limit = min(limit, runners_share_limit)
        spawn_limit = None
        if self._spawn_rate is not None and hit_rate > 1:
            spawn_limit = self._spawn_rate / hit_rate
            limit = min(limit, spawn_limit)
        if random.random() < 0.5:  # round up or down randomly
            limit = floor(limit)
        else:
            limit = ceil(limit)

        scenario_ids = [x for k, v in diff.items() for x in repeat(k, v)]
        random.shuffle(scenario_ids)
        work = []
        for scenario_id in scenario_ids[:limit]:
            if scenario := self._scenarios.get(scenario_id):
                data_pool_id = None
                data_pool_data = None
                if scenario.datapool is not None:
                    try:
                        dpi = await scenario.datapool.checkout(
                            config=self._config_manager
                        )
                    except DataPoolExhausted:
                        logger.info(
                            f"Removed scenario {scenario_id} because data pool exhausted"
                        )
                        del self._scenarios[scenario_id]
                        continue
                    else:
                        data_pool_id, data_pool_data = dpi.id, dpi.data

                work.append(
                    (scenario_id, data_pool_id, scenario.journey_spec, data_pool_data)
                )
        logger.debug(
            f"current={sum(all_current_work.values())} required={sum(required_work.values())} "
            f"diff={sum(diff.values())} {limit=} {runners_share_limit=} {spawn_limit=} "
            f"{runner_self_limit=} {num_runners=} spawn_rate={self._spawn_rate} {hit_rate=} "
            f"{this_runner_current_work=} len_work={len(work)}",
        )

        return work

    def is_active(self):
        return self._in_start or bool(self._scenarios)

    async def checkin_data(self, ids):
        for scenario_id, scenario_data_id in ids:
            if scenario_id in self._scenarios:
                # FIXME: this leaks datapool items if:
                # - some journey is running (with a datapool)
                # - we call _update_required_and_period and that journey is
                #   removed
                # - we come here to check the data pool items for the
                #   previously-running journeys in
                # - the datapool to check in to is missing
                # This probably isn't a huge deal for us, because all our
                # tests currently are structured to all run for the same time
                # and finish simultaneously.  But eventually we should fix
                # this, probably by storing an immutable mapping of
                # scenario_id:datapool for checkin purposes
                await self._scenarios[scenario_id].datapool.checkin(scenario_data_id)
