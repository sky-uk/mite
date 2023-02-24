from collections import defaultdict

from mite.controller import WorkTracker

work = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}


def test_remove_runner():
    work_tracker = WorkTracker()
    for i in range(1, 6):
        work_tracker._all_work[i] = defaultdict(int, work)
    for i in range(1, 6):
        work_tracker.remove_runner(i)
        assert i not in work_tracker._all_work


def test_set_actual():
    work_tracker = WorkTracker()
    for i in range(5):
        work_tracker.set_actual(i, work)
        assert work_tracker._all_work[i]


def test_add_assume():
    work_tracker = WorkTracker()
    for i in range(5):
        work_tracker.add_assumed(i, work)
    assert work_tracker._total_work == {1: 1 * 5, 2: 2 * 5, 3: 3 * 5, 4: 4 * 5, 5: 5 * 5}
