import logging
import time
from collections import defaultdict, deque
from itertools import count

logger = logging.getLogger(__name__)


class WorkTracker:
    """Keep track of how much work each runner has assigned to it.

    `_all_work` is a dictionary keyed by runner id.  The values are a
    dictionary of `scenario_id: count` for each runner.

    """

    def __init__(self):
        self._all_work = defaultdict(lambda: defaultdict(int))

    def set_actual(self, runner_id, work):
        """Actual is set upon request from live runner"""
        self._all_work[runner_id] = defaultdict(int, work)

    def add_assumed(self, runner_id, work):
        """Work given out is assumed to be being done"""
        current = self._all_work[runner_id]
        for scenario_id, *_ in work:
            current[scenario_id] += 1

    def get_total_work(self, runner_ids):
        """Adds up the total assigned work for each scenario, across all runners.

        The return value is a dict of `scenario_id: count`.

        """
        for expired_runner_id in set(self._all_work.keys()) - set(runner_ids):
            self.remove_runner(expired_runner_id)
        total_work = defaultdict(int)
        for runner_work in self._all_work.values():
            for scenario_id, jobs in runner_work.items():
                total_work[scenario_id] += jobs
        return total_work

    def get_runner_total(self, runner_id):
        return sum(self._all_work[runner_id].values())

    def remove_runner(self, runner_id):
        del self._all_work[runner_id]


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
        del self._last_seen[runner_id]

    def get_active(self):
        t = time.time()
        return [k for k, v in self._last_seen.items() if v + self._timeout > t]

    def get_active_count(self):
        return len(self.get_active())


class Controller:
    def __init__(self, testname, scenario_manager, config_manager):
        self._testname = testname
        self._scenario_manager = scenario_manager
        self._runner_id_gen = count(1)
        self._work_tracker = WorkTracker()
        self._runner_tracker = RunnerTracker()
        self._config_manager = config_manager

    def hello(self):
        runner_id = next(self._runner_id_gen)
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
        work = await self._scenario_manager.get_work(
            current_work, runner_total, len(active_runner_ids), max_work, hit_rate
        )
        self._add_assumed(runner_id, work)
        return work

    async def request_work(
        self, runner_id, current_work, completed_data_ids, max_work=None
    ):
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
        logger.debug(
            "Scenario manager active: %s" % (self._scenario_manager.is_active(),)
        )
        logger.debug("Active runners: %s" % (self._runner_tracker.get_active_count(),))
        return (
            not self._scenario_manager.is_active()
        ) and self._runner_tracker.get_active_count() == 0

    def bye(self, runner_id):
        self._runner_tracker.remove_runner(runner_id)
        self._work_tracker.remove_runner(runner_id)
