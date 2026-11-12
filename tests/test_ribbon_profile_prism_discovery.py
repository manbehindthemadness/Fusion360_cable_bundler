"""
Exercise lobe-height discovery and charged valley fallback on authored material geometry.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route import contact_phase_core
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.contact_phase_core import CoreProbe, ProfileProbe
from experiments.experiment_ribbon_fold_route.contact_phase_prism import CorePreparations, PrismKind
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_terminal_hardware.restoration_order import MaterialFocus
from experiments.experiment_ribbon_terminal_hardware.restoration_screen import screen
from tests.test_ribbon_phase_core_discovery import _flat_crossing, _parallel_strips


def _valley_fallback() -> FoldRoute:
    """
    Clip perpendicular strip envelopes near a material end with their width valleys aligned.

    The outer centroid has height .35 in the second strip's empty valley;
    the inner proposal lies below the .3 valley inside both actual profiles.
    """
    source = _parallel_strips(0)
    first = PlacedPiece(
        Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)),
        Straight(4),
        "first authored strip",
    )
    other = PlacedPiece(
        Pose(Vector3(4.2, 0, -2), Vector3(0, 0, 1), Vector3(0, 1, 0)),
        Straight(4),
        "second authored strip",
    )
    return replace(
        source,
        targets=replace(source.targets, lines=2),
        pieces=(first, source.pieces[1], other),
    )


@pytest.mark.parametrize("offset", (0.0, 0.4, 0.8))
def test_profile_prism_finds_core_and_lobe_only_crossings(offset: float) -> None:
    """
    Propose actual material contact across valley and lobe heights without hull supports.
    """
    route = _parallel_strips(offset)
    probe = ProfileProbe()
    result = probe(route, 0, 2, 1, lambda: None)
    assert result.witness is not None and result.pairs_checked == 1
    assert probe.lobe_comparisons == probe.witnesses == 1 and probe.valley_fallbacks == 0
    assert probe.edges == 24 and probe.inverse_tests == 2
    for index in (0, 2):
        assert occupied_coordinates(route.pieces[index], result.witness.point, 1, 1.0) is not None


def test_valley_fallback_is_charged_and_cannot_escape_the_last_comparison() -> None:
    """
    An invalid outer centroid needs a second allocation before testing a valid inner centroid.
    """
    route = _valley_fallback()
    limited = ProfileProbe()
    first = limited(route, 0, 2, 1, lambda: None)
    assert first.witness is None and first.limit == "pairs" and first.pairs_checked == 1
    assert limited.lobe_comparisons == 1 and limited.valley_fallbacks == 0
    assert limited.inverse_tests == 2 and limited.edges == 24
    complete = ProfileProbe()
    result = complete(route, 0, 2, 2, lambda: None)
    witness = result.witness
    assert witness is not None and result.pairs_checked == complete.comparisons == 2
    assert complete.lobe_comparisons == complete.valley_fallbacks == 1
    assert complete.edges == 48 and complete.inverse_tests == 4
    assert 0 < witness.second[2] < 0.3
    assert all(occupied_coordinates(route.pieces[i], witness.point, 2, 1.0) for i in (0, 2))


@pytest.mark.parametrize("offset,comparisons", ((1.0, 2), (2.0, 1)))
def test_tangency_and_empty_envelopes_never_supply_clearance(
    offset: float, comparisons: int
) -> None:
    """
    Empty outer overlap skips only inner proposal work; strict tangency still supplies no witness.
    """
    route = _parallel_strips(offset)
    probe = ProfileProbe()
    result = probe(route, 0, 2, 2, lambda: None)
    assert result.witness is None and result.axis_proposal is None
    assert result.pairs_checked == comparisons and probe.witnesses == 0
    assert (
        screen(
            route,
            FlatProbe(),
            32,
            lambda: None,
            lambda _: True,
            focus=MaterialFocus(route, ((0, 2),)),
            flat_core_probe=probe,
        ).status
        == "unresolved"
    )


@pytest.mark.parametrize("phase", (FlatPhase.BEFORE, FlatPhase.AFTER))
@pytest.mark.parametrize(
    "lines,diameter,side,turn", ((1, 0.25, -1, -1), (3, 1.0, 1, -1), (9, 0.75, -1, 1))
)
def test_banked_phase_discovery_preserves_current_material_identity(
    phase: FlatPhase, lines: int, diameter: float, side: int, turn: int
) -> None:
    """
    Test actual placed banked phases under different scales and signed turns.
    """
    route = _flat_crossing(lines, diameter, side, turn, phase)
    opposite = FlatPhase.AFTER if phase is FlatPhase.BEFORE else FlatPhase.BEFORE
    probe = ProfileProbe()
    result = probe(
        route, 0, 2, 2, lambda: None, excluded_phases=frozenset(((opposite, FlatPhase.STRAIGHT),))
    )
    assert result.witness is not None and result.witness.pieces == (0, 2)
    assert result.pairs_checked in (1, 2)
    assert probe.skipped_phase_pairs <= 1
    assert probe.edges <= result.pairs_checked * 30
    assert all(
        occupied_coordinates(route.pieces[i], result.witness.point, lines, diameter) for i in (0, 2)
    )


def test_both_prism_kinds_share_the_original_bounded_geometry_cache() -> None:
    """
    Shape-kind reuse cannot double the sixty-four-entry memory allowance or cache a witness.
    """
    piece = _parallel_strips(0).pieces[0]
    preparations = CorePreparations()
    for index in range(33):
        moved = replace(piece, pose=replace(piece.pose, origin=Vector3(index, 0, 0)))
        for kind in PrismKind:
            assert preparations(moved, FlatPhase.STRAIGHT, 1, 1.0, kind) is not None
    assert preparations.statistics() == {
        "hits": 0,
        "preparations": 66,
        "retained": 64,
        "capacity": 64,
    }


def test_screen_preserves_root_and_shared_support_limits_for_profile_proposals() -> None:
    """
    Count a root plus two proposals and refuse activation after original support exhaustion.
    """
    route = _valley_fallback()
    probe, hull = ProfileProbe(), FlatProbe()
    focus = MaterialFocus(route, ((0, 2),))
    assert (
        screen(
            route, hull, 2, lambda: None, lambda _: True, focus=focus, flat_core_probe=probe
        ).status
        == "unresolved"
    )
    result = screen(
        route, hull, 3, lambda: None, lambda _: True, focus=focus, flat_core_probe=probe
    )
    assert result.status == "penetration" and result.pairs_checked == 3
    assert "flat-profile prism" in result.reason
    before = probe.comparisons
    hull.supports = 2048
    stopped = screen(
        route, hull, 32, lambda: None, lambda _: True, focus=focus, flat_core_probe=probe
    )
    assert stopped.status == "unresolved" and stopped.pairs_checked == 0
    assert probe.comparisons == before


def test_profile_proposals_require_both_original_inverses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Neither nonempty outer nor inner intersection can bypass failed material containment.
    """
    calls = []

    def reject(piece: PlacedPiece, point: Vector3, lines: int, diameter: float) -> None:
        """
        Reject every candidate at the original physical boundary and record actual calls.
        """
        calls.append((piece, point, lines, diameter))

    monkeypatch.setitem(vars(contact_phase_core), "occupied_coordinates", reject)
    probe = ProfileProbe()
    result = probe(_parallel_strips(0.4), 0, 2, 2, lambda: None)
    assert result.witness is None and result.axis_proposal is None
    assert probe.comparisons == 2 and probe.inverse_tests == len(calls) == 4
    assert probe.witnesses == 0


