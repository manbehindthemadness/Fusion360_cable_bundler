"""
Distinguish legitimate shared boundary support from unsupported returning material interiors.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span
from experiments.experiment_ribbon_fold_route.contact_cap_factor import entry_arc_supported
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy, cap_region
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from tests.test_fold_contact_caps import _chain
from tests.test_ribbon_restoration_handoff import _source as _crossing_source


@pytest.mark.parametrize("scale", (1e-3, 1.0, 1e3))
@pytest.mark.parametrize("sign", (-1, 1))
@pytest.mark.parametrize("at_end", (False, True))
@pytest.mark.parametrize("bank", (-0.5, 0.0, 0.5))
def test_factored_cap_support_encloses_actual_material_across_scales(
    scale: float, sign: int, at_end: bool, bank: float
) -> None:
    """
    Every newly certified complete cell retains actual guarded inward cap distances.
    """
    before = scale * abs(math.tan(bank))
    geometry = CylindricalFold(scale, sign * 2.5, bank, 2 * scale, before, before)
    pose = Pose(Vector3(13 * scale, -7 * scale, 2 * scale), Vector3(0, 1, 0), Vector3(0, 0, 1))
    piece = PlacedPiece(pose, geometry, "analytical factored cap")
    cell = Cell(0, Span(0, 1), Span(-scale, scale), Span(-scale / 4, scale / 4))
    assert entry_arc_supported(piece, cell, at_end)
    assert cap_region(piece, cell, at_end, CapPolicy.FACTORED_SUPPORT)
    assert not cap_region(piece, cell, at_end, CapPolicy.ANALYTIC_SUPPORT)
    cap = piece.end_pose() if at_end else piece.pose
    tangent = cap.tangent
    axis = Vector3(-tangent.x, -tangent.y, -tangent.z) if at_end else tangent
    guard = 1e-11 * (1 + geometry.material_length_mm + 2 * before + 4 * scale)
    for u in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0):
        for q in (-scale, 0.0, scale):
            for height in (-scale / 4, 0.0, scale / 4):
                point, velocity, width, _ = piece.surface(u, q)
                occupied = point.translated(unit(cross(velocity, width)), height)
                assert dot(difference(occupied, cap.origin), axis) >= -guard


@pytest.mark.parametrize("sign", (-1, 1))
@pytest.mark.parametrize("at_end", (False, True))
def test_factored_interior_cannot_exempt_a_backtracking_exit(sign: int, at_end: bool) -> None:
    """
    A positive circular factor grants no clearance to exit-plane material across the cap.
    """
    geometry = CylindricalFold(1, sign * 2.5, 0, 2, 10 if at_end else 0, 0 if at_end else 10)
    pose = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    piece = PlacedPiece(pose, geometry, "analytical cap return")
    cell = Cell(0, Span(0, 1), Span(-1, 1), Span(-0.25, 0.25))
    assert entry_arc_supported(piece, cell, at_end)
    assert not cap_region(piece, cell, at_end, CapPolicy.FACTORED_SUPPORT)


def test_zero_factor_halfturn_and_invalid_material_domains_are_unsupported() -> None:
    """
    Decline degenerate factor, outside width, reversed spans, nonfinite input and irregular thickness.
    """
    pose = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    piece = PlacedPiece(pose, CylindricalFold(1, math.pi, 0, 2, 0, 0), "zero-factor halfturn")
    cell = Cell(0, Span(0, 1), Span(-1, 1), Span(-0.25, 0.25))
    assert not entry_arc_supported(piece, cell, False)
    piece = replace(piece, geometry=CylindricalFold(1, 2.5, 0, 2, 0, 0))
    for malformed in (
        replace(cell, u=Span(-0.1, 1)),
        replace(cell, q=Span(-1.1, 1)),
        replace(cell, height=Span(0.25, -0.25)),
        replace(cell, height=Span(-1, 1)),
        replace(cell, u=Span(math.nan, 1)),
    ):
        assert not entry_arc_supported(piece, malformed, False)


def test_factored_policy_still_rejects_linked_fold_interior_return() -> None:
    """
    Shared-cap topology and a tiny bridge cannot exempt a genuine folded interior crossing.
    """
    returning = replace(fold(1, 2.4, math.pi, 0, 0), after_mm=0.01)
    route = _chain((fold(1, 2.4, math.pi, 0, 0), Straight(1e-4), returning))
    assert (
        inspect_contact(route, maximum_pairs=1000, cap_policy=CapPolicy.FACTORED_SUPPORT).status
        != "separated"
    )


def test_factored_policy_keeps_genuine_strict_crossing_rejection() -> None:
    """
    A returned witness must occupy both actual material interiors despite stronger cap shortcuts.
    """
    route = _crossing_source()
    result = inspect_contact(route, maximum_pairs=2048, cap_policy=CapPolicy.FACTORED_SUPPORT)
    assert result.status == "penetration" and result.witness is not None
    witness = result.witness
    for index, expected in zip(witness.pieces, (witness.first, witness.second)):
        actual = occupied_coordinates(
            route.pieces[index], witness.point, route.targets.lines, route.targets.diameter_mm
        )
        assert actual is not None and actual == pytest.approx(expected, abs=1e-12, rel=0)
