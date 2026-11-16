"""
Construct branch centerline candidates directly from fixed ordered target poses.

This deterministic initializer supplies the existing complete-input adapter;
it does not certify material compatibility, curvature, contact, ending allowance
or native construction. Those gates must evaluate the resulting geometry.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from cable_bundler.application.cable_group_routes import CableGroupControlStep, CableGroupRouteLeg
from cable_bundler.domain import HarnessDefinition
from cable_bundler.routing import RoutePreview
from cable_bundler.routing.geometry import CubicBezier, Vector3, difference, magnitude
from devtools.ribbon_analysis.contracts import Targets

from .capture import FRAME_IDENTITY, branch_geometry, capture, finite, target
from .contracts import (
    CapPort,
    CompleteRibbonInput,
    FixedTarget,
    IncompleteRibbonInput,
    ResolvedBranch,
)


class UnresolvedBranchConstruction(ValueError):
    """
    Retain an unsupported initializer outcome without claiming input infeasibility.
    """


@dataclass(frozen=True)
class BranchControlPose:
    """
    Bind an original directed control step to its explicitly resolved branch pose.

    The tangent follows increasing branch traversal, including the saved step's
    reversal. Resolving that pose from a gate or attachment is a caller boundary;
    this constructor never chooses a crossing or infers missing control geometry.
    """

    step: CableGroupControlStep
    pose: FixedTarget


@dataclass(frozen=True)
class BranchTargets:
    """
    Freeze terminal-to-parent/cap boundary data without requiring a solved route.

    Every declared control must have one pose in the same explicit order. Route
    identities, control directions and endpoint identities remain unchanged.
    """

    leg: CableGroupRouteLeg
    terminal: FixedTarget
    arrival: FixedTarget
    controls: tuple[BranchControlPose, ...] = ()


def initialize(source: BranchTargets, checkpoint: Callable[[], None]) -> ResolvedBranch:
    """
    Construct one cubic per fixed pose interval with chord/3 tangent handles.

    No search, retry, geometric repair or internal work allocation occurs. The
    caller's checkpoint covers validation and construction across all branches.
    Cubics preserve endpoint position and tangent direction, including ordered
    controls; their speeds and second derivatives can differ at joins. They are
    candidates for downstream physical checks, never preaccepted branch plans.
    Coincident poses and unrepresentable handles remain unresolved rather than
    receiving a fabricated loop or being classified as impossible boundary data.
    """
    checkpoint()
    if tuple(control.step for control in source.controls) != source.leg.control_steps:
        raise IncompleteRibbonInput("Every ordered branch control needs its original directed pose")
    if any(control.pose.target_id != control.step.control_id for control in source.controls):
        raise IncompleteRibbonInput("A branch control pose must retain its control identity")
    poses = (
        (source.terminal,) + tuple(control.pose for control in source.controls) + (source.arrival,)
    )
    for pose in poses:
        checkpoint()
        target(pose)
    curves = []
    for first, following in zip(poses, poses[1:]):
        checkpoint()
        chord = magnitude(difference(following.point, first.point))
        if not math.isfinite(chord) or chord <= 0:
            raise UnresolvedBranchConstruction("Distinct finite branch pose positions required")
        curve = CubicBezier(
            first.point,
            first.point.translated(first.tangent, chord / 3),
            following.point.translated(following.tangent, -chord / 3),
            following.point,
        )
        if not finite(curve.control_a) or not finite(curve.control_b):
            raise UnresolvedBranchConstruction("Branch endpoint handles cannot be represented")
        for parameter, pose in ((0, first), (1, following)):
            velocity = curve.derivative(parameter)
            speed = magnitude(velocity)
            # The existing route validator requires usable, consistent coordinate directions.
            if not math.isfinite(speed) or speed <= 1e-12:
                raise UnresolvedBranchConstruction("Branch endpoint handles cannot be represented")
            direction = Vector3(velocity.x / speed, velocity.y / speed, velocity.z / speed)
            if magnitude(difference(direction, pose.tangent)) > FRAME_IDENTITY:
                raise UnresolvedBranchConstruction(
                    "Branch endpoint direction cannot be represented"
                )
        curves.append(curve)
    route = RoutePreview(
        source.leg.route_id, source.leg.label, tuple(pose.point for pose in poses), tuple(curves)
    )
    result = ResolvedBranch(source.leg, route, source.terminal, source.arrival)
    branch_geometry(result)
    checkpoint()
    return result


def capture_targets(
    definition: HarnessDefinition,
    group_id: UUID,
    trunk: Targets,
    caps: tuple[CapPort, ...],
    branches: tuple[BranchTargets, ...],
    checkpoint: Callable[[], None],
) -> CompleteRibbonInput:
    """
    Construct and capture all ending candidates from fixed targets under one caller guard.

    The existing capture validates both ends, complete descendant coverage,
    root conductor identity, associations and cap correspondence. No supplied
    route, cached answer, per-branch recovery budget or native operation is used.
    The result remains a candidate input to branch/material/native validation.
    """
    checkpoint()
    resolved = tuple(initialize(branch, checkpoint) for branch in branches)
    result = capture(definition, group_id, trunk, caps, resolved)
    checkpoint()
    return result
