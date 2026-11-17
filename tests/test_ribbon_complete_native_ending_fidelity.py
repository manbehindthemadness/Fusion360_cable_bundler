"""
Verify native support bounds without treating parameter changes or loose bounds as success.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.native_branch_surface import NativeSurfaceGrid
from experiments.experiment_ribbon_complete.native_ending_fidelity import compare
from experiments.experiment_ribbon_complete.native_material_chart import NativeSurfaceSnapshot


def checkpoint() -> None:
    """
    Supply a deterministic checkpoint for tiny analytical controls.
    """


def surfaces() -> tuple[NativeSurfaceGrid, NativeSurfaceSnapshot]:
    """
    Bind a weighted rectangle to an explicit observation of its encoded support.
    """
    rows = tuple(
        tuple((Fraction(i) * w, Fraction(j) * w, Fraction(0), w) for j in (0, 1))
        for i, w in ((0, Fraction(1)), (1, Fraction(1, 2)))
    )
    grid = NativeSurfaceGrid(rows, checkpoint)
    points = tuple(tuple(Fraction(getattr(p, axis)) * 10 for axis in "xyz") for p in grid.points_cm)
    weights = tuple(Fraction(w) * 3 for w in grid.weights)
    snapshot = NativeSurfaceSnapshot(
        "original-body",
        0,
        0,
        "original-edge",
        1,
        1,
        (Fraction(0), Fraction(0), Fraction(1), Fraction(1)),
        (Fraction(0), Fraction(0), Fraction(1), Fraction(1)),
        (points[:2], points[2:]),
        (weights[:2], weights[2:]),
    )
    return grid, snapshot


@pytest.mark.parametrize("shift", (Fraction(1, 200), Fraction(1, 50)))
def test_complete_support_bound_includes_observed_control_displacement(shift: Fraction) -> None:
    """
    A translated native rectangle gives a known whole-surface error on either side of the gate.
    """
    grid, actual = surfaces()
    moved = replace(
        actual, rows=tuple(tuple((p[0] + shift, p[1], p[2]) for p in row) for row in actual.rows)
    )
    result = compare(grid, moved, checkpoint)
    assert result.upper_mm == shift + grid.distance_upper_mm
    assert (result.status == "within_0.01mm_position_bound") == (shift < Fraction(1, 100))


def test_equal_support_accepts_common_weight_scale_but_not_changed_parameterization() -> None:
    """
    Common homogeneous scaling preserves correspondence; a single changed weight does not.
    """
    grid, actual = surfaces()
    assert compare(grid, actual, checkpoint).upper_mm == grid.distance_upper_mm
    changed = replace(actual, weights=((Fraction(4), actual.weights[0][1]), actual.weights[1]))
    assert compare(grid, changed, checkpoint).status == "unresolved_native_weights"
    changed = replace(actual, knots_u=(Fraction(0), Fraction(0), Fraction(2), Fraction(2)))
    assert compare(grid, changed, checkpoint).status == "unresolved_native_basis"
