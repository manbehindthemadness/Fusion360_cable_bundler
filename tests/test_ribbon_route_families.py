"""
Verify geometric diversity selection,determinism and explicit duplicate exclusion.
"""

from __future__ import annotations

import pytest

from experiments.experiment_ribbon_route_discovery.families import Seed, select, separation


def _seed(index: int, score: float, x: float) -> Seed:
    """
    Author an independent geometric descriptor with one width-normalized sample.
    """
    return Seed(index, (0.0,) * 10, score, (x, 0.0, 0.0))


def test_selection_preserves_best_and_rejects_near_duplicate_routes() -> None:
    """
    Require every retained pair to differ even when duplicate starts score better.
    """
    bank = tuple(_seed(i, float(i), x) for i, x in enumerate((0, 0.1, 0.6, 0.7, -0.6)))
    chosen = select(bank)
    assert tuple(seed.index for seed in chosen) == (0, 2, 4)
    assert select(tuple(reversed(bank))) == chosen
    assert all(separation(a, b) >= 0.5 for i, a in enumerate(chosen) for b in chosen[i + 1 :])


def test_missing_families_are_not_filled_with_duplicate_seeds() -> None:
    """
    Keep a single available family and handle an empty bank explicitly.
    """
    assert select((_seed(2, 1, 0), _seed(1, 1, 0))) == (_seed(1, 1, 0),)
    assert select(()) == ()


def test_explicit_breadth_preserves_order_and_geometric_exclusion() -> None:
    """
    Expand a run's declared breadth without changing ranking or duplicate policy.
    """
    bank = tuple(_seed(i, float(i), i * 0.3) for i in range(20))
    chosen = select(bank, maximum=8)
    assert tuple(seed.index for seed in chosen) == tuple(range(0, 16, 2))
    assert select(bank) == chosen[:3]
    assert select(tuple(reversed(bank)), maximum=8) == chosen


@pytest.mark.parametrize("maximum", [0, -1, True, 1.5])
def test_invalid_family_limits_are_rejected(maximum: object) -> None:
    """
    Reject ambiguous or empty work allocations before selecting a route.
    """
    with pytest.raises(ValueError):
        select((), maximum=maximum)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "bank",
    [
        (_seed(0, 0, 0), _seed(0, 1, 1)),
        (_seed(0, float("nan"), 0),),
        (_seed(0, 0, float("inf")),),
        (Seed(0, (), 0, (1.0,)),),
        (_seed(0, 0, 0), Seed(1, (), 1, (0.0,) * 6)),
    ],
)
def test_invalid_descriptor_banks_are_rejected(bank: tuple[Seed, ...]) -> None:
    """
    Refuse ambiguous identities,nonfinite values and mismatched sample layouts.
    """
    with pytest.raises(ValueError):
        select(bank)
