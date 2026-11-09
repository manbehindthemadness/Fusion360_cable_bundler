"""
Reuse exact immutable material prefixes without changing placement arithmetic or domain validation.
"""

from __future__ import annotations

import math

import pytest

from experiments.experiment_ribbon_fold_relaxation.flexible import FlexibleModel
from experiments.experiment_ribbon_fold_relaxation.prefixes import PrefixModel
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from tests.test_ribbon_aesthetic import _route


@pytest.fixture
def original() -> FoldRoute:
    """
    Retain opposite fold signs, staggered leads and every original runway slot.
    """
    return _route(
        (Straight(2), fold(2, 1.2, 1, 0.2, 0), Straight(3), fold(3, 1.2, -1, -0.3, 0), Straight(4))
    )


@pytest.mark.parametrize("angles", ((1.0, -1.0), (0.0, -1.0), (1.0, 0.0), (0.0, 0.0)))
@pytest.mark.parametrize("tail", (0.0, 4.0))
def test_cached_placement_matches_uncached_merging_and_order_exactly(
    original: FoldRoute, angles: tuple[float, float], tail: float
) -> None:
    """
    Preserve complete poses, labels, zero-fold merges, material lengths and fixed radius anchors.
    """
    plain, cached = FlexibleModel(original), PrefixModel(original)
    values = list(plain.initial)
    values[1], values[5], values[8] = angles[0], angles[1], tail / plain.scale
    coordinates = tuple(values)
    assert cached.pieces(coordinates) == plain.pieces(coordinates)
    assert cached.route(coordinates) == plain.route(coordinates)
    assert all(
        a.end_pose() == b.end_pose()
        for a, b in zip(cached.pieces(coordinates), plain.pieces(coordinates))
    )


def test_late_probes_reuse_prefixes_with_bounded_per_model_ownership(original: FoldRoute) -> None:
    """
    Reuse unchanged leading objects while evicting old keys and keeping different models independent.
    """
    model = PrefixModel(original)
    first = model.pieces(model.initial)
    for index in range(128):
        values = list(model.initial)
        values[5] += (index + 1) * 1e-4
        changed = model.pieces(tuple(values))
        assert changed[0] is first[0] and changed[1] is first[1]
        assert changed[-1] is not first[-1]
    assert model._prefixes.cache_info().currsize == 64
    separate = PrefixModel(original).pieces(model.initial)
    assert separate == first and separate[0] is not first[0]


@pytest.mark.parametrize(
    "index,value", ((None, None), (0, -1.0), (1, math.nan), (1, math.inf), (3, 0.0))
)
def test_invalid_full_coordinates_are_rejected_before_cache_access(
    original: FoldRoute, index: int | None, value: float | None
) -> None:
    """
    Retain shape, finite-coordinate and physical-bound errors without caching an invalid prefix.
    """
    plain, cached = FlexibleModel(original), PrefixModel(original)
    values = list(plain.initial)
    if index is None:
        values.pop()
    else:
        assert value is not None
        values[index] = value
    for model in (plain, cached):
        with pytest.raises(ValueError):
            model.pieces(tuple(values))
    assert cached._prefixes.cache_info().currsize == 0
