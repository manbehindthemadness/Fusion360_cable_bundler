"""
Require actual occupied-volume evidence from deterministic inscribed-core intersections.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.contact_core import core_witness
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.straight_witness import straight_witness
from tests.test_fold_contact import X, Y, _route


@pytest.mark.parametrize("width_offset,height_offset", ((0.0, 0.5), (3.0, 0.0), (1.5, 0.4)))
def test_parallel_thickness_overlap_has_a_strict_point_without_midplane_crossing(
    width_offset: float, height_offset: float
) -> None:
    """
    Certify both actual profiles at a shared point even when parallel midplanes cannot intersect.
    """
    first = PlacedPiece(Pose(Vector3(0, 0, 0), X, Y), Straight(10), "first")
    second = PlacedPiece(Pose(Vector3(2, width_offset, height_offset), X, Y), Straight(6), "second")
    route = _route(first, second)
    assert straight_witness(route, 0, 1) is None
    witness = core_witness(route, 0, 1)
    assert witness is not None and witness.pieces == (0, 1)
    for piece, coordinates in zip(route.pieces, (witness.first, witness.second)):
        assert occupied_coordinates(piece, witness.point, 3, 1.5) == coordinates


@pytest.mark.parametrize("height", (1.0, 1.5, 2.0))
def test_empty_core_intersection_does_not_claim_clearance(height: float) -> None:
    """
    Leave thickness-only contacts outside the smaller core to the unchanged full contact checker.
    """
    first = PlacedPiece(Pose(Vector3(0, 0, 0), X, Y), Straight(10), "first")
    second = PlacedPiece(Pose(Vector3(0, 0, height), X, Y), Straight(10), "second")
    route = _route(first, second)
    assert core_witness(route, 0, 1) is None
    if height == 1.0:
        assert inspect_contact(route).status == "penetration"


def test_shared_caps_and_invalid_pair_indices_never_invent_penetration() -> None:
    """
    Reject material-boundary centroids and invalid pair identities.
    """
    first = PlacedPiece(Pose(Vector3(0, 0, 0), X, Y), Straight(5), "first")
    route = _route(first, PlacedPiece(first.end_pose(), Straight(5), "second"))
    assert core_witness(route, 0, 1) is None
    for pair in ((1, 0), (0, 0), (0, 2)):
        with pytest.raises(ValueError, match="distinct ordered"):
            core_witness(route, *pair)


def test_core_witness_is_not_a_fold_intersection_test() -> None:
    """
    Leave unsupported curved pieces to their original contact rules.
    """
    from experiments.experiment_ribbon_fold_route.primitives import fold

    first = PlacedPiece(Pose(Vector3(0, 0, 0), X, Y), fold(1, 4.8, 0.5, 0, 0), "fold")
    route = _route(first, PlacedPiece(first.end_pose(), Straight(5), "straight"))
    assert core_witness(route, 0, 1) is None


def test_skew_core_witness_survives_rigid_translation() -> None:
    """
    Preserve occupied-coordinate evidence for nonparallel boxes after changing the world origin.
    """
    first = PlacedPiece(Pose(Vector3(0, 0, 0), X, Y), Straight(10), "first")
    second = PlacedPiece(Pose(Vector3(5, -4, 0.3), Y, X), Straight(8), "second")
    route = _route(first, second)
    moved = FoldRoute(
        route.targets,
        tuple(
            replace(
                piece,
                pose=replace(
                    piece.pose, origin=piece.pose.origin.translated(Vector3(1, -2, 3), 100)
                ),
            )
            for piece in route.pieces
        ),
        route.radius_mm,
    )
    before, after = core_witness(route, 0, 1), core_witness(moved, 0, 1)
    assert before is not None and after is not None
    assert before.first == pytest.approx(after.first, abs=1e-11)
    assert before.second == pytest.approx(after.second, abs=1e-11)
