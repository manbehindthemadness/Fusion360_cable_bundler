"""
Reach late material crossings through bounded focus without replaying saved layouts or granting clearance.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_feature_insertion.separation import Region, Side, regions
from experiments.experiment_ribbon_fold_route.contact import Penetration, ProbeResult
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import Piece, fold
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.material_constraint import MaterialConstraint
from experiments.experiment_ribbon_terminal_hardware.restoration_order import (
    FocusKind,
    MaterialFocus,
    ordered_pairs,
)
from experiments.experiment_ribbon_terminal_hardware.restoration_screen import screen
from tests.test_ribbon_aesthetic import _route


def _checkpoint() -> None:
    """
    Permit finite authored ordering controls without an external host.
    """


def _loop_route(*, leading: bool = True, cycles: int = 2) -> tuple[FoldRoute, int]:
    """
    Author connected repeated hairpins after a distant three-turn prefix.

    Repeated south/north straight lanes and their return flats coincide by
    construction. These are negative-contact controls, never accepted layouts
    or native coverage. Every half turn is legal; no full-turn primitive is used.
    """
    prefix: tuple[Piece, ...] = (
        *((Straight(20),) if leading else ()),
        fold(2, 1.2, math.pi / 2, 0, 0),
        Straight(10),
        fold(2, 1.2, math.pi / 2, 0, 0),
        Straight(5),
        fold(2, 1.2, math.pi / 2, 0, 0),
    )
    cycle = (fold(2, 1.2, math.pi, 0, 1), Straight(4)) * 2
    return _route(prefix + (Straight(4),) + cycle * cycles), len(prefix)


def _current(source: FoldRoute) -> tuple[FoldRoute, SignedJoints]:
    """
    Obtain the exact immutable working placement used by the real signed-joint model.
    """
    model = SignedJoints(source)
    route = model.route(model.initial)
    assert route is not None
    return route, model


def _constraint(
    route: FoldRoute, model: SignedJoints, pair: tuple[int, int], *, point: Vector3 | None = None
) -> tuple[MaterialConstraint, Side]:
    """
    Bind real whole material guidance from independently verified coincident straight interiors.
    """
    point = route.pieces[pair[0]].surface(0.5, 0)[0] if point is None else point
    first, second = (
        occupied_coordinates(
            route.pieces[index], point, route.targets.lines, route.targets.diameter_mm
        )
        for index in pair
    )
    assert first is not None and second is not None
    bound = MaterialConstraint.from_witness(model, route, Penetration(pair, first, second, point))
    assert bound is not None
    return bound, Side.BEFORE


def _guidance(
    route: FoldRoute, model: SignedJoints, offset: int
) -> tuple[tuple[MaterialConstraint, Side], ...]:
    """
    Retain two actual overlapping event neighborhoods while leaving a different return-flat pair new.
    """
    return tuple(_constraint(route, model, (offset + a, offset + b)) for a, b in ((2, 6), (4, 8)))


def _global(route: FoldRoute) -> tuple[tuple[int, int], ...]:
    """
    Describe the original complete nonadjacent pair order independently of focus preparation.
    """
    return tuple((a, b) for a in range(len(route.pieces)) for b in range(a + 2, len(route.pieces)))


def test_actual_late_return_crossing_is_reachable_inside_the_same_small_screen() -> None:
    """
    Verify a genuinely new late flat witness through both strict inverse maps under the original32pool.
    """
    prefix = (
        Straight(20),
        fold(2, 1.2, math.pi / 2, 0, 0),
        Straight(10),
        fold(2, 1.2, math.pi / 2, 0, 0),
        Straight(5),
        fold(2, 1.2, math.pi / 2, 0, 0),
        Straight(7),
        fold(2, 1.2, math.pi / 2, 0, 0),
    )
    source = _route(
        prefix
        + (Straight(10), fold(2, 1.2, math.pi, 0, 1), fold(2, 1.2, math.pi, 0, 1), Straight(10))
    )
    offset = len(prefix)
    route, model = _current(source)
    returning = route.pieces[offset + 2]
    point = returning.surface(1 - 0.5 / returning.geometry.material_length_mm, 0)[0]
    guidance = (_constraint(route, model, (offset, offset + 2), point=point),)
    focus = MaterialFocus.from_constraints(route, model, model.initial, guidance, _checkpoint)
    assert focus is not None
    target = (offset + 1, offset + 3)
    known = {(offset, offset + 2)}
    assert target not in known and _global(route).index(target) >= 32
    retained: list[Penetration] = []
    observed: list[tuple[int, int]] = []

    def retain(witness: Penetration) -> bool:
        """
        Accept only the independently intended new return pair, never an already-known crossing.
        """
        observed.append(witness.pieces)
        if witness.pieces != target:
            return False
        retained.append(witness)
        return True

    old = screen(route, FlatProbe(), 32, _checkpoint, retain)
    assert old.status == "unresolved" and not retained
    probe = FlatProbe()
    result = screen(route, probe, 32, _checkpoint, retain, focus=focus)
    assert result.status == "penetration" and result.witness is retained[0], (
        result,
        probe,
        observed,
    )
    assert result.witness is not None and result.witness.pieces == target
    assert result.pairs_checked <= 32
    for index, coordinates in zip(target, (result.witness.first, result.witness.second)):
        assert (
            occupied_coordinates(
                route.pieces[index],
                result.witness.point,
                route.targets.lines,
                route.targets.diameter_mm,
            )
            == coordinates
        )


@pytest.mark.parametrize("leading", (False, True))
def test_local_unknown_pairs_precede_known_pairs_without_filtering_global_remainder(
    leading: bool,
) -> None:
    """
    Keep overlapping event ranges whole, every pair unique and the untouched remainder in original order.
    """
    source, offset = _loop_route(leading=leading)
    route, model = _current(source)
    focus = MaterialFocus.from_constraints(
        route, model, model.initial, _guidance(route, model, offset), _checkpoint
    )
    assert focus is not None and focus.source is route
    known = ((offset + 2, offset + 6), (offset + 4, offset + 8))
    assert focus.priority[-2:] == known
    assert all(offset + 2 <= a < b <= offset + 8 for a, b in focus.priority)
    expected = _global(route)
    ordered = tuple(ordered_pairs(route, focus, _checkpoint))
    assert len(ordered) == len(set(ordered)) == len(expected) and set(ordered) == set(expected)
    assert ordered == focus.priority + tuple(
        pair for pair in expected if pair not in focus.priority
    )
    assert tuple(ordered_pairs(route, None, _checkpoint)) == expected
    assert tuple(ordered_pairs(replace(route), focus, _checkpoint)) == expected


def test_appearing_runway_resolves_same_material_without_inheriting_old_indices() -> None:
    """
    A real absent leading slot may appear; surviving event identities move to new primitive indices.
    """
    source, offset = _loop_route(leading=False)
    route, model = _current(source)
    guidance = _guidance(route, model, offset)
    focus = MaterialFocus.from_constraints(route, model, model.initial, guidance, _checkpoint)
    assert focus is not None and model.initial[0] == 0
    values = (0.2 / model.scale,) + model.initial[1:]
    changed = model.route(values)
    assert changed is not None and len(changed.pieces) == len(route.pieces) + 1
    moved = MaterialFocus.from_constraints(changed, model, values, guidance, _checkpoint)
    assert moved is not None and moved.source is changed
    assert moved.priority == tuple((a + 1, b + 1) for a, b in focus.priority)
    assert tuple(ordered_pairs(changed, focus, _checkpoint)) == _global(changed)
    assert (
        MaterialFocus.from_constraints(changed, model, model.initial, guidance, _checkpoint) is None
    )


def test_disjoint_occupied_neighborhoods_are_not_bridged_into_one_global_prefix() -> None:
    """
    Preserve real material gaps between separate witnessed loops while keeping cross-range pairs eligible later.
    """
    source, offset = _loop_route(cycles=3)
    route, model = _current(source)
    guidance = tuple(
        _constraint(route, model, (offset + a, offset + b)) for a, b in ((0, 4), (8, 12))
    )
    focus = MaterialFocus.from_constraints(route, model, model.initial, guidance, _checkpoint)
    assert focus is not None
    assert all(b <= offset + 4 or a >= offset + 8 for a, b in focus.priority)
    cross = (offset, offset + 12)
    assert cross not in focus.priority and cross in tuple(ordered_pairs(route, focus, _checkpoint))


@pytest.mark.parametrize("leading", (False, True))
def test_combined_discovery_reaches_other_material_or_preserves_shared_exhaustion(
    leading: bool,
) -> None:
    """
    Exercise earlier motion with retained late-loop guidance under the unchanged32pool.

    Both strict original inverses must verify an earlier crossing. Selecting
    a neighborhood measures discovery reach, not absence of other crossings, full
    clearance or complete accepted geometry. The present-leading-slot variant
    exhausts its hull budget before a witness: priority fairness does not imply
    proof-work fairness. Preserve that unresolved limitation, never grant clearance.
    No saved layout is replayed.
    """
    source, offset = _loop_route(leading=leading, cycles=3)
    model = SignedJoints(source)
    original_tags = regions(source)
    values = (model.initial[0] + 0.2 / model.scale,) + model.initial[1:]
    route = model.route(values)
    assert route is not None
    tags = regions(route)
    late_offset = tags.index(original_tags[offset + 4])
    guidance = _guidance(route, model, late_offset)
    retained = MaterialFocus.from_constraints(route, model, values, guidance, _checkpoint)
    assert retained is not None
    retained_priority = retained.priority
    first_retained = min(a for a, _ in retained_priority)
    focus = MaterialFocus.for_correction(route, model, values, guidance, _checkpoint)
    assert focus is not None and focus.kind is FocusKind.COMBINED
    assert len(focus.priority) <= 32
    witnesses: list[Penetration] = []

    def accept(witness: Penetration) -> bool:
        """
        Measure actual earlier material outside the retained late neighborhood.
        """
        if witness.pieces[0] >= first_retained or witness.pieces in retained_priority:
            return False
        witnesses.append(witness)
        return True

    old = screen(route, FlatProbe(), 32, _checkpoint, accept, focus=retained)
    assert old.status == "unresolved" and not witnesses
    probe = FlatProbe()
    result = screen(route, probe, 32, _checkpoint, accept, focus=focus)
    if leading:
        assert result.status == "unresolved" and result.witness is None and not witnesses
        assert result.pairs_checked == 32 and probe.supports < 2048
        return
    assert result.status == "penetration" and result.witness is witnesses[0]
    assert result.pairs_checked <= 32 and result.witness is not None
    for index in result.witness.pieces:
        assert (
            occupied_coordinates(
                route.pieces[index],
                result.witness.point,
                route.targets.lines,
                route.targets.diameter_mm,
            )
            is not None
        )
    ordered = tuple(ordered_pairs(route, focus, _checkpoint))
    assert len(ordered) == len(set(ordered)) == len(_global(route))
    assert set(ordered) == set(_global(route))
    assert ordered[len(focus.priority) :] == tuple(
        pair for pair in _global(route) if pair not in focus.priority
    )


def test_combined_order_defers_known_pairs_and_preserves_each_source_priority() -> None:
    """
    Alternate actual unknown priorities, retaining known rows only after new discovery opportunities.
    """
    source, offset = _loop_route(cycles=3)
    model = SignedJoints(source)
    values = (model.initial[0] + 0.2 / model.scale,) + model.initial[1:]
    route = model.route(values)
    assert route is not None
    guidance = _guidance(route, model, offset + 4)
    retained = MaterialFocus.from_constraints(route, model, values, guidance, _checkpoint)
    motion = MaterialFocus.from_motion(route, model, values, _checkpoint)
    focus = MaterialFocus.for_correction(route, model, values, guidance, _checkpoint)
    assert retained is not None and motion is not None and focus is not None
    assert focus.kind is FocusKind.COMBINED
    assert focus == MaterialFocus.for_correction(route, model, values, guidance, _checkpoint)
    assert focus is not None
    known = retained.known_pairs
    unknown_motion = tuple(pair for pair in motion.priority if pair not in known)
    unknown_retained = tuple(pair for pair in retained.priority if pair not in known)
    assert focus.priority[:2] == (unknown_motion[0], unknown_retained[0])
    assert len(focus.priority) == 32 and not known.intersection(focus.priority)
    assert focus.known_pairs == frozenset()
    with pytest.raises(InterruptedError, match="combined preparation"):
        MaterialFocus.for_correction(
            route,
            model,
            values,
            guidance,
            Mock(side_effect=InterruptedError("combined preparation")),
        )
    for pool in (0, 1, 6, 32):
        result = screen(route, FlatProbe(), pool, _checkpoint, lambda _: False, focus=focus)
        assert result.status == "unresolved" and result.pairs_checked <= pool
    probe = FlatProbe(supports=2048)
    result = screen(route, probe, 32, _checkpoint, lambda _: True, focus=focus)
    assert result.status == "unresolved" and result.pairs_checked == 0 and probe.supports == 2048


def test_correction_focus_falls_back_to_exact_single_source_or_global_order() -> None:
    """
    Unchanged motion and empty retained guidance preserve their existing ordering contracts.
    """
    source, offset = _loop_route()
    route, model = _current(source)
    guidance = _guidance(route, model, offset)
    retained = MaterialFocus.from_constraints(route, model, model.initial, guidance, _checkpoint)
    assert retained is not None and retained.kind is FocusKind.RETAINED
    assert (
        MaterialFocus.for_correction(route, model, model.initial, guidance, _checkpoint) == retained
    )
    assert MaterialFocus.for_correction(route, model, model.initial, (), _checkpoint) is None
    values = (model.initial[0] + 0.2 / model.scale,) + model.initial[1:]
    changed = model.route(values)
    assert changed is not None
    motion = MaterialFocus.from_motion(changed, model, values, _checkpoint)
    assert motion is not None and motion.kind is FocusKind.MOTION
    assert MaterialFocus.for_correction(changed, model, values, (), _checkpoint) == motion
    assert (
        MaterialFocus.for_correction(changed, model, model.initial, guidance, _checkpoint) is None
    )


def test_small_combined_prefix_deduplicates_and_defers_already_represented_pairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Share opportunities in source order and retain known guidance at the end when capacity remains.
    """
    source, offset = _loop_route(cycles=3)
    route, model = _current(source)
    guidance = _guidance(route, model, offset)
    known = frozenset({(5, 9)})
    retained = MaterialFocus(route, ((5, 8), (5, 9), (6, 9)), known, FocusKind.RETAINED)
    motion = MaterialFocus(route, ((5, 9), (0, 2), (5, 8), (1, 3)), kind=FocusKind.MOTION)
    retained_source, motion_source = Mock(return_value=retained), Mock(return_value=motion)
    monkeypatch.setattr(MaterialFocus, "from_constraints", retained_source)
    monkeypatch.setattr(MaterialFocus, "from_motion", motion_source)
    focus = MaterialFocus.for_correction(route, model, model.initial, guidance, _checkpoint)
    assert focus is not None and focus.kind is FocusKind.COMBINED
    assert focus.priority == ((0, 2), (5, 8), (1, 3), (6, 9), (5, 9))
    assert focus.known_pairs == known
    retained_source.assert_called_once_with(route, model, model.initial, guidance, _checkpoint)
    motion_source.assert_called_once_with(route, model, model.initial, _checkpoint)


