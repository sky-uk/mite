import logging
import random
import time
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class WorkTracker:
    def __init__(self):
        self._all_work = defaultdict(lambda: defaultdict(int))
        self._total_work = defaultdict(int)

    def set_actual(self, runner_id, work):
        """Actual is set upon request from live runner"""
        for k, v in self._all_work[runner_id].items():
            self._total_work[k] -= v
        for k, v in work.items():
            self._total_work[k] += v
        self._all_work[runner_id] = defaultdict(int, work)

    def add_assumed(self, runner_id, work):
        """Work given out is assumed to be being done"""
        current = self._all_work[runner_id]
        for k, v in work.items():
            current[k] += v
            self._total_work[k] += v

    def get_total_work(self, runner_ids):
        for expired_runner_id in set(self._all_work.keys()) - set(runner_ids):
            self.remove_runner(expired_runner_id)
        return self._total_work

    def get_runner_total(self, runner_id):
        return sum(self._all_work[runner_id].values())

    def remove_runner(self, runner_id):
        for k, v in self._all_work.pop(runner_id, {}).items():
            self._total_work[k] -= v


class RunnerTracker:
    def __init__(self, timeout=10):
        self._hits = deque()  # Every time a runner hits a controller is a hit
        self._last_seen = {}
        self._timeout = timeout

    def update(self, runner_id):
        t = time.time()
        self._last_seen[runner_id] = t
        self._hits.append(t)
        if self._hits[0] < t - self._timeout:
            self._hits.popleft()

    def get_hit_rate(self):
        t = time.time()
        while self._hits and self._hits[0] < t - self._timeout:
            self._hits.popleft()
        return len(self._hits) / self._timeout

    def remove_runner(self, runner_id):
        self._last_seen.pop(runner_id, None)

    def get_active(self):
        t = time.time()
        return [k for k, v in self._last_seen.items() if v + self._timeout > t]

    def get_active_count(self):
        return len(self.get_active())


class Controller:
    def __init__(self, testname, scenario_manager, config_manager):
        self._testname = testname
        self._scenario_manager = scenario_manager
        self._registered_runners = set()
        self._issued_data = defaultdict(set)
        self._work_tracker = WorkTracker()
        self._runner_tracker = RunnerTracker()
        self._config_manager = config_manager

    def _new_runner_id(self):
        # Random rather than sequential so IDs aren't reused after a controller restart
        while (runner_id := random.getrandbits(63)) in self._registered_runners:
            pass
        return runner_id

    def hello(self):
        runner_id = self._new_runner_id()
        self._registered_runners.add(runner_id)
        return (
            runner_id,
            self._testname,
            self._config_manager.get_changes_for_runner(runner_id),
        )

    def _set_actual(self, runner_id, current_work):
        self._work_tracker.set_actual(runner_id, current_work)

    def _add_assumed(self, runner_id, work):
        self._work_tracker.add_assumed(runner_id, work)

    async def _required_work_for_runner(self, runner_id, max_work=None):
        runner_total = self._work_tracker.get_runner_total(runner_id)
        active_runner_ids = self._runner_tracker.get_active()
        current_work = self._work_tracker.get_total_work(active_runner_ids)
        hit_rate = self._runner_tracker.get_hit_rate()
        work, scenario_volume_map = await self._scenario_manager.get_work(
            current_work, runner_total, len(active_runner_ids), max_work, hit_rate
        )
        self._add_assumed(runner_id, scenario_volume_map)
        self._issued_data[runner_id].update(
            (scenario_id, data_id)
            for scenario_id, data_id, *_ in work
            if data_id is not None
        )
        return work

    def _filter_issued_data(self, runner_id, completed_data_ids):
        # Only accept data this controller handed out, so stale IDs from a
        # previous controller (or duplicates) can't corrupt recyclable pools
        issued = self._issued_data[runner_id]
        valid = []
        for scenario_id, data_id in completed_data_ids:
            key = (scenario_id, data_id)
            if key in issued:
                issued.remove(key)
                valid.append(key)
        dropped = len(completed_data_ids) - len(valid)
        if dropped:
            logger.debug(
                "Dropping %d stale data ids from runner %s", dropped, runner_id
            )
        return valid

    async def request_work(
        self, runner_id, current_work, completed_data_ids, max_work=None
    ):
        if runner_id not in self._registered_runners:
            logger.info("Adopting runner %s from a previous controller", runner_id)
            self._registered_runners.add(runner_id)
        completed_data_ids = self._filter_issued_data(runner_id, completed_data_ids)
        self._set_actual(runner_id, current_work)
        self._runner_tracker.update(runner_id)
        await self._scenario_manager.checkin_data(completed_data_ids)
        work = await self._required_work_for_runner(runner_id, max_work)
        return (
            work,
            self._config_manager.get_changes_for_runner(runner_id),
            not self._scenario_manager.is_active(),
        )

    def report(self, sender):
        required = self._scenario_manager.get_required_work()
        active_runner_ids = self._runner_tracker.get_active()
        actual = self._work_tracker.get_total_work(active_runner_ids)
        sender(
            {
                "type": "controller_report",
                "time": time.time(),
                "test": self._testname,
                "required": required,
                "actual": dict(actual),
                "num_runners": len(active_runner_ids),
            }
        )

    def should_stop(self):
        logger.debug(f"Scenario manager active: {self._scenario_manager.is_active()}")
        logger.debug(f"Active runners: {self._runner_tracker.get_active_count()}")
        return (
            not self._scenario_manager.is_active()
        ) and self._runner_tracker.get_active_count() == 0

    def bye(self, runner_id):
        self._registered_runners.discard(runner_id)
        self._issued_data.pop(runner_id, None)
        self._runner_tracker.remove_runner(runner_id)
        self._work_tracker.remove_runner(runner_id)
