"""
Verify full-profile terminal collision evidence without treating analytical primitives as solved routes.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware.check import inspect
from experiments.experiment_ribbon_terminal_hardware.model import Box, Dimensions, Hardware


def _primitives(pieces: tuple[PlacedPiece, ...]) -> FoldRoute:
    """
    Bind endpoint boxes to independent primitive fixtures; no connected-route feasibility is asserted.
    """
    start, end = pieces[0].pose, pieces[-1].end_pose()
    target = Targets(
        "hardware analytical",
        start.origin,
        end.origin,
        start.tangent,
        end.tangent,
        start.width,
        end.width,
        2,
        1.0,
    )
    return FoldRoute(target, pieces, 0.6)


def _straight(x: float, y: float, z: float, length: float) -> PlacedPiece:
    """
    Place one rigid analytical strip with a known positive material direction.
    """
    return PlacedPiece(
        Pose(Vector3(x, y, z), Vector3(1, 0, 0), Vector3(0, 1, 0)), Straight(length), "test"
    )


def test_straight_approach_keeps_both_intended_mating_faces() -> None:
    """
    Correctly arriving full-width profiles can touch their own connector face without entering hardware.
    """
    route = _primitives((_straight(0, 0, 0, 10),))
    hardware = Hardware.create(route.targets, Dimensions.scaled(route.targets))
    report = inspect(route, hardware)
    assert report.status == "clear" and report.cells_checked == 2
    assert hardware.boxes[0].bounds[0].high == hardware.boxes[1].bounds[0].high == 0
    assert hardware.boxes[0].pose.tangent.x == 1 and hardware.boxes[1].pose.tangent.x == -1


def test_returning_run_enters_start_hardware_even_after_legal_first_fold() -> None:
    """
    A shared mating cap never exempts the later backward return from full material checks.
    """
    pose = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    turn = PlacedPiece(pose, fold(0.6, 2.2, math.pi, 0, 0), "turn")
    back = PlacedPiece(turn.end_pose(), Straight(2), "return")
    route = _primitives((turn, back))
    report = inspect(route, Hardware.create(route.targets, Dimensions.scaled(route.targets)))
    assert report.status == "blocked" and report.witness is not None
    assert report.witness.terminal == "start" and report.witness.piece == 1


def test_edge_material_intrusion_is_detected_with_centerline_outside_proxy() -> None:
    """
    Independently placed strips isolate side-lobe contact that a centerline-only check would miss.
    """
    route = _primitives((_straight(0, 0, 0, 10), _straight(4, 1.2, 0, 1)))
    hardware = Hardware.create(route.targets, Dimensions(1, 2, 2))
    report = inspect(route, hardware)
    assert report.status == "blocked" and report.witness is not None
    witness = report.witness
    assert witness.terminal == "end" and witness.piece == 0
    assert 0.7 < witness.point.y < 1.1
    assert witness.point.y != 0


def test_finite_proxy_does_not_become_an_infinite_terminal_halfspace() -> None:
    """
    A remote primitive behind the terminal plane stays clear when outside finite proxy depth.
    """
    route = _primitives((_straight(0, 0, 0, 1), _straight(-10, 0, 0, 1)))
    report = inspect(route, Hardware.create(route.targets, Dimensions(3, 3, 2)))
    assert report.status == "clear"


def test_exhaustion_never_becomes_clearance() -> None:
    """
    An incomplete traversal stays explicitly unresolved even for a simple eligible route.
    """
    route = _primitives((_straight(0, 0, 0, 10),))
    report = inspect(route, Hardware.create(route.targets, Dimensions(3, 3, 2)), maximum_cells=1)
    assert report.status == "unresolved" and report.cells_checked == 1


def test_intrusion_evidence_is_invariant_under_a_rigid_frame_change() -> None:
    """
    A rotated and translated complete input retains the same material collision and local coordinates.
    """
    route = _primitives((_straight(0, 0, 0, 10), _straight(4, 1.2, 0, 1)))

    def rotate(vector: Vector3) -> Vector3:
        """
        Cycle coordinates with a proper orthogonal rotation.
        """
        return Vector3(vector.z, vector.x, vector.y)

    def point(vector: Vector3) -> Vector3:
        """
        Apply the same rigid translation after rotating all positions.
        """
        return rotate(vector).translated(Vector3(1, -2, 3), 11)

    target = route.targets
    moved = replace(
        route,
        targets=replace(
            target,
            start=point(target.start),
            end=point(target.end),
            start_tangent=rotate(target.start_tangent),
            end_tangent=rotate(target.end_tangent),
            start_width=rotate(target.start_width),
            end_width=rotate(target.end_width),
        ),
        pieces=tuple(
            replace(
                p, pose=Pose(point(p.pose.origin), rotate(p.pose.tangent), rotate(p.pose.width))
            )
            for p in route.pieces
        ),
    )
    original = inspect(route, Hardware.create(target, Dimensions(1, 2, 2)))
    transformed = inspect(moved, Hardware.create(moved.targets, Dimensions(1, 2, 2)))
    assert original.status == transformed.status == "blocked"
    a, b = original.witness, transformed.witness
    assert a is not None and b is not None
    assert (a.terminal, a.piece, a.material) == (b.terminal, b.piece, b.material)
    assert b.box_coordinates == pytest.approx(a.box_coordinates, abs=1e-12)
    assert b.point == point(a.point)


def test_displaced_mating_plane_cannot_claim_the_intended_cap_exemption() -> None:
    """
    Arbitrary proxy motion is rejected before local cap support can exempt any material.
    """
    route = _primitives((_straight(0, 0, 0, 10),))
    hardware = Hardware.create(route.targets, Dimensions(3, 3, 2))
    start = hardware.boxes[0]
    moved = Box(start.terminal, replace(start.pose, origin=Vector3(1, 0, 0)), start.dimensions)
    with pytest.raises(ValueError, match="fixed target poses"):
        Hardware(route.targets, (moved, hardware.boxes[1]))


@pytest.mark.parametrize("value", (True, 0, -1, float("nan"), float("inf")))
def test_invalid_dimensions_are_rejected_before_geometry_work(value: float) -> None:
    """
    Malformed physical dimensions cannot silently change the meaning of a keep-out volume.
    """
    with pytest.raises(ValueError):
        Dimensions(value, 1, 1)
