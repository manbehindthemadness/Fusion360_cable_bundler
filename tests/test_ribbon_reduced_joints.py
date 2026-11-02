"""
Verify reduced-joint orientation closure, derived descent and conservative bounded acceptance.
"""

from __future__ import annotations

import math
from typing import Any, Callable

import pytest

from cable_bundler.routing.geometry import Vector3, cross, unit
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import Pose, Straight, extend
from experiments.experiment_ribbon_joint_route.allocation import Allocation, allocations
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import rotation_choices
from experiments.experiment_ribbon_reduced_joints.kinematics import Joint, moved
from experiments.experiment_ribbon_reduced_joints.sensitivity import direction
from experiments.experiment_ribbon_reduced_joints.solve import solve
from experiments.experiment_ribbon_spline_guide.guide import Guide


def _example() -> tuple[Joint, Pose, Allocation]:
    """
    Derive a spatial four-fold analytical fixture without archived routes or random guesses.
    """
    origin = Vector3(0, 0, 0)
    start = Pose(origin, Vector3(1, 0, 0), Vector3(0, 1, 0))
    tangent = unit(Vector3(1, 1, 2))
    middle = Pose(origin, tangent, unit(cross(tangent, Vector3(0, 1, 0))))
    tangent = unit(Vector3(2, -1, 1))
    end = Pose(origin, tangent, unit(cross(tangent, Vector3(0, 0, 1))))
    end = moved(end, (1.0, 0.0, 0.0), 0.4)
    first = rotation_choices(start, middle, 1.0, 1.2)[0]
    last = rotation_choices(middle, end, 1.0, 1.2)[0]
    geometries = []
    for index, fold in enumerate(first + last):
        geometries.extend((Straight(2.0 + index), fold))
    geometries.append(Straight(6.0))
    target = extend(start, tuple(geometries))
    boundary = Boundary(
        Targets(
            "analytical joint",
            origin,
            target.origin,
            start.tangent,
            target.tangent,
            start.width,
            target.width,
            1,
            1.0,
        ),
        1.0,
    )
    joint = Joint.capture(boundary, middle, "guide-0-0")
    model = joint.model(middle)
    assert model is not None
    choices = allocations(model, lambda: None, lambda event: None)
    return joint, middle, min(choices, key=lambda a: a.route.material_length_mm)


def test_joint_recloses_both_terminal_frames_after_internal_motion() -> None:
    """
    Preserve exact ordered cap frames and material compatibility as an internal frame rotates.
    """
    joint, frame, baseline = _example()
    shifted = moved(frame, (1.0, 0.0, 0.0), 0.03)
    model = joint.model(shifted)
    assert model is not None
    choices = allocations(model, lambda: None, lambda event: None)
    assert choices
    assert all(cap_error(a.route) < 1e-7 and material_error(a.route) < 1e-10 for a in choices)
    assert all(a.route.targets == baseline.route.targets for a in choices)
    descent = direction(joint, frame, baseline, lambda: None)
    assert descent is not None
    assert descent.slope_mm_per_rad < 0 < descent.step_radians <= math.pi / 4


@pytest.mark.parametrize("status", ("unresolved", "penetration", "separated"))
def test_contact_outcomes_never_waive_rules_or_exceed_work(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """
    Accept shorter closed updates only with a passing full-profile contact boundary.
    """
    joint, frame, baseline = _example()
    calls: list[int] = []

    def contact(*args: Any, maximum_pairs: int, checkpoint: Callable[[], None]) -> ContactResult:
        """
        Isolate bounded acceptance from native/interval work on the analytical fixture.
        """
        del args
        checkpoint()
        calls.append(maximum_pairs)
        return ContactResult(status, maximum_pairs)

    monkeypatch.setattr(
        "experiments.experiment_ribbon_reduced_joints.solve.inspect_contact", contact
    )
    result = solve(
        joint,
        frame,
        baseline,
        Guide.create(baseline.route.targets),
        lambda: None,
        lambda event: None,
    )
    assert calls and result.contacts == len(calls) <= 4 and all(value == 1024 for value in calls)
    assert result.iterations <= 4
    if status == "separated":
        assert (
            result.accepted > 0
            and result.allocation.route.material_length_mm < baseline.route.material_length_mm
        )
        assert (
            cap_error(result.allocation.route) < 1e-7
            and material_error(result.allocation.route) < 1e-10
        )
    else:
        assert result.allocation is baseline and result.accepted == 0


def test_branch_changes_and_external_resource_stops_remain_explicit() -> None:
    """
    Never silently switch algebraic roots or absorb a run controller's resource interruption.
    """
    joint, frame, baseline = _example()
    target = joint.boundary.targets
    assert joint.model(Pose(frame.origin, target.start_tangent, target.start_width)) is None

    def stop() -> None:
        """
        Model a cooperative source/time/memory stop without another proposal.
        """
        raise TimeoutError("unit resource stop")

    with pytest.raises(TimeoutError, match="unit resource stop"):
        solve(joint, frame, baseline, Guide.create(target), stop, lambda event: None)
