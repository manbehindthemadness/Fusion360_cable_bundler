"""
Check native scheduling limits without importing Fusion or launching a kernel.
"""

from __future__ import annotations

import pytest

from experiments.experiment_ribbon_cap_transition.native_budget import NativeBudget


@pytest.mark.parametrize("elapsed,rss", ((120.0, 10), (0.0, 2 * 1024 * 1024)))
def test_budget_latches_stop_before_operation(elapsed: float, rss: int) -> None:
    """
    Prevent both the first over-budget launch and every subsequent launch.
    """
    time = [0.0]
    calls: list[str] = []
    budget = NativeBudget(clock=lambda: time[0], memory=lambda: rss)
    time[0] = elapsed

    def operation() -> None:
        """
        Record whether a fake native operation was launched.
        """
        calls.append("launched")

    measured = budget.measure("native", operation, native=True)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="Scheduling limit"):
            measured()
    assert calls == [] and budget.stopped is not None
    assert len(budget.samples) == 1


def test_inflight_operation_finishes_then_next_launch_stops() -> None:
    """
    Do not mistake a scheduling time limit for cancellation of a running kernel.
    """
    time = [0.0]
    budget = NativeBudget(clock=lambda: time[0], memory=lambda: 100)

    def operation() -> str:
        """
        Finish normally after exceeding the scheduling limit in flight.
        """
        time[0] = 130.0
        return "completed"

    measured = budget.measure("native", operation, native=True)
    assert measured() == "completed"
    assert budget.timings == {"native": 130.0}
    with pytest.raises(RuntimeError, match="Scheduling limit"):
        measured()


def test_failed_operation_is_timed_and_exception_preserved() -> None:
    """
    Keep failure cost without converting an exception into a successful result.
    """
    time = [0.0]
    budget = NativeBudget(clock=lambda: time[0], memory=lambda: 100)

    def operation() -> None:
        """
        Fail after observable work.
        """
        time[0] = 3.0
        raise ValueError("native failure")

    with pytest.raises(ValueError, match="native failure"):
        budget.measure("native", operation, native=True)()
    assert budget.timings == {"native": 3.0}
