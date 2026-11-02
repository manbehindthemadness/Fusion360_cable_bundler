"""
Verify guide turning targets, coupled derivatives and conservative bounded placement.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Callable

import pytest

from cable_bundler.routing.geometry import Vector3, cross, magnitude, unit
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_bend_reduction.closure import affine_projection
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import Pose, Straight, extend, pose_error
from experiments.experiment_ribbon_guide_joints.direction import direction
from experiments.experiment_ribbon_guide_joints.placement import Placement
from experiments.experiment_ribbon_guide_joints.solve import solve
from experiments.experiment_ribbon_joint_route.allocation import Allocation, allocations
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import rotation_choices
from experiments.experiment_ribbon_reduced_joints.kinematics import Joint, moved
from experiments.experiment_ribbon_spline_guide.guide import Guide


def _example(scale: float = 1.0) -> tuple[Joint, Pose, Allocation, Placement]:
    """
    Compose one analytical spatial fixture with a regular four-fold orientation branch.
    """
    start = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))

    def frame(tangent: Vector3, reference: Vector3) -> Pose:
        """
        Construct a perpendicular material frame from analytical directions.
        """
        return Pose(start.origin, unit(tangent), unit(cross(tangent, reference)))

    middle = frame(Vector3(1, 1, 2), Vector3(0, 1, 0))
    end = moved(frame(Vector3(2, -1, 1), Vector3(0, 0, 1)), (1.0, 0.0, 0.0), 0.4)
    folds = (
        rotation_choices(start, middle, scale, 1.2 * scale)[0]
        + rotation_choices(middle, end, scale, 1.2 * scale)[0]
    )
    geometries = []
    for index, fold in enumerate(folds):
        geometries.extend((Straight((2.0 + index) * scale), fold))
    target = extend(start, tuple(geometries + [Straight(6.0 * scale)]))
    boundary = Boundary(
        Targets(
            "analytical placement",
            start.origin,
            target.origin,
            start.tangent,
            target.tangent,
            start.width,
            target.width,
            1,
            scale,
        ),
        scale,
    )
    joint = Joint.capture(boundary, middle, "guide-0-0")
    model = joint.model(middle)
    assert model is not None
    choices = allocations(model, lambda: None, lambda event: None)
    baseline = min(choices, key=lambda a: a.route.material_length_mm)
    placement = Placement.create(baseline.route, Guide.create(boundary.targets))
    assert placement is not None
    return joint, middle, baseline, placement


def test_turning_targets_are_ordered_and_scale_covariant() -> None:
    """
    Derive the same dimensionless placement policy across geometrically scaled layouts.
    """
    _, _, baseline, placement = _example()
    _, _, scaled, large = _example(20)
    assert placement.parameters == tuple(sorted(placement.parameters))
    assert len(placement.targets) == 4
    assert math.fsum(placement.weights) == pytest.approx(1.0)
    assert large.parameters == pytest.approx(placement.parameters)
    assert large.score(scaled.route.pieces) == pytest.approx(placement.score(baseline.route.pieces))
    assert [magnitude(p) for p in large.targets] == pytest.approx(
        [20 * magnitude(p) for p in placement.targets]
    )


def test_placement_derivative_includes_global_closure_response() -> None:
    """
    Compare implicit placement/length slopes with independently reclosed finite probes.
    """
    joint, frame, baseline, placement = _example()
    descent = direction(joint, frame, baseline, placement, lambda: None)
    assert descent is not None and descent.placement_slope < 0
    assert descent.length_slope_mm <= 1e-7
    scores, lengths = [], []
    for sign in (-1, 1):
        model = joint.model(moved(frame, descent.motion, sign * 1e-7))
        assert model is not None
        columns, right = model.equations()
        values = affine_projection(
            [[columns[i][a] for i in baseline.support] for a in range(3)],
            list(right),
            [baseline.values[i] for i in baseline.support],
        )
        assert values is not None and min(values) >= 0
        allocated = [0.0] * model.size
        for i, value in zip(baseline.support, values):
            allocated[i] = value
        pieces = model.pieces(tuple(allocated))
        scores.append(placement.score(pieces))
        lengths.append(math.fsum(p.geometry.material_length_mm for p in pieces))
        for a, b in zip(pieces, pieces[1:]):
            assert max(pose_error(a.end_pose(), b.pose)) < 1e-7
    assert (scores[1] - scores[0]) / 2e-7 == pytest.approx(
        descent.placement_slope, rel=2e-5, abs=1e-7
    )
    assert (lengths[1] - lengths[0]) / 2e-7 == pytest.approx(
        descent.length_slope_mm, rel=2e-5, abs=1e-6
    )


@pytest.mark.parametrize("status", ("penetration", "unresolved", "separated"))
def test_finite_acceptance_never_waives_contact_or_length(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    """
    Preserve physical rejection and non-growth gates under the same finite work ceiling.
    """
    joint, frame, baseline, placement = _example()
    calls: list[int] = []
    events: list[dict[str, Any]] = []

    def contact(*args: Any, maximum_pairs: int, checkpoint: Callable[[], None]) -> ContactResult:
        """
        Isolate acceptance from interval subdivision on the analytical fixture.
        """
        del args
        checkpoint()
        calls.append(maximum_pairs)
        return ContactResult(status, maximum_pairs)

    monkeypatch.setattr("experiments.experiment_ribbon_guide_joints.solve.inspect_contact", contact)
    result = solve(joint, frame, baseline, placement, lambda: None, events.append)
    assert calls and result.contacts == len(calls) <= 4 and all(v == 1024 for v in calls)
    assert result.iterations <= 4
    assert result.allocation.route.material_length_mm <= baseline.route.material_length_mm + 1e-8
    assert cap_error(result.allocation.route) < 1e-7
    if status != "separated":
        assert result.accepted == 0 and result.allocation is baseline
    else:
        assert result.accepted > 0
    for event in events:
        if event.get("status") == "accepted":
            assert status == "separated" and event["placement_score"] < placement.score(
                baseline.route.pieces
            )


def test_stationary_or_straight_guide_is_explicitly_unresolved() -> None:
    """
    Refuse to invent turning targets where an endpoint reference has no heading variation.
    """
    _, _, baseline, _ = _example()
    target = baseline.route.targets
    straight = replace(target, end=Vector3(10, 0, 0), end_tangent=target.start_tangent)
    assert Placement.create(baseline.route, Guide.create(straight)) is None


def test_resource_stop_propagates_before_any_proposal() -> None:
    """
    Preserve the run controller's hard stop instead of returning a successful retained result.
    """
    joint, frame, baseline, placement = _example()

    def stop() -> None:
        """
        Simulate the frozen numerical phase reaching a resource boundary.
        """
        raise TimeoutError("guide-joint unit stop")

    with pytest.raises(TimeoutError, match="guide-joint unit stop"):
        solve(joint, frame, baseline, placement, stop, lambda event: None)