@pytest.mark.parametrize(
    "invalid", ("missing", "foreign", "reversed", "targets", "values", "duplicate", "empty")
)
def test_unsupported_or_stale_guidance_cannot_guess_a_material_neighborhood(invalid: str) -> None:
    """
    Model ownership, exact placement and unambiguous stable identities remain mandatory for priority.
    """
    source, offset = _loop_route()
    route, model = _current(source)
    bounds = list(_guidance(route, model, offset))
    values = model.initial
    if invalid in ("missing", "reversed"):
        original = bounds[0][0].pair
        pair = (
            (Region(999, True), original[1]) if invalid == "missing" else (original[1], original[0])
        )
        bounds = [(MaterialConstraint(replace(bounds[0][0].bound, pair=pair)), Side.BEFORE)]
    elif invalid == "foreign":
        other = SignedJoints(source)
        bounds = list(_guidance(route, other, offset))
    elif invalid == "targets":
        route = replace(route, targets=replace(route.targets, name="different input"))
    elif invalid == "values":
        values = ()
    elif invalid == "duplicate":
        route = replace(route, pieces=(route.pieces[0],) + route.pieces)
    else:
        bounds = []
    assert MaterialFocus.from_constraints(route, model, values, bounds, _checkpoint) is None


@pytest.mark.parametrize("pool", (0, 1, 6, 32))
def test_focused_miss_never_grants_clearance_or_more_work(pool: int) -> None:
    """
    Declined witnesses and exhausted comparisons remain explicitly unresolved under the same allowance.
    """
    source, offset = _loop_route()
    route, model = _current(source)
    focus = MaterialFocus.from_constraints(
        route, model, model.initial, _guidance(route, model, offset), _checkpoint
    )
    result = screen(route, FlatProbe(), pool, _checkpoint, lambda _: False, focus=focus)
    assert result.status == "unresolved" and result.witness is None
    assert 0 <= result.pairs_checked <= pool


