"""
Verify bounded flat-phase negative discovery on authored material, never saved layouts.
"""

from __future__ import annotations

import math
from dataclasses import fields, replace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route import contact_phase_core
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_core import core_dimensions
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.contact_phase_core import CoreProbe
from experiments.experiment_ribbon_fold_route.contact_phase_prism import CorePreparations, prepare
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware.curved_discovery import CurvedProbe
from experiments.experiment_ribbon_terminal_hardware.restoration_order import MaterialFocus
from experiments.experiment_ribbon_terminal_hardware.restoration_screen import screen
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_curved_discovery import _curved_crossing


def _phase_point(piece: PlacedPiece, phase: FlatPhase, q: float) -> Vector3:
    """
    Choose an interior point of an actual bank-dependent flat phase for analytical authoring.
    """
    geometry = piece.geometry
    assert isinstance(geometry, CylindricalFold)
    c, s = math.cos(geometry.bank_radians), math.sin(geometry.bank_radians)
    boundary = geometry.before_mm - s * q / c
    along = (
        boundary / 2
        if phase is FlatPhase.BEFORE
        else (
            boundary
            + geometry.radius_mm * abs(geometry.angle_radians) / c
            + geometry.material_length_mm
        )
        / 2
    )
    return piece.surface(along / geometry.material_length_mm, q)[0]


def _flat_crossing(
    lines: int, diameter: float, side: int, turn: int, phase: FlatPhase
) -> FoldRoute:
    """
    Pass a transverse straight through one flat phase in a rotated, translated world frame.

    These disconnected material controls are not endpoint solutions or native
    geometry coverage. Their shared point lies strictly inside both actual cores.
    """
    geometry = fold(2 * diameter, (lines + 0.2) * diameter, turn * 1.2, side * 0.4, 0)
    source = _route((geometry, Straight(5 * diameter), Straight(4 * diameter)))
    pose = Pose(
        Vector3(10 * diameter, -7 * diameter, 4 * diameter), Vector3(0, 1, 0), Vector3(0, 0, 1)
    )
    piece = PlacedPiece(pose, geometry, "authored flat phase")
    q = side * lines * diameter * 0.15
    point = _phase_point(piece, phase, q)
    along = geometry.before_mm - math.tan(geometry.bank_radians) * q
    if phase is FlatPhase.AFTER:
        along = geometry.material_length_mm
    _, velocity, width, _ = piece.surface(along / geometry.material_length_mm, q)
    normal = unit(cross(velocity, width))
    other = PlacedPiece(
        Pose(point.translated(normal, -2 * diameter), normal, unit(width)),
        Straight(4 * diameter),
        "authored transverse straight",
    )
    return replace(
        source,
        targets=replace(source.targets, lines=lines, diameter_mm=diameter),
        pieces=(piece, source.pieces[1], other),
    )


@pytest.mark.parametrize("lines,diameter", ((1, 0.25), (3, 1.0), (9, 0.75)))
@pytest.mark.parametrize("side", (-1, 1))
@pytest.mark.parametrize("turn", (-1, 1))
@pytest.mark.parametrize("phase", (FlatPhase.BEFORE, FlatPhase.AFTER))
def test_flat_phase_cores_verify_both_actual_material_inverses(
    lines: int, diameter: float, side: int, turn: int, phase: FlatPhase
) -> None:
    """
    Cover conductor width, thickness scale, banks, turns and both actual affine phases.
    """
    route = _flat_crossing(lines, diameter, side, turn, phase)
    opposite = FlatPhase.AFTER if phase is FlatPhase.BEFORE else FlatPhase.BEFORE
    context = CoreProbe()
    measured = context(
        route,
        0,
        2,
        1,
        lambda: None,
        excluded_phases=frozenset(((opposite, FlatPhase.STRAIGHT),)),
    )
    witness = measured.witness
    assert witness is not None and witness.pieces == (0, 2)
    assert measured.pairs_checked == context.comparisons == context.witnesses == 1
    assert 0 < context.edges <= 30 and context.inverse_tests == 2
    for index, expected in zip(witness.pieces, (witness.first, witness.second)):
        assert occupied_coordinates(route.pieces[index], witness.point, lines, diameter) == expected
    geometry = route.pieces[0].geometry
    assert isinstance(geometry, CylindricalFold)
    xi = (
        math.cos(geometry.bank_radians)
        * (witness.first[0] * geometry.material_length_mm - geometry.before_mm)
        + math.sin(geometry.bank_radians) * witness.first[1]
    )
    if phase is FlatPhase.BEFORE:
        assert xi < 0
    else:
        assert xi > geometry.radius_mm * abs(geometry.angle_radians)


