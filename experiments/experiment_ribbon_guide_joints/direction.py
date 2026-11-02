"""
Differentiate guide placement through one shared joint and its affine endpoint closure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import Vector3, difference, dot
from experiments.experiment_ribbon_bend_reduction.closure import affine_projection
from experiments.experiment_ribbon_fold_route.geometry import Pose
from experiments.experiment_ribbon_joint_route.allocation import Allocation
from experiments.experiment_ribbon_reduced_joints.kinematics import Joint, moved
from experiments.experiment_ribbon_reduced_joints.sensitivity import costs

from .placement import Placement, centers


@dataclass(frozen=True)
class Direction:
    """
    Carry common placement/length descent at the current affine basis.
    """

    motion: tuple[float, float, float]
    step_radians: float
    placement_slope: float
    length_slope_mm: float


def direction(
    joint: Joint,
    frame: Pose,
    current: Allocation,
    placement: Placement,
    checkpoint: Callable[[], None],
) -> Direction | None:
    """
    Use six fixed derivative probes and implicit linear closure, without route/contact trials.

    Shared joins remain composed by the existing material model. The derivative
    includes every active straight/radius response required by all three endpoint
    position equations. Nonlinear finite-step acceptance is separately mandatory.
    """
    model = joint.model(frame)
    if model is None:
        return None
    columns, _ = model.equations()
    support = current.support
    rows = [[columns[i][a] for i in support] for a in range(3)]
    actual = centers(model.pieces(current.values))
    feature_columns = []
    for index in support:
        checkpoint()
        values = list(current.values)
        values[index] += 1.0
        changed = centers(model.pieces(tuple(values)))
        feature_columns.append(tuple(difference(b, a) for a, b in zip(actual, changed)))
    length_weights = costs(model)
    length_gradient = []
    placement_gradient = []
    allocation_rates = []
    h = 1e-5
    for axis in range(3):
        unit = (float(axis == 0), float(axis == 1), float(axis == 2))
        samples = []
        for sign in (-1, 1):
            checkpoint()
            probe = joint.model(moved(frame, unit, sign * h))
            if probe is None:
                return None
            pieces = probe.pieces(current.values)
            samples.append(
                (
                    centers(pieces),
                    pieces[-1].end_pose().origin,
                    math.fsum(p.geometry.material_length_mm for p in pieces),
                )
            )
        before, after = samples
        endpoint_rate = difference(after[1], before[1])
        diameter = joint.boundary.targets.diameter_mm
        rates = affine_projection(
            rows,
            [-getattr(endpoint_rate, a) / (2 * h * diameter) for a in "xyz"],
            [0.0] * len(support),
        )
        if rates is None:
            return None
        allocation_rates.append(rates)
        length_gradient.append(
            (after[2] - before[2]) / (2 * h)
            + math.fsum(length_weights[i] * rate for i, rate in zip(support, rates))
        )
        slope = 0.0
        for feature, (a, b, point, target, weight) in enumerate(
            zip(before[0], after[0], actual, placement.targets, placement.weights)
        ):
            velocity = Vector3(0, 0, 0).translated(difference(b, a), 1 / (2 * h))
            for column, rate in zip(feature_columns, rates):
                velocity = velocity.translated(column[feature], rate)
            slope += 2 * weight * dot(difference(point, target), velocity) / placement.scale_mm**2
        placement_gradient.append(slope)
    motion = [-g for g in placement_gradient]
    uphill = math.fsum(a * b for a, b in zip(motion, length_gradient))
    length_norm2 = math.fsum(g * g for g in length_gradient)
    if uphill > 0 and length_norm2 > 1e-20:
        placement_norm = math.sqrt(math.fsum(g * g for g in placement_gradient))
        length_norm = math.sqrt(length_norm2)
        # The unit-gradient bisector descends both objectives unless they oppose exactly.
        motion = [
            -a / placement_norm - b / length_norm
            for a, b in zip(placement_gradient, length_gradient)
        ]
    norm = math.sqrt(math.fsum(v * v for v in motion))
    if norm <= 1e-12:
        return None
    normalized = (motion[0] / norm, motion[1] / norm, motion[2] / norm)
    slope = math.fsum(a * b for a, b in zip(normalized, placement_gradient))
    if slope >= -1e-12:
        return None
    rates = [
        math.fsum(normalized[a] * allocation_rates[a][i] for a in range(3))
        for i in range(len(support))
    ]
    step = min(
        [math.pi / 4]
        + [current.values[i] / -rate for i, rate in zip(support, rates) if rate < -1e-12]
    )
    if step <= 1e-12:
        return None
    return Direction(
        normalized,
        step,
        slope,
        math.fsum(a * b for a, b in zip(normalized, length_gradient)),
    )
