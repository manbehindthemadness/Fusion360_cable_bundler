"""
Keep nested recovery strategies inside the original finite work allocation.
"""

from dataclasses import replace

import pytest

from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work


def test_successive_strategies_share_all_unspent_resources() -> None:
    """
    Charge unsuccessful preparation and corrections before transferring work again.
    """
    original = Work(4, 2048, 0.35, 2.0)
    first = original.remaining(updates=1, pairs=623, cpu_seconds=0.1, wall_seconds=0.4)
    assert first is not None
    second = first.remaining(updates=2, pairs=700, cpu_seconds=0.15, wall_seconds=0.5)
    assert second is not None
    assert (second.updates, second.pairs) == (1, 725)
    assert second.cpu_seconds == pytest.approx(0.1)
    assert second.wall_seconds == pytest.approx(1.1)
    assert second.remaining(updates=1, pairs=0, cpu_seconds=0, wall_seconds=0) is None
    assert original == Work(4, 2048, 0.35, 2.0)


@pytest.mark.parametrize(
    ("updates", "pairs", "cpu_seconds", "wall_seconds"),
    [
        (4, 0, 0.0, 0.0),
        (5, 0, 0.0, 0.0),
        (0, 2048, 0.0, 0.0),
        (0, 2049, 0.0, 0.0),
        (0, 0, 0.35, 0.0),
        (0, 0, 0.4, 0.0),
        (0, 0, 0.0, 2.0),
        (0, 0, 0.0, 2.1),
    ],
)
def test_exhausting_any_resource_prevents_another_strategy(
    updates: int, pairs: int, cpu_seconds: float, wall_seconds: float
) -> None:
    """
    Never compensate for an exhausted resource using unused work in another unit.
    """
    assert (
        Work(4, 2048, 0.35, 2.0).remaining(
            updates=updates, pairs=pairs, cpu_seconds=cpu_seconds, wall_seconds=wall_seconds
        )
        is None
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("updates", True),
        ("updates", 0),
        ("updates", 5),
        ("pairs", 0),
        ("pairs", 2049),
        ("cpu_seconds", float("nan")),
        ("cpu_seconds", 0.350001),
        ("wall_seconds", float("inf")),
        ("wall_seconds", 2.000001),
    ],
)
def test_malformed_or_enlarged_allocations_reject(field: str, value: float) -> None:
    """
    Keep all strategy entry points on the same finite, nonrenewable bounds.
    """
    with pytest.raises(ValueError):
        replace(Work(4, 2048, 0.35, 2.0), **{field: value})


@pytest.mark.parametrize("value", [-0.01, float("nan"), float("inf"), True])
def test_invalid_elapsed_time_cannot_create_child_work(value: float) -> None:
    """
    Reject malformed accounting rather than clamping it into a fresh allowance.
    """
    with pytest.raises(ValueError):
        Work(4, 2048, 0.35, 2.0).remaining(updates=0, pairs=0, cpu_seconds=value, wall_seconds=0)
