import time

import pytest

from mite.controller import RunnerTracker


def test_remove_runner():
    runner_tracker = RunnerTracker()
    runner_tracker._last_seen = {
        1: 1539012109.6872835,
        2: 1539012109.6883354,
        3: 1539012109.6891248,
        4: 1539012109.6899157,
        5: 1539012109.6907856,
    }
    for i in range(1, 6):
        runner_tracker.remove_runner(i)
        assert i not in runner_tracker._last_seen


def test_update():
    runner_tracker = RunnerTracker()
    for i in range(10, 15):
        runner_tracker.update(i)
        assert i in runner_tracker._last_seen
        assert len(runner_tracker._hits) == i - 9


@pytest.mark.slow
def test_update_popleft():
    runner_tracker = RunnerTracker(2)
    for i in range(3):
        runner_tracker.update(i)
    time.sleep(3)
    for i in range(10, 15):
        runner_tracker.update(i)
    assert len(runner_tracker._hits) == 5


@pytest.mark.slow
def test_get_hit_rate():
    runner_tracker = RunnerTracker(2)
    for i in range(3):
        runner_tracker.update(i)
    time.sleep(3)
    for i in range(3, 5):
        runner_tracker.update(i)
    assert runner_tracker.get_hit_rate() == 1


@pytest.mark.slow
def test_get_active():
    runner_tracker = RunnerTracker(2)
    for i in range(5):
        runner_tracker.update(i)
    time.sleep(3)
    for i in range(5, 7):
        runner_tracker.update(i)
    assert runner_tracker.get_active() == [5, 6]