def test_cancellation_during_fallback_preserves_actual_partial_work() -> None:
    """
    A charged inner proposal cannot swallow a hard resource/source cancellation.
    """
    probe = ProfileProbe()

    def checkpoint() -> None:
        """
        Stop before the first inner edge after its comparison has been charged.
        """
        if probe.valley_fallbacks:
            raise RuntimeError("source changed")

    with pytest.raises(RuntimeError, match="source changed"):
        probe(_valley_fallback(), 0, 2, 2, checkpoint)
    assert probe.comparisons == 2 and probe.valley_fallbacks == 1
    assert probe.edges == 24 and probe.inverse_tests == 2 and probe.witnesses == 0


@pytest.mark.parametrize("probe_type", (CoreProbe, ProfileProbe))
def test_disjoint_proposal_bounds_skip_edges_but_charge_the_comparison(
    probe_type: type[CoreProbe],
) -> None:
    """
    Skip only provably empty proposal work, retaining an unmeasured material result.
    """
    probe = probe_type()
    result = probe(_parallel_strips(2.0), 0, 2, 1, lambda: None)
    assert result.pairs_checked == probe.comparisons == 1
    assert result.witness is None and result.axis_proposal is None
    assert probe.edges == probe.inverse_tests == probe.witnesses == 0


@pytest.mark.parametrize("kind", tuple(PrismKind))
def test_prism_world_bounds_enclose_every_rotated_banked_vertex(kind: PrismKind) -> None:
    """
    Outward world bounds retain all original vertices and shared edge endpoints.
    """
    route = _flat_crossing(9, 0.75, -1, -1, FlatPhase.AFTER)
    prism = CorePreparations()(route.pieces[0], FlatPhase.AFTER, 9, 0.75, kind)
    assert prism is not None
    for edge in prism.edges:
        for point in edge:
            assert all(
                low < coordinate < high for coordinate, (low, high) in zip(point, prism.bounds)
            )
