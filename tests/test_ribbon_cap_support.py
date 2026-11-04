"""
Challenge analytic cap halfspaces independently through placed thick-material points.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, cap_neighborhood
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy, cap_region
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose
from tests.test_fold_contact import _route


@pytest.mark.parametrize("angle", (-2.7, -2.1, 2.1, 2.7))
@pytest.mark.parametrize("bank", (-0.35, -0.188, 0.188, 0.35))
@pytest.mark.parametrize("at_end", (False, True))
def test_additional_support_contains_complete_sampled_thickness(
    angle: float, bank: float, at_end: bool
) -> None:
    """
    Check both signs and reversed caps on cells that the original monotonicity proof cannot certify.
    """
    half = 3.075
    lead = half * abs(math.tan(bank))
    fold = CylindricalFold(0.3765061, angle, bank, 2 * half, lead, lead)
    piece = PlacedPiece(
        Pose(Vector3(10, -4, 7), Vector3(0, 1, 0), Vector3(0, 0, 1)), fold, "banked"
    )
    cap = piece.end_pose() if at_end else piece.pose
    additions = 0
    for lo, hi in ((0.0, 1.0), (0.0, 0.3), (0.7, 1.0), (0.2, 0.8)):
        for qlo, qhi in ((-half, -half / 2), (-half / 2, 0.0), (0.0, half / 2), (half / 2, half)):
            cell = Cell(0, Span(lo, hi), Span(qlo, qhi), Span(-0.375, 0.375))
            historical = cap_neighborhood(piece, cell, at_end)
            assert cap_region(piece, cell, at_end, CapPolicy.MONOTONE) is historical
            if historical or not cap_region(piece, cell, at_end, CapPolicy.ANALYTIC_SUPPORT):
                continue
            additions += 1
            for i in range(5):
                for j in range(5):
                    point, velocity, width, _ = piece.surface(
                        lo + (hi - lo) * i / 4, qlo + (qhi - qlo) * j / 4
                    )
                    for height in (-0.375, 0.0, 0.375):
                        occupied = point.translated(unit(cross(velocity, width)), height)
                        distance = dot(difference(occupied, cap.origin), cap.tangent)
                        assert distance <= 1e-10 if at_end else distance >= -1e-10
    assert additions > 0


def test_support_does_not_waive_a_closed_half_turn_or_invalid_policy() -> None:
    """
    Preserve ambiguous touching volumes and reject unrecognized certification strategies.
    """
    fold = CylindricalFold(0.75 / 0.996, math.pi, 0.0, 4.8, 0.0, 0.0)
    first = PlacedPiece(Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), fold, "first")
    second = PlacedPiece(first.end_pose(), fold, "second")
    route = _route(first, second)
    assert (
        inspect_contact(route, maximum_pairs=1000, cap_policy=CapPolicy.ANALYTIC_SUPPORT).status
        != "separated"
    )
    with pytest.raises(ValueError, match="cap separation policy"):
        inspect_contact(route, cap_policy="analytic_support")  # type: ignore[arg-type]