@pytest.mark.parametrize("left", (FlatPhase.BEFORE, FlatPhase.AFTER))
@pytest.mark.parametrize("right", (FlatPhase.BEFORE, FlatPhase.AFTER))
@pytest.mark.parametrize("side", (-1, 1))
def test_two_banked_fold_phases_share_a_verified_core_point(
    left: FlatPhase, right: FlatPhase, side: int
) -> None:
    """
    Verify oblique polygon clipping between two independently placed fold phases.
    """
    route = _flat_crossing(3, 1.0, side, 1, left)
    target = _phase_point(route.pieces[0], left, 0.4)
    geometry = fold(2.5, 3.2, -0.9, -side * 0.32, 0)
    other = PlacedPiece(
        Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 0, 1)), geometry, "other phase"
    )
    shift = difference(target, _phase_point(other, right, 0.0))
    other = replace(other, pose=replace(other.pose, origin=shift))
    route = replace(route, pieces=(route.pieces[0], route.pieces[1], other))
    excluded = frozenset(
        (a, b)
        for a in (FlatPhase.BEFORE, FlatPhase.AFTER)
        for b in (FlatPhase.BEFORE, FlatPhase.AFTER)
        if (a, b) != (left, right)
    )
    measured = CoreProbe()(route, 0, 2, 1, lambda: None, excluded_phases=excluded)
    assert measured.witness is not None and measured.pairs_checked == 1
    for index in (0, 2):
        assert occupied_coordinates(route.pieces[index], measured.witness.point, 3, 1.0) is not None


def _parallel_strips(offset: float) -> FoldRoute:
    """
    Place two independent parallel one-conductor strips at a declared height offset.
    """
    source = _route((Straight(4), Straight(5), Straight(4)))
    first = source.pieces[0]
    normal = unit(cross(first.pose.tangent, first.pose.width))
    other = replace(
        first, pose=replace(first.pose, origin=first.pose.origin.translated(normal, offset))
    )
    return replace(
        source,
        targets=replace(source.targets, lines=1, diameter_mm=1.0),
        pieces=(first, source.pieces[1], other),
    )


@pytest.mark.parametrize("offset", (0.0, 0.4))
def test_straight_cores_recompute_witnesses_but_reuse_only_exact_preparation(offset: float) -> None:
    """
    Preparation hits never replace current inverse tests or return a cached physical result.
    """
    route = _parallel_strips(offset)
    context = CoreProbe()
    results = [context(route, 0, 2, 1, lambda: None) for _ in range(2)]
    assert all(result.witness is not None for result in results)
    assert context.comparisons == context.witnesses == 2
    assert context.inverse_tests == 4 and context.edges == 48
    unique = 2 if offset else 1
    assert context.preparations() == {
        "hits": 4 - unique,
        "preparations": unique,
        "retained": unique,
        "capacity": 64,
    }
    if offset:
        changed = _parallel_strips(offset / 2)
        measured = context(changed, 0, 2, 1, lambda: None)
        assert measured.witness is not None and measured.witness != results[-1].witness
        assert context.preparations()["preparations"] == 3


@pytest.mark.parametrize("offset", (1.0, 2.0))
def test_actual_tangency_and_separation_supply_no_negative_witness(offset: float) -> None:
    """
    Empty core intersections remain unresolved and never supply an axis or clearance.
    """
    route = _parallel_strips(offset)
    context = CoreProbe()
    measured = context(route, 0, 2, 1, lambda: None)
    assert measured.witness is None and measured.axis_proposal is None
    assert context.inverse_tests == context.witnesses == 0
    result = screen(route, FlatProbe(), 32, lambda: None, lambda _: True, flat_core_probe=context)
    assert result.status == "unresolved"


def test_lobe_only_crossing_can_miss_the_core_and_still_requires_the_full_probe() -> None:
    """
    Demonstrate why a core miss must never replace complete joined-profile checking.
    """
    route = _parallel_strips(0.8)
    context = CoreProbe()
    assert context(route, 0, 2, 1, lambda: None).witness is None
    point = (
        route.pieces[0]
        .surface(0.5, 0.0)[0]
        .translated(unit(cross(route.pieces[0].pose.tangent, route.pieces[0].pose.width)), 0.4)
    )
    assert all(occupied_coordinates(route.pieces[i], point, 1, 1.0) for i in (0, 2))
    full = FlatProbe()
    assert full(route, 0, 2, 32, lambda: None).witness is not None
    focus = MaterialFocus(route, ((0, 2),))
    negative = screen(
        route, full, 32, lambda: None, lambda _: True, focus=focus, flat_core_probe=context
    )
    assert negative.status == "unresolved" and negative.witness is None
    assert (
        screen(route, FlatProbe(), 32, lambda: None, lambda _: True, focus=focus).status
        == "penetration"
    )


def test_curved_only_witness_stays_with_the_original_curved_discovery() -> None:
    """
    Flat-core misses neither claim curved coverage nor suppress the independent curved candidate path.
    """
    route = _curved_crossing(1, 1.0, 1, 1)
    piece = route.pieces[0]
    assert isinstance(piece.geometry, CylindricalFold)
    geometry = replace(piece.geometry, radius_mm=20.0)
    piece = replace(piece, geometry=geometry)
    q = route.half_width_mm - 0.25
    along = geometry.before_mm + (
        geometry.radius_mm * abs(geometry.angle_radians) / 2 - math.sin(geometry.bank_radians) * q
    ) / math.cos(geometry.bank_radians)
    point, velocity, width, _ = piece.surface(along / geometry.material_length_mm, q)
    normal = unit(cross(velocity, width))
    other = PlacedPiece(
        Pose(point.translated(normal, -2), normal, unit(velocity)),
        Straight(4),
        "curved-only control",
    )
    route = replace(route, pieces=(piece, route.pieces[1], other))
    assert CoreProbe()(route, 0, 2, 2, lambda: None).witness is None
    result = screen(
        route,
        FlatProbe(),
        32,
        lambda: None,
        lambda _: True,
        focus=MaterialFocus(route, ((0, 2),)),
        curved_probe=CurvedProbe(),
        flat_core_probe=CoreProbe(),
    )
    assert result.status == "penetration" and "curved" in result.reason


