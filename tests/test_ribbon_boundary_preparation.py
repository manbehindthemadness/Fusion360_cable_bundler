"""
Share axis-independent geometry without transferring scalar results or cell identities.
"""

from __future__ import annotations

import math
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route import contact_boundary
from experiments.experiment_ribbon_fold_route.contact_boundary import BoundaryCache
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, prepare_projection
from experiments.experiment_ribbon_fold_route.contact_extrema import prepare_extrema
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose


@pytest.mark.parametrize("angle", (-1.2, 1.2))
@pytest.mark.parametrize("along", ((-3.0, -1.0), (-1.0, 3.0), (0.0, 1.2), (2.0, 4.0)))
@pytest.mark.parametrize("coefficients", ((0.7, -0.2, 0.3), (-0.4, 0.5, 1.0), (0.0, 1.0, 0.0)))
def test_shared_boundary_retains_every_scalar_extremum(
    angle: float, along: tuple[float, float], coefficients: tuple[float, float, float]
) -> None:
    """
    Entry, curved, join-crossing and exit cells retain exact extrema under either fold orientation.
    """
    fold = CylindricalFold(1, angle, 0, 4, 5, 5)
    low, high = along
    corners = ((low, -1.0), (high, -1.0), (high, 1.0), (low, 1.0))
    heights = (-0.5, 0.5)
    evaluator = prepare_extrema(fold, *coefficients)
    original = evaluator(corners, heights)
    boundary = contact_boundary.prepare_boundary(fold, corners, heights)
    shared = evaluator(corners, heights, boundary=boundary)
    assert original is not None and shared is not None
    assert tuple(v.hex() for v in shared) == tuple(v.hex() for v in original)


def test_separate_signed_zero_owners_cannot_share_boundary_offsets() -> None:
    """
    Retained object identity distinguishes numerically equal cells carrying opposite zero signs.
    """
    tiny = math.ulp(0.0)
    fold = CylindricalFold(tiny, -1e-3, 0, 4, 1, 1)
    corners = ((tiny, 0.0),) * 4
    evaluate = prepare_extrema(fold, -0.0, -0.0, 1.0)
    cache = BoundaryCache()
    owners = (object(), object())
    results = []
    for owner, height in zip(owners, (0.0, -0.0)):
        heights = (height, height)
        boundary = cache.prepare(owner, fold, corners, heights)
        result = evaluate(corners, heights, boundary=boundary)
        assert result is not None
        results.append(tuple(value.hex() for value in result))
    assert results == [("0x0.0p+0",) * 2, ("-0x0.0p+0",) * 2]


@pytest.mark.parametrize(
    "coefficients", ((math.inf, 1.0, 1.0), (1.0, math.inf, 1.0), (1.0, 1.0, math.inf))
)
def test_shared_geometry_preserves_nonfinite_projection_decline(
    coefficients: tuple[float, float, float],
) -> None:
    """
    Prepared finite coordinates cannot bypass axis-specific finite-arithmetic guards.
    """
    fold = CylindricalFold(1, 1.2, 0, 4, 5, 5)
    corners = ((-1.0, -1.0), (3.0, -1.0), (3.0, 1.0), (-1.0, 1.0))
    heights = (-0.5, 0.5)
    boundary = contact_boundary.prepare_boundary(fold, corners, heights)
    assert prepare_extrema(fold, *coefficients)(corners, heights, boundary=boundary) is None


def test_shared_geometry_keeps_stationary_derivative_underflow_decline() -> None:
    """
    A flat prepared cell still obeys the original stationary derivative failure guard.
    """
    fold = CylindricalFold(1e200, 1.2, 0, 4, 5, 5)
    corners = ((-2e-200, -1.0), (-1e-200, -1.0), (-1e-200, 1.0), (-2e-200, 1.0))
    heights = (-0.5, 0.5)
    boundary = contact_boundary.prepare_boundary(fold, corners, heights)
    assert prepare_extrema(fold, 1.0, 0.0, 0.0)(corners, heights, boundary=boundary) is None


def test_cell_geometry_is_shared_across_axes_but_not_walks_or_fold_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    One retained cell reuses only its exact fold geometry; each axis computes its own bounds.
    """
    fold = CylindricalFold(1, 1.2, 0.2, 4, 5, 5)
    pose = Pose(Vector3(10, -4, 7), Vector3(0, 1, 0), Vector3(0, 0, 1))
    piece = PlacedPiece(pose, fold, "analytical shared boundary")
    cell = Cell(0, Span(0.1, 0.8), Span(-2, 2), Span(-0.5, 0.5))
    axes = tuple(unit(axis) for axis in (Vector3(1, 2, -3), Vector3(3, -1, 2)))
    expected = [prepare_projection(piece, axis)(cell) for axis in axes]
    prepare = Mock(wraps=contact_boundary.prepare_boundary)
    monkeypatch.setattr(contact_boundary, "prepare_boundary", prepare)
    cache = BoundaryCache()
    assert [
        prepare_projection(piece, axis, boundary_cache=cache)(cell) for axis in axes
    ] == expected
    assert prepare.call_count == 1
    prepare_projection(piece, axes[0], boundary_cache=BoundaryCache())(cell)
    assert prepare.call_count == 2
    other = PlacedPiece(pose, CylindricalFold(1, 1.2, 0.2, 4, 5, 5), piece.label)
    prepare_projection(other, axes[0], boundary_cache=cache)(cell)
    assert prepare.call_count == 3


def test_preparation_store_evicts_after_128_owners(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Strong owner retention prevents identity recycling while finite LRU eviction bounds memory.
    """
    fold = CylindricalFold(1, 1.2, 0, 4, 5, 5)
    corners = ((-1.0, -1.0), (3.0, -1.0), (3.0, 1.0), (-1.0, 1.0))
    heights = (-0.5, 0.5)
    prepare = Mock(wraps=contact_boundary.prepare_boundary)
    monkeypatch.setattr(contact_boundary, "prepare_boundary", prepare)
    owners = [object() for _ in range(129)]
    cache = BoundaryCache()
    first = cache.prepare(owners[0], fold, corners, heights)
    assert cache.prepare(owners[0], fold, corners, heights) is first
    for owner in owners[1:]:
        cache.prepare(owner, fold, corners, heights)
    assert prepare.call_count == 129
    assert cache.prepare(owners[0], fold, corners, heights) == first
    assert prepare.call_count == 130