def test_focus_preparation_and_ordering_preserve_original_caller_cancellation() -> None:
    """
    Material scheduling is part of the existing work, never an unguarded preparation phase.
    """
    source, offset = _loop_route()
    route, model = _current(source)
    guidance = _guidance(route, model, offset)
    stop = Mock(side_effect=InterruptedError("original source stop"))
    with pytest.raises(InterruptedError, match="original source stop"):
        MaterialFocus.from_constraints(route, model, model.initial, guidance, stop)
    focus = MaterialFocus.from_constraints(route, model, model.initial, guidance, _checkpoint)
    with pytest.raises(InterruptedError, match="original source stop"):
        tuple(ordered_pairs(route, focus, stop))


@pytest.mark.parametrize(
    "priority", (((0, 2), (0, 2)), ((0, 1),), ((2, 0),), ((0, 999),), ((False, 2),), [(0, 2)])
)
def test_focus_cannot_carry_mutable_or_invented_pair_indices(priority: Any) -> None:
    """
    A source-bound prefix remains immutable, nonadjacent and duplicate-free before screening starts.
    """
    source = _route((Straight(2), fold(2, 1.2, 0.8, 0, 0), Straight(3)))
    with pytest.raises(ValueError):
        MaterialFocus(source, priority)


def test_focus_cannot_renew_an_exhausted_shared_support_pool() -> None:
    """
    Prioritizing another material interval does not create another negative-probe support allowance.
    """
    source, offset = _loop_route()
    route, model = _current(source)
    focus = MaterialFocus.from_constraints(
        route, model, model.initial, _guidance(route, model, offset), _checkpoint
    )
    probe = FlatProbe(supports=2048)
    result = screen(route, probe, 32, _checkpoint, lambda _: True, focus=focus)
    assert result.status == "unresolved" and result.pairs_checked == 0 and probe.supports == 2048


@pytest.mark.parametrize("bad", ("count", "identity", "point"))
def test_focused_probe_still_requires_strict_current_witness_and_comparison_contract(
    bad: str,
) -> None:
    """
    An ordering hint cannot legitimize invented work, material identities or occupied coordinates.
    """
    source, offset = _loop_route()
    route, model = _current(source)
    focus = MaterialFocus.from_constraints(
        route, model, model.initial, _guidance(route, model, offset), _checkpoint
    )
    assert focus is not None
    pair = (0, 2) if bad == "identity" else focus.priority[0]
    witness = Penetration(pair, (0.5, 0, 0), (0.5, 0, 0), Vector3(999, 999, 999))
    probe: Any = Mock(
        supports=0, return_value=ProbeResult(99 if bad == "count" else 0, witness=witness)
    )
    with pytest.raises(ArithmeticError):
        screen(route, probe, 32, _checkpoint, lambda _: True, focus=focus)
