"""
Verify actual curved-phase negative witnesses and shared discovery budgets without saved layouts.
"""

from __future__ import annotations

import math
from dataclasses import fields, replace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact import ProbeResult
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware.curved_discovery import CurvedProbe
from experiments.experiment_ribbon_terminal_hardware.restoration_order import MaterialFocus
from experiments.experiment_ribbon_terminal_hardware.restoration_screen import screen
from tests.test_ribbon_aesthetic import _route


def _curved_crossing(lines: int, diameter: float, side: int, turn: int) -> FoldRoute:
    """
    Place a separate straight through one actual curved material point in a rotated world frame.

    These disconnected placed-piece controls exercise original strict inverses;
    they are not endpoint solutions or complete native geometry coverage.
    """
    width = (lines + 0.2) * diameter
    geometry = fold(2 * diameter, width, turn * 1.2, side * 0.4, 0)
    source = _route((geometry, Straight(5 * diameter), Straight(4 * diameter)))
    targets = replace(source.targets, lines=lines, diameter_mm=diameter)
    pose = Pose(
        Vector3(10 * diameter, -7 * diameter, 4 * diameter), Vector3(0, 1, 0), Vector3(0, 0, 1)
    )
    piece = PlacedPiece(pose, geometry, "authored curved crossing")
    q = side * (width / 2 - diameter / 4)
    xi = geometry.radius_mm * abs(geometry.angle_radians) / 2

    def sample(across: float) -> tuple[Vector3, Vector3, Vector3, Vector3]:
        """
        Follow the same fixed curved progress while changing the material width coordinate.
        """
        along = geometry.before_mm + (xi - math.sin(geometry.bank_radians) * across) / math.cos(
            geometry.bank_radians
        )
        return piece.surface(along / geometry.material_length_mm, across)

    point, velocity, width_velocity, _ = sample(q)
    normal = unit(cross(velocity, width_velocity))
    ruling = unit(difference(sample(q + diameter / 8)[0], point))
    other_pose = Pose(point.translated(normal, -2 * diameter), normal, unit(cross(ruling, normal)))
    other = PlacedPiece(other_pose, Straight(4 * diameter), "independent transverse straight")
    return replace(source, targets=targets, pieces=(piece, source.pieces[1], other))


@pytest.mark.parametrize("lines,diameter", ((1, 0.25), (3, 1.0), (9, 0.75)))
@pytest.mark.parametrize("side", (-1, 1))
@pytest.mark.parametrize("turn", (-1, 1))
def test_curved_material_midpoint_uses_actual_width_dependent_phase_and_both_inverses(
    lines: int,
    diameter: float,
    side: int,
    turn: int,
) -> None:
    """
    Detect both width sides under independent scales, turn signs and rigid placement.
    """
    route = _curved_crossing(lines, diameter, side, turn)
    context = CurvedProbe()
    result = context(route, 0, 2, 6, lambda: None)
    witness = result.witness
    assert witness is not None and witness.pieces == (0, 2)
    assert result.pairs_checked == context.candidates <= 3
    assert context.inverse_tests == 2 * context.candidates
    first = witness.first
    geometry = route.pieces[0].geometry
    assert isinstance(geometry, CylindricalFold)
    xi = (
        math.cos(geometry.bank_radians)
        * (first[0] * geometry.material_length_mm - geometry.before_mm)
        + math.sin(geometry.bank_radians) * first[1]
    )
    assert xi == pytest.approx(geometry.radius_mm * abs(geometry.angle_radians) / 2)
    assert first[1] * side > 0
    for index, expected in zip(witness.pieces, (witness.first, witness.second)):
        assert occupied_coordinates(route.pieces[index], witness.point, lines, diameter) == expected
    result = screen(
        route,
        FlatProbe(),
        32,
        lambda: None,
        lambda _: True,
        focus=MaterialFocus(route, ((0, 2),)),
        curved_probe=CurvedProbe(),
    )
    assert result.status == "penetration" and result.pairs_checked <= 7
    assert result.witness is not None and result.witness.pieces == (0, 2)
    assert len(fields(result)) == 9 and len(fields(FlatProbe())) == 4