def test_comparison_exhaustion_and_covered_phases_do_not_renew_work() -> None:
    """
    Charge the last permitted phase exactly once; exclusions are local guidance identity only.
    """
    route = _flat_crossing(3, 1.0, 1, 1, FlatPhase.AFTER)
    context = CoreProbe()
    assert context(route, 0, 2, 0, lambda: None).pairs_checked == 0
    assert context.preparations()["preparations"] == 0
    limited = context(route, 0, 2, 1, lambda: None)
    assert limited.witness is None and limited.limit == "pairs" and limited.pairs_checked == 1
    assert context(route, 0, 2, 2, lambda: None).witness is not None
    skipped = context(
        route,
        0,
        2,
        2,
        lambda: None,
        excluded_phases=frozenset(
            (phase, FlatPhase.STRAIGHT) for phase in (FlatPhase.BEFORE, FlatPhase.AFTER)
        ),
    )
    assert skipped.pairs_checked == 0 and skipped.witness is None
    assert context.skipped_phase_pairs == 2
    assert context(route, 0, 2, 2, lambda: None).witness is not None


def test_screen_preserves_root_budget_and_the_original_exhausted_support_stop() -> None:
    """
    Core discovery cannot reactivate an exhausted ordinary context or escape root accounting.
    """
    route = _flat_crossing(3, 1.0, 1, 1, FlatPhase.AFTER)
    context, full = CoreProbe(), FlatProbe()
    focus = MaterialFocus(route, ((0, 2),))
    limited = screen(
        route, full, 2, lambda: None, lambda _: True, focus=focus, flat_core_probe=context
    )
    assert limited.status == "unresolved" and limited.pairs_checked == 2
    accepted = screen(
        route, full, 3, lambda: None, lambda _: True, focus=focus, flat_core_probe=context
    )
    assert accepted.status == "penetration" and accepted.pairs_checked == 3
    assert "flat-core" in accepted.reason
    before = context.comparisons
    full.supports = 2048
    stopped = screen(
        route,
        full,
        32,
        lambda: None,
        lambda _: True,
        focus=focus,
        curved_probe=CurvedProbe(),
        flat_core_probe=context,
    )
    assert stopped.status == "unresolved" and stopped.pairs_checked == 0
    assert context.comparisons == before and full.supports == 2048


def test_cancellation_and_failed_strict_inverse_never_become_optional_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve hard caller failures and count partially examined edges separately from inverse work.
    """
    route = _parallel_strips(0.4)
    context = CoreProbe()

    def checkpoint() -> None:
        """
        Interrupt the active edge traversal after a small known prefix.
        """
        if context.edges == 2:
            raise RuntimeError("source changed")

    with pytest.raises(RuntimeError, match="source changed"):
        context(route, 0, 2, 1, checkpoint)
    assert (context.comparisons, context.inverse_tests) == (1, 0)
    assert context.edges == 2
    inverse = Mock(return_value=None)
    monkeypatch.setitem(vars(contact_phase_core), "occupied_coordinates", inverse)
    result = CoreProbe()(route, 0, 2, 1, lambda: None)
    assert result.witness is None and inverse.call_count == 2


@pytest.mark.parametrize("remaining", (-1, 1.5, True))
def test_invalid_comparison_allocations_are_rejected(remaining: Any) -> None:
    """
    Reject malformed external work without geometry preparation.
    """
    with pytest.raises(ValueError, match="allowance"):
        CoreProbe()(_parallel_strips(0.4), 0, 2, remaining, lambda: None)


def test_bounded_preparation_and_public_receipts_keep_their_original_contracts() -> None:
    """
    Eviction loses pure geometry reuse only; public contact and hull counters stay unchanged.
    """
    source = _parallel_strips(0.4).pieces[0]
    context = CorePreparations()
    for index in range(65):
        placed = replace(source, pose=replace(source.pose, origin=Vector3(index, 0, 0)))
        assert context(placed, FlatPhase.STRAIGHT, 1, 1.0) is not None
    assert context.statistics() == {"hits": 0, "preparations": 65, "retained": 64, "capacity": 64}
    assert core_dimensions(3, 0.75) == (3 * 0.75 / 2, 0.3 * 0.75)
    with pytest.raises(ValueError):
        prepare(source, FlatPhase.BEFORE, 1, 1.0)
    with pytest.raises(ValueError):
        core_dimensions(0, 1.0)
    assert len(fields(FlatProbe)) == 4 and len(fields(ContactResult)) == 9
