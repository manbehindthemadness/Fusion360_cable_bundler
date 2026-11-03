"""
Challenge the experimental correlated projection independently of contact decisions.
"""

import math

import pytest

from cable_bundler.routing.geometry import Vector3, cross, dot, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, projection
from experiments.experiment_ribbon_fold_route.contact_bounds import interval_projection as original
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight


@pytest.mark.parametrize("bank", [0.0, 1e-12, -0.426, 0.7, -1.3])
@pytest.mark.parametrize("angle", [1e-7, 1.2, -3.048, math.pi, -math.pi])
def test_correlated_enclosure_contains_thick_material(bank: float, angle: float) -> None:
    """
    Include both planes, cylinder and interior points at varied signs and bank scales.
    """
    lead = 2.4 * abs(math.tan(bank))
    fold = CylindricalFold(0.76, angle, bank, 4.8, lead, lead + 0.4)
    piece = PlacedPiece(Pose(Vector3(10, -4, 7), Vector3(0, 1, 0), Vector3(0, 0, 1)), fold, "test")
    for low, high, qlow, qhigh in ((0.0, 1.0, -2.4, 2.4), (0.11, 0.83, -1.7, 2.0)):
        cell = Cell(0, Span(low, high), Span(qlow, qhigh), Span(-0.75, 0.75))
        for axis in (Vector3(1, 0, 0), Vector3(0, 1, 0), unit(Vector3(1, 2, -3))):
            bound = projection(piece, cell, axis)
            for i in range(17):
                u = low + (high - low) * i / 16
                for j in range(9):
                    q = qlow + (qhigh - qlow) * j / 8
                    point, velocity, across, _ = piece.surface(u, q)
                    for height in (-0.75, -0.13, 0.75):
                        value = dot(point.translated(unit(cross(velocity, across)), height), axis)
                        assert bound.low <= value <= bound.high


def test_cylinder_stationary_phase_is_included_without_sampling() -> None:
    """
    Bound a known off-grid interior maximum on a zero-bank half cylinder exactly.
    """
    fold = CylindricalFold(2, math.pi, 0, 4, 0, 0)
    piece = PlacedPiece(Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), fold, "test")
    axis = unit(Vector3(0.7, 0, -0.3))
    cell = Cell(0, Span(0, 1), Span(-2, 2), Span(-0.5, 0.5))
    bound = projection(piece, cell, axis)
    maximum = 2.5 * math.hypot(axis.x, axis.z) + 2 * axis.z
    assert bound.high == pytest.approx(maximum, abs=2e-9)


def test_banked_plane_preserves_coordinate_correlation() -> None:
    """
    Eliminate a demonstrably loose interval without shrinking the material envelope.
    """
    bank = math.pi / 4
    fold = CylindricalFold(2, 1, bank, 4, 10, 10)
    piece = PlacedPiece(Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), fold, "test")
    cell = Cell(0, Span(0, 0.1), Span(-2, 2), Span(-0.5, 0.5))
    axis = Vector3(1, 0, 0)
    tight, loose = projection(piece, cell, axis), original(piece, cell, axis)
    assert tight.low == pytest.approx(0, abs=2e-9)
    assert tight.high == pytest.approx(0.1 * fold.material_length_mm, abs=2e-9)
    assert tight.high - tight.low < (loose.high - loose.low) * 0.6


def test_straight_bounds_are_unchanged() -> None:
    """
    Delegate unaffected straight cells to the existing interval implementation.
    """
    piece = PlacedPiece(
        Pose(Vector3(1, 2, 3), Vector3(1, 0, 0), Vector3(0, 1, 0)), Straight(10), "test"
    )
    cell = Cell(0, Span(0, 1), Span(-2, 2), Span(-0.5, 0.5))
    axis = unit(Vector3(1, 2, -3))
    assert projection(piece, cell, axis) == original(piece, cell, axis)
