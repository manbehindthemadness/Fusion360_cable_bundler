"""
Derive a reduced joint descent direction and its first nonnegative-allocation bound.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import difference
from experiments.experiment_ribbon_bend_reduction.closure import affine_projection
from experiments.experiment_ribbon_fold_route.geometry import Pose
from experiments.experiment_ribbon_joint_route.allocation import Allocation, Model

from .kinematics import Joint, moved


@dataclass(frozen=True)
class Descent:
    """
    Carry a derived unit joint motion, negative length slope and bounded initial step.
    """

    direction: tuple[float, float, float]
    slope_mm_per_rad: float
    step_radians: float


def costs(model: Model) -> list[float]:
    """
    Differentiate material length with respect to diameter-normalized affine coordinates.
    """
    diameter = model.source.targets.diameter_mm
    return [
        diameter
        if i % 2 == 0
        else diameter
        * abs(model.topology.folds[i // 2].angle_radians)
        / math.cos(model.topology.folds[i // 2].bank_radians)
        for i in range(model.size)
    ]


def direction(
    joint: Joint, frame: Pose, current: Allocation, checkpoint: Callable[[], None]
) -> Descent | None:
    """
    Differentiate exact rotation factorization and certify the current LP dual before descent.

    Six1e-5radian precision probes evaluate derivatives, never candidate routes.
    The initial move is limited by the first active allocation reaching zero and
    the existing pi/4angular trust scale. Exact reclosure/contact acceptance remains
    mandatory; this derivative cannot certify a finite movement by itself.
    """
    model = joint.model(frame)
    if model is None:
        return None
    columns, _ = model.equations()
    support = current.support
    weights = costs(model)
    dual = affine_projection(
        [list(columns[i]) for i in support], [weights[i] for i in support], [0.0] * 3
    )
    if dual is None or any(
        cost - math.fsum(a * b for a, b in zip(column, dual))
        < -1e-8 * joint.boundary.targets.diameter_mm
        for cost, column in zip(weights, columns)
    ):
        return None
    derivatives = []
    gradient = []
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
            delta = difference(pieces[-1].end_pose().origin, joint.boundary.targets.end)
            samples.append(
                (
                    math.fsum(p.geometry.material_length_mm for p in pieces),
                    tuple(getattr(delta, a) / joint.boundary.targets.diameter_mm for a in "xyz"),
                )
            )
        before, after = samples
        residual = tuple((b - a) / (2 * h) for a, b in zip(before[1], after[1]))
        derivatives.append(residual)
        gradient.append(
            (after[0] - before[0]) / (2 * h) - math.fsum(a * b for a, b in zip(dual, residual))
        )
    norm = math.sqrt(math.fsum(g * g for g in gradient))
    if norm <= 1e-10 * joint.boundary.targets.diameter_mm:
        return None
    motion = (-gradient[0] / norm, -gradient[1] / norm, -gradient[2] / norm)
    right = [-math.fsum(motion[i] * derivatives[i][a] for i in range(3)) for a in range(3)]
    rates = affine_projection(
        [[columns[i][a] for i in support] for a in range(3)], right, [0.0] * len(support)
    )
    if rates is None:
        return None
    step = min(
        [math.pi / 4]
        + [current.values[i] / -rate for i, rate in zip(support, rates) if rate < -1e-12]
    )
    return Descent(motion, -norm, step) if step > 1e-12 else None
