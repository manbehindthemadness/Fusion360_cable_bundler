"""
Omit only already represented complete flat phase pairs from negative restoration probes.
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_feature_insertion.separation import Side
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.flat_separation import (
    FlatSeparation,
    ProfileExtent,
)
from experiments.experiment_ribbon_terminal_hardware.material_constraint import MaterialConstraint
from experiments.experiment_ribbon_terminal_hardware.restoration_screen import (
    represented_phases,
    screen,
)
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_restoration_screen import _crossing


def _complete(route: FoldRoute) -> FlatSeparation:
    """
    Derive actual complete phase guidance from an independently authored strict crossing.
    """
    witness = FlatProbe()(route, 0, 6, 32, None).witness
    if witness is None:
        raise AssertionError("Authored crossing must have a strict material witness")
    bound = FlatSeparation.create(
        SignedJoints(route), route, witness, extent=ProfileExtent.COMPLETE
    )
    if bound is None:
        raise AssertionError("Authored straight phases must supply complete guidance")
    return bound


def test_exact_complete_phase_pair_omits_support_work_without_persisting_into_final_probes() -> (
    None
):
    """
    The ordinary next call on the same probe must still see the real crossing and consume real work.
    """
    route = _crossing()
    coverage = represented_phases(route, [(_complete(route), Side.BEFORE)])
    assert coverage == {(0, 6): frozenset({(FlatPhase.STRAIGHT, FlatPhase.STRAIGHT)})}
    probe = FlatProbe()
    missed = probe(route, 0, 6, 32, None, excluded_phases=coverage[(0, 6)])
    assert missed.witness is None and missed.pairs_checked == 0
    assert probe.supports == probe.comparisons == probe.inverse_tests == 0
    assert probe.skipped_phase_pairs == 1
    ordinary = probe(route, 0, 6, 32, None)
    assert ordinary.witness is not None and ordinary.pairs_checked > 0 and probe.supports > 0


@pytest.mark.parametrize("incomplete", ("left", "right", "height", "wider_profile"))
def test_partial_profile_coverage_never_authorizes_a_phase_omission(incomplete: str) -> None:
    """
    Require both complete current width and thickness rather than a witness arc or stale profile.
    """
    route = _crossing()
    bound = _complete(route)
    first, second = bound.parts
    if incomplete == "left":
        first = replace(first, low_q=0.0)
    elif incomplete == "right":
        second = replace(second, high_q=0.0)
    elif incomplete == "height":
        first = replace(first, half_height=route.targets.diameter_mm / 4)
    else:
        route = replace(route, targets=replace(route.targets, lines=3))
    bound = replace(bound, parts=(first, second))
    assert represented_phases(route, [(bound, Side.BEFORE)]) == {}


def test_material_slot_identity_tracks_insertions_and_declines_absent_or_ambiguous_slots() -> None:
    """
    A shifted primitive index cannot move an exclusion onto another material region.
    """
    route = _crossing()
    bound = _complete(route)
    shifted = replace(route, pieces=route.pieces[:2] + route.pieces[3:])
    assert (0, 5) in represented_phases(shifted, [(bound, Side.BEFORE)])
    assert (0, 6) not in represented_phases(shifted, [(bound, Side.BEFORE)])
    absent = replace(route, pieces=route.pieces[1:])
    assert represented_phases(absent, [(bound, Side.BEFORE)]) == {}
    ambiguous = replace(route, pieces=(route.pieces[0], *route.pieces))
    assert represented_phases(ambiguous, [(bound, Side.BEFORE)]) == {}


def test_curved_whole_piece_guidance_grants_no_flat_phase_exclusion() -> None:
    """
    Missing explicit flat coverage is not a certificate to skip all phases of the pair.
    """
    route = _crossing()
    flat = _complete(route)
    curved = Mock(spec=MaterialConstraint, pair=flat.pair, parts=())
    assert represented_phases(route, [(curved, Side.BEFORE)]) == {}


def test_excluding_one_fold_phase_pair_leaves_other_phases_measured() -> None:
    """
    The exclusion names phases rather than suppressing both complete pieces.
    """
    route = _route((fold(2, 1.2, 1, 0.5, 1), Straight(3), fold(2, 1.2, -0.7, 0.3, 1)))
    probe = FlatProbe()
    probe(route, 0, 2, 64, None, excluded_phases=frozenset({(FlatPhase.BEFORE, FlatPhase.AFTER)}))
    assert probe.skipped_phase_pairs == 1
    assert probe.comparisons > 0 and probe.supports > 0


def test_skipped_negative_phases_never_return_a_separation_certificate() -> None:
    """
    A route with represented crossings remains unmeasured by the optional screen.
    """
    route = _crossing()
    coverage = represented_phases(route, [(_complete(route), Side.BEFORE)])
    probe = FlatProbe()
    result = screen(route, probe, 32, lambda: None, lambda witness: False, covered_phases=coverage)
    assert result.status == "unresolved" and result.witness is None
    assert probe.skipped_phase_pairs >= 1 and result.pairs_checked <= 32
    final = inspect_contact(route, maximum_pairs=2048, witness_probe=probe)
    assert final.status == "penetration" and final.witness is not None