@pytest.mark.parametrize("allowance", (0, 1, 2, 6, 32))
def test_curved_misses_and_declined_witnesses_never_grant_clearance_or_more_work(
    allowance: int,
) -> None:
    """
    Preserve the same comparison pool for limited sampling, callback rejection and actual separation.
    """
    route = _curved_crossing(3, 1, -1, 1)
    other = route.pieces[2]
    far = replace(
        other, pose=replace(other.pose, origin=other.pose.origin.translated(Vector3(1, 0, 0), 100))
    )
    for candidate in (route, replace(route, pieces=route.pieces[:2] + (far,))):
        measured = screen(
            candidate,
            FlatProbe(),
            allowance,
            lambda: None,
            lambda _: False,
            curved_probe=CurvedProbe(),
        )
        assert measured.status == "unresolved" and measured.witness is None
        assert measured.pairs_checked <= allowance


def test_prepass_and_flat_hulls_share_root_debits_and_leave_every_pair_eligible() -> None:
    """
    Revisit already charged roots for flat work without duplicate root charges or a separate hull pool.
    """
    route = _route((Straight(2),) * 6)
    probe: Any = Mock(supports=0, return_value=ProbeResult(1))
    curves = CurvedProbe()
    result = screen(route, probe, 32, lambda: None, lambda _: False, curved_probe=curves)
    expected = tuple((a, b) for a in range(6) for b in range(a + 2, 6))
    observed = tuple((call.args[1], call.args[2]) for call in probe.call_args_list)
    assert observed == expected and len(observed) == len(set(observed))
    assert result.status == "unresolved" and result.pairs_checked == 2 * len(expected)
    assert curves.candidates == curves.inverse_tests == 0


@pytest.mark.parametrize("side", (-1, 1))
def test_phase_breadth_reaches_later_curved_material_before_flat_support_starvation(
    side: int,
) -> None:
    """
    Reach the fifth prioritized pair before any flat hull can consume the shared support pool.
    """
    crossing = _curved_crossing(3, 1, side, 1)
    source = _route((Straight(2),) * 9)
    pieces = list(source.pieces)
    pieces[6], pieces[8] = crossing.pieces[0], crossing.pieces[2]
    route = replace(source, targets=crossing.targets, pieces=tuple(pieces))
    focus = MaterialFocus(route, ((0, 2), (0, 3), (1, 3), (2, 4), (6, 8)))
    flat: Any = Mock(
        supports=0, side_effect=AssertionError("Flat refinement starved phase discovery")
    )
    curves = CurvedProbe()
    result = screen(route, flat, 32, lambda: None, lambda _: True, focus=focus, curved_probe=curves)
    assert result.status == "penetration" and result.witness is not None
    assert result.witness.pieces == (6, 8) and result.pairs_checked == 5 + curves.candidates <= 16
    flat.assert_not_called()


@pytest.mark.parametrize("allowance", (-1, True, 1.5))
def test_curved_probe_rejects_malformed_comparison_allowances(allowance: Any) -> None:
    """
    Numeric coercion cannot invent a usable discovery budget.
    """
    with pytest.raises(ValueError):
        CurvedProbe()(_curved_crossing(1, 1, -1, 1), 0, 2, allowance, lambda: None)


def test_exhausted_support_context_and_cancellation_cannot_be_bypassed_by_curved_discovery() -> (
    None
):
    """
    Keep original owner stop gates and propagate preparation/measurement cancellation unchanged.
    """
    route = _curved_crossing(3, 1, -1, 1)
    context = CurvedProbe()
    probe = FlatProbe(supports=2048)
    result = screen(route, probe, 32, lambda: None, lambda _: True, curved_probe=context)
    assert result.status == "unresolved" and result.pairs_checked == 0
    assert context.candidates == context.inverse_tests == 0 and probe.supports == 2048
    with pytest.raises(InterruptedError, match="original guard"):
        screen(
            route,
            FlatProbe(),
            32,
            Mock(side_effect=InterruptedError("original guard")),
            lambda _: True,
            curved_probe=context,
        )


@pytest.mark.parametrize("bad", ("count", "identity", "point"))
def test_owner_revalidates_curved_work_and_original_material_witness(bad: str) -> None:
    """
    A typed optional proposer cannot invent comparisons, piece identities or actual occupancy.
    """
    route = _curved_crossing(3, 1, -1, 1)
    valid = CurvedProbe()(route, 0, 2, 6, lambda: None)
    assert valid.witness is not None
    witness = valid.witness
    if bad == "identity":
        witness = replace(witness, pieces=(0, 1))
    elif bad == "point":
        witness = replace(witness, point=Vector3(100, 100, 100))
    proposer: Any = Mock(return_value=ProbeResult(99 if bad == "count" else 1, witness))
    with pytest.raises(ArithmeticError):
        screen(route, FlatProbe(), 32, lambda: None, lambda _: True, curved_probe=proposer)
