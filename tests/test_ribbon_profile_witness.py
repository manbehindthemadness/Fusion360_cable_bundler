"""
Check negative-only profile refinement on analytical volumes, without saved ribbon layouts.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight


def _crossed_strips(scale: float, gap: float = 0.9) -> FoldRoute:
    """
    Place two perpendicular lobed volumes with known shared lobe interiors and empty valleys.

    These disconnected analytical volumes test the detector, not endpoint solving
    or independent complete-ribbon coverage. Gap is measured in conductor diameters.
    """
    first = Pose(Vector3(-5 * scale, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    second = Pose(Vector3(0, -5 * scale, gap * scale), Vector3(0, 1, 0), Vector3(1, 0, 0))
    targets = Targets(
        "analytical crossing lobes",
        first.origin,
        Vector3(0, 5 * scale, gap * scale),
        first.tangent,
        second.tangent,
        first.width,
        second.width,
        2,
        scale,
    )
    return FoldRoute(
        targets,
        (
            PlacedPiece(first, Straight(10 * scale), "first volume"),
            PlacedPiece(second, Straight(10 * scale), "second volume"),
        ),
        scale,
    )


@pytest.mark.parametrize("scale", (0.1, 1.0, 20.0))
def test_lobe_refinement_finds_actual_overlap_after_hull_point_misses(scale: float) -> None:
    """
    Derive a strict occupied point even when a whole-profile convex proposal lies in empty material.
    """
    route = _crossed_strips(scale)
    known = Vector3(-0.5 * scale, -0.5 * scale, 0.45 * scale)
    assert all(occupied_coordinates(p, known, 2, scale) is not None for p in route.pieces)
    probe = FlatProbe()
    result = probe(route, 0, 1, 128, None)
    assert result.witness is not None
    assert 1 < result.pairs_checked <= 128 and probe.supports <= 2048
    assert all(
        occupied_coordinates(p, result.witness.point, 2, scale) is not None for p in route.pieces
    )
    complete = inspect_contact(route, maximum_pairs=128, witness_probe=FlatProbe())
    assert complete.status == "penetration" and complete.witness is not None
    assert complete.pairs_checked <= 128


@pytest.mark.parametrize("gap", (1.0, 1.1))
def test_tangent_or_separated_lobes_never_supply_a_penetration(gap: float) -> None:
    """
    A convex proposal never turns tangency or empty material into a strict witness.
    """
    result = FlatProbe()(_crossed_strips(1.0, gap), 0, 1, 128, None)
    assert result.witness is None


def test_profile_refinement_shares_the_original_pair_allowance() -> None:
    """
    A missed hull proposal consumes its comparison; refinement cannot renew that work.
    """
    result = FlatProbe()(_crossed_strips(1.0), 0, 1, 1, None)
    assert result.witness is None and result.pairs_checked == 1 and result.limit == "pairs"


def test_overlapping_hulls_above_empty_valleys_never_supply_false_evidence() -> None:
    """
    Restrict the longitudinal overlap to empty profile valleys despite intersecting phase hulls.
    """
    source = _crossed_strips(1.0)
    pieces = (
        replace(
            source.pieces[0],
            pose=replace(source.pieces[0].pose, origin=Vector3(-0.05, 0, 0)),
            geometry=Straight(0.1),
        ),
        replace(
            source.pieces[1],
            pose=replace(source.pieces[1].pose, origin=Vector3(0, -0.05, 0.9)),
            geometry=Straight(0.1),
        ),
    )
    probe = FlatProbe()
    result = probe(replace(source, pieces=pieces), 0, 1, 128, None)
    assert result.witness is None and result.limit is None
    assert 1 < result.pairs_checked <= 128 and probe.supports <= 2048


def test_cancellation_after_unoccupied_hull_point_propagates() -> None:
    """
    Preserve hard cancellation before constituent work instead of silently disabling the accelerator.
    """
    probe = FlatProbe()

    def checkpoint() -> None:
        """
        Simulate a source stop after the first actual-volume rejection.
        """
        if probe.inverse_tests:
            raise RuntimeError("profile source stop")

    with pytest.raises(RuntimeError, match="profile source stop"):
        probe(_crossed_strips(1.0), 0, 1, 128, checkpoint)
