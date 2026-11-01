"""
Verify simultaneous cap closure and guide-derived orientation without translation resets.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Callable

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import Piece, fold
from experiments.experiment_ribbon_joint_route.allocation import Model, allocations
from experiments.experiment_ribbon_joint_route.frames import Topology, middle_frame, topologies
from experiments.experiment_ribbon_joint_route.solve import solve
from experiments.experiment_ribbon_spline_guide.guide import Guide


def _route(geometries: tuple[Piece, ...]) -> FoldRoute:
    """
    Capture analytical target poses independently of archived gym layouts.
    """
    start = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    pose = start
    pieces = []
    for geometry in geometries:
        piece = PlacedPiece(pose, geometry, "analytical")
        pieces.append(piece)
        pose = piece.end_pose()
    target = Targets(
        "analytical joint route",
        start.origin,
        pose.origin,
        start.tangent,
        pose.tangent,
        start.width,
        pose.width,
        1,
        1.0,
    )
    return FoldRoute(target, tuple(pieces), 1.0)


def _checkpoint() -> None:
    """
    Keep small analytical unit checks independent of resource scheduling.
    """


def _record(event: dict[str, Any]) -> None:
    """
    Ignore persistence in checks of other behavior.
    """
    del event


def test_joint_corner_allocates_radius_and_travel_before_construction() -> None:
    """
    Find the known one-corner optimum while preserving complete cap/material identity.
    """
    turn = fold(1, 1.2, math.pi / 2, 0, 0)
    source = _route((Straight(10), turn, Straight(12)))
    model = Model(source, Topology("corner", (turn,), None))
    options = allocations(model, _checkpoint, _record)
    best = min(options, key=lambda item: item.route.material_length_mm)
    assert best.values == pytest.approx((0, 10, 2))
    assert cap_error(best.route) < 1e-10 and material_error(best.route) < 1e-12
    assert (
        best.route.targets == source.targets
        and best.route.material_length_mm < source.material_length_mm
    )


def test_guide_frames_distribute_rotation_and_remain_closed() -> None:
    """
    Make useful rotation progress before arrival rather than resetting to departure.
    """
    source = _route(
        (
            Straight(8),
            fold(1, 1.2, 0.8, 0.3, 0),
            Straight(6),
            fold(1, 1.2, -1.2, -0.2, 0),
            Straight(7),
        )
    )
    guide = Guide.create(source.targets)
    middle = middle_frame(source, guide)
    options = topologies(source, guide)
    assert 1 <= len(options) <= 6
    guided = [t for t in options if t.middle_after is not None]
    assert guided
    for topology in guided:
        model = Model(source, topology)
        pieces = model.pieces((0.0,) * model.size)
        assert topology.middle_after is not None
        actual = pieces[topology.middle_after - 1].end_pose()
        assert magnitude(difference(actual.tangent, middle.tangent)) < 1e-10
        assert magnitude(difference(actual.width, middle.width)) < 1e-10
        end = pieces[-1].end_pose()
        assert magnitude(difference(end.tangent, source.targets.end_tangent)) < 1e-10
        assert magnitude(difference(end.width, source.targets.end_width)) < 1e-10
        assert magnitude(difference(middle.tangent, source.targets.start_tangent)) > 0.1


def test_direct_straight_is_not_replaced_with_folds() -> None:
    """
    Preserve the simplest admissible control with a real contact gate.
    """
    source = _route((Straight(10),))
    result, details = solve(source, Guide.create(source.targets), _checkpoint, _record)
    assert details["selected"] is not None
    assert len(result.pieces) == 1 and isinstance(result.pieces[0].geometry, Straight)
    assert result.material_length_mm == pytest.approx(10)
    assert cap_error(result) < 1e-10


def test_joint_allocation_is_affine_in_radius_and_straight_values() -> None:
    """
    Compare endpoint columns against independent full material recomposition.
    """
    source = _route(
        (
            Straight(5),
            fold(1, 1.2, 0.7, 0.2, 0),
            Straight(5),
            fold(1, 1.2, -0.9, -0.3, 0),
            Straight(8),
        )
    )
    topology = topologies(source, Guide.create(source.targets))[-1]
    model = Model(source, topology)
    columns, _ = model.equations()
    values = tuple((i + 1) / 7 for i in range(model.size))
    expected = model.endpoint((0.0,) * model.size).origin
    for column, value in zip(columns, values):
        expected = expected.translated(Vector3(*column), value * source.targets.diameter_mm)
    assert magnitude(difference(expected, model.endpoint(values).origin)) < 1e-10


@pytest.mark.parametrize("status", ["penetration", "unresolved"])
def test_unaccepted_contact_never_replaces_the_baseline(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """
    Retain failed physical outcomes rather than treating algebraic closure as success.
    """
    source = _route((Straight(10), fold(1, 1.2, math.pi / 2, 0, 0), Straight(12)))

    def contact(route: FoldRoute, *, checkpoint: Callable[[], None]) -> ContactResult:
        """
        Return an explicit unaccepted contact disposition.
        """
        del route, checkpoint
        return ContactResult(status, 1)

    monkeypatch.setattr("experiments.experiment_ribbon_joint_route.solve.inspect_contact", contact)
    result, details = solve(source, Guide.create(source.targets), _checkpoint, _record)
    assert result is source and details["selected"] is None
    assert 1 <= sum(c["status"] == status for c in details["candidates"]) <= 12


def test_resource_stop_propagates_before_candidate_work() -> None:
    """
    Never turn a resource interruption into a retained successful experiment.
    """
    source = _route((Straight(10),))

    def stop() -> None:
        """
        Model the frozen experiment runner's external time/memory gate.
        """
        raise TimeoutError("unit stop")

    with pytest.raises(TimeoutError, match="unit stop"):
        solve(source, Guide.create(source.targets), stop, _record)


def test_intermediate_frame_is_covariant_when_mean_width_degenerates() -> None:
    """
    Resolve opposing cap widths from input frames without introducing world-axis bias.
    """
    source = _route((Straight(10),))
    targets = replace(source.targets, end_width=Vector3(0, -1, 0))
    source = replace(source, targets=targets)
    before = middle_frame(source, Guide.create(targets))

    def rotate(value: Vector3) -> Vector3:
        """
        Apply a rigid quarter turn with no reference to the planner's entry axes.
        """
        return Vector3(-value.y, value.x, value.z)

    shift = Vector3(3, -7, 2)
    moved = replace(
        targets,
        start=rotate(targets.start).translated(shift, 1),
        end=rotate(targets.end).translated(shift, 1),
        start_tangent=rotate(targets.start_tangent),
        end_tangent=rotate(targets.end_tangent),
        start_width=rotate(targets.start_width),
        end_width=rotate(targets.end_width),
    )
    after = middle_frame(replace(source, targets=moved), Guide.create(moved))
    assert magnitude(difference(after.origin, rotate(before.origin).translated(shift, 1))) < 1e-10
    assert magnitude(difference(after.tangent, rotate(before.tangent))) < 1e-10
    assert magnitude(difference(after.width, rotate(before.width))) < 1e-10
