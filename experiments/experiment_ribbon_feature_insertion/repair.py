"""
Reclose fixed-radius feature chains through residual-derived joint-angle corrections.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations
from typing import Callable

from cable_bundler.routing.geometry import difference
from experiments.experiment_ribbon_bend_reduction.closure import affine_projection
from experiments.experiment_ribbon_fold_route.geometry import Pose
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology, rotation_choices
from experiments.experiment_ribbon_reduced_joints.kinematics import moved

from .features import Chain
from .linear_fit import least_squares


@dataclass(frozen=True)
class Closure:
    """
    Retain the nearest nonnegative straight-cone endpoint and its actual placement residual.
    """

    values: tuple[float, ...]
    residual: tuple[float, float, float]
    error: float


def nearest(model: Model, checkpoint: Callable[[], None]) -> Closure:
    """
    Project onto the three-dimensional straight-displacement cone using at most64derived supports.

    Supports of at most three rays suffice in XYZ. This is convex nearest-endpoint
    accounting, not guessed path initialization or an accepted material route.
    """
    columns, right = model.equations()
    count = len(model.topology.folds) + 1
    best: Closure | None = None
    for size in range(4):
        for support in combinations(range(count), size):
            checkpoint()
            rows = [[columns[2 * i][a] for i in support] for a in range(3)]
            values = least_squares([], [], rows, list(right), size)
            if values is None or min(values, default=0) < -1e-9:
                continue
            allocation = [0.0] * model.size
            for i, value in zip(support, values):
                allocation[2 * i] = max(0.0, value)
            delta = difference(model.endpoint(tuple(allocation)).origin, model.source.targets.end)
            diameter = model.source.targets.diameter_mm
            residual = (delta.x / diameter, delta.y / diameter, delta.z / diameter)
            error = math.sqrt(math.fsum(v * v for v in residual))
            current = Closure(tuple(allocation), residual, error)
            if best is None or (error, math.fsum(allocation)) < (
                best.error,
                math.fsum(best.values),
            ):
                best = current
    if best is None:
        raise ArithmeticError("The zero-travel displacement-cone projection must exist")
    return best


def reframed(boundary: Boundary, original: Chain, references: tuple[Pose, ...]) -> Chain | None:
    """
    Preserve the same exact root indices/group sizes while shared guide joint orientations change.
    """
    target = boundary.targets
    sequence = (
        Pose(target.start, target.start_tangent, target.start_width),
        *references,
        Pose(target.end, target.end_tangent, target.end_width),
    )
    sizes = tuple(
        b - a
        for a, b in zip(
            (0, *original.group_ends), (*original.group_ends, len(original.topology.folds))
        )
    )
    groups = []
    for a, b, root, size in zip(sequence, sequence[1:], original.roots, sizes):
        try:
            choices = rotation_choices(a, b, boundary.radius_mm, boundary.half_width_mm * 2)
        except ValueError:
            return None
        if root >= len(choices) or len(choices[root]) != size:
            return None
        groups.append(choices[root])
    return Chain(
        Topology(original.topology.identifier, tuple(p for group in groups for p in group), None),
        original.group_ends,
        references,
        original.feature_count,
        original.roots,
    )


def changed(references: tuple[Pose, ...], delta: list[float], scale: float) -> tuple[Pose, ...]:
    """
    Apply a covariant angular correction at the existing shared sites, never moving their guide targets.
    """
    result = []
    for i, frame in enumerate(references):
        vector = delta[3 * i : 3 * i + 3]
        norm = math.sqrt(math.fsum(v * v for v in vector))
        result.append(
            moved(frame, (vector[0] / norm, vector[1] / norm, vector[2] / norm), scale * norm)
            if norm > 1e-12
            else frame
        )
    return tuple(result)


def correction(
    boundary: Boundary,
    chain: Chain,
    closure: Closure,
    checkpoint: Callable[[], None],
) -> list[float] | None:
    """
    Derive a minimum-norm linearized endpoint correction from six probes per shared joint.

    Exact terminal orientation is eliminated algebraically. Straight allocation is
    held for differentiation, then re-projected globally after every finite step.
    The angular norm is capped at pi/4; no trial orientation bank is introduced.
    """
    columns = []
    count = len(chain.targets) * 3
    step = 1e-5
    for axis in range(count):
        delta = [float(i == axis) for i in range(count)]
        positions = []
        for sign in (-1, 1):
            checkpoint()
            probe = reframed(boundary, chain, changed(chain.targets, delta, sign * step))
            if probe is None:
                return None
            positions.append(Model(boundary, probe.topology).endpoint(closure.values).origin)
        rate = difference(positions[1], positions[0])
        columns.append(
            tuple(getattr(rate, a) / (2 * step * boundary.targets.diameter_mm) for a in "xyz")
        )
    delta = affine_projection(
        [[column[a] for column in columns] for a in range(3)],
        [-v for v in closure.residual],
        [0.0] * count,
    )
    if delta is None:
        return None
    norm = math.sqrt(math.fsum(v * v for v in delta))
    if norm <= 1e-12:
        return None
    return [v * min(1.0, math.pi / (4 * norm)) for v in delta]
