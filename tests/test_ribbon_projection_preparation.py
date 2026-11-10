"""
Reuse immutable projection coefficients while retaining full material bounds and failure guards.
"""

from __future__ import annotations

import math
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route import contact_bounds
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, prepare_projection
from experiments.experiment_ribbon_fold_route.contact_extrema import prepare_extrema
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight


def _piece(geometry: Straight | CylindricalFold) -> PlacedPiece:
    """
    Place analytical material away from the world origin without using a saved route.
    """
    pose = Pose(Vector3(10, -4, 7), Vector3(0, 1, 0), Vector3(0, 0, 1))
    return PlacedPiece(pose, geometry, "analytical prepared projection")


def test_straight_cells_reuse_fixed_transforms_with_identical_interval_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Repeated material boxes retain outward-rounded bounds without redoing piece/axis dot products.
    """
    piece, axis = _piece(Straight(10)), unit(Vector3(1, 2, -3))
    cells = [Cell(0, Span(i / 32, (i + 1) / 32), Span(-2, 2), Span(-0.5, 0.5)) for i in range(32)]
    expected = [contact_bounds.interval_projection(piece, cell, axis) for cell in cells]
    dot = Mock(wraps=contact_bounds.dot)
    monkeypatch.setitem(vars(contact_bounds), "dot", dot)
    bound = prepare_projection(piece, axis)
    assert dot.call_count > 0
    dot.reset_mock()
    assert [bound(cell) for cell in cells] == expected
    dot.assert_not_called()


def test_fold_exit_cells_reuse_fixed_trigonometry_without_changing_the_enclosure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Cells wholly in the exit plane need no repeated fixed-angle sine or cosine evaluation.
    """
    piece = _piece(CylindricalFold(1, 1.2, 0, 4, 2, 2))
    cell = Cell(0, Span(0.95, 1), Span(-2, 2), Span(-0.5, 0.5))
    axis = unit(Vector3(1, 2, -3))
    expected = contact_bounds.projection(piece, cell, axis)
    bound = prepare_projection(piece, axis)
    sine, cosine = Mock(wraps=math.sin), Mock(wraps=math.cos)
    monkeypatch.setattr(math, "sin", sine)
    monkeypatch.setattr(math, "cos", cosine)
    assert [bound(cell) for _ in range(8)] == [expected] * 8
    sine.assert_not_called()
    cosine.assert_not_called()


def test_changing_cells_reuses_only_unchanged_height_coefficients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Width and along-cell changes cannot require rebuilding fixed stationary coefficients or reuse old cell bounds.
    """
    evaluate = prepare_extrema(CylindricalFold(1, 1.2, 0, 4, 2, 2), 1.0, 0.2, -0.3)
    amplitude = Mock(wraps=math.hypot)
    monkeypatch.setattr(math, "hypot", amplitude)
    first = evaluate(((-1, -1), (3, -1), (3, 1), (-1, 1)), (-0.5, 0.5))
    assert amplitude.call_count == 2
    amplitude.reset_mock()
    second = evaluate(((0, -2), (2, -2), (2, 2), (0, 2)), (-0.5, 0.5))
    assert first is not None and second is not None and first != second
    amplitude.assert_not_called()
    evaluate(((0, -2), (2, -2), (2, 2), (0, 2)), (-0.25, 0.5))
    assert amplitude.call_count == 1


def test_height_coefficient_cache_is_local_and_bounded_to_sixteen_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Height refinement must not accumulate coefficients or share mutable state across prepared axes.
    """
    fold = CylindricalFold(1, 1.2, 0, 4, 2, 2)
    evaluate = prepare_extrema(fold, 1.0, 0.2, -0.3)
    corners = ((-1.0, -1.0), (3.0, -1.0), (3.0, 1.0), (-1.0, 1.0))
    amplitude = Mock(wraps=math.hypot)
    monkeypatch.setattr(math, "hypot", amplitude)
    for i in range(9):
        evaluate(corners, (i / 32, (i + 16) / 32))
    assert amplitude.call_count == 18
    amplitude.reset_mock()
    evaluate(corners, (0.0, 0.5))
    assert amplitude.call_count == 2
    amplitude.reset_mock()
    other_axis = prepare_extrema(fold, 0.2, 1.0, -0.3)
    other_axis(corners, (0.0, 0.5))
    assert amplitude.call_count == 2


@pytest.mark.parametrize(
    "coefficients", ((math.inf, 1.0, 1.0), (1.0, math.inf, 1.0), (1.0, 1.0, math.inf))
)
def test_prepared_extrema_preserve_nonfinite_decline(
    coefficients: tuple[float, float, float],
) -> None:
    """
    Invalid finite-extrema arithmetic still requests the existing conservative interval fallback.
    """
    fold = CylindricalFold(1, 1.2, 0, 4, 2, 2)
    evaluate = prepare_extrema(fold, *coefficients)
    assert evaluate(((-1, -1), (3, -1), (3, 1), (-1, 1)), (-0.5, 0.5)) is None
