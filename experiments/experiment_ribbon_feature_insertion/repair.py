"""
Reclose fixed-radius feature chains through residual-derived joint-angle corrections.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from itertools import combinations
from typing import Callable

from cable_bundler.routing.geometry import difference
from experiments.experiment_ribbon_bend_reduction.closure import affine_projection
from experiments.experiment_ribbon_fold_route.geometry import Pose
from experiments.experiment_ribbon_fold_route.native_length import minimum_coordinate
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology, rotation_choices
from experiments.experiment_ribbon_reduced_joints.kinematics import moved

from .angular_allocation import bounded_correction
from .closure_goal import ClosureGoal
from .continuation import BranchPolicy, closest
from .features import Chain
from .linear_fit import least_squares
from .native_cone import project as native_projection


class StraightMotion(Enum):
    """
    Choose the straight degrees of freedom eliminated from an angular correction.
    """

    FIXED = "fixed"
    REALLOCATABLE = "reallocatable"


@dataclass(frozen=True)
class Closure:
    """
    Retain the best measured bounded-support endpoint and its actual placement residual.
    """

    values: tuple[float, ...]
    residual: tuple[float, float, float]
    error: float


def nearest(
    model: Model,
    checkpoint: Callable[[], None],
    *,
    maximum_straight_mm: float | None = None,
    minimum_straight_mm: float = 0.0,
) -> Closure:
    """
    Project onto the three-dimensional straight-displacement cone using at most64derived supports.

    Supports of at most three rays suffice in the zero-minimum XYZ cone. This is nearest-endpoint
    accounting, not guessed path initialization or an accepted material route.
    An explicit straight budget projects onto the truncated cone using the same
    supports. A boundary face is solved exactly instead of accepting arbitrarily
    long near-cancelling travel as closure. Fold material is not debited here.
    A positive native minimum restricts each original support to buildable
    positive coordinates; the zero support remains. At most sixteen algebraic
    lower/sum faces replace its unconstrained projection, without adding any
    support or orientation trial. Error still measures actual endpoint distance.
    Positive floors retain the original three-ray representation limit; failure
    does not prove infeasibility of larger native-sized supports or other shapes.
    """
    columns, right = model.equations()
    count = len(model.topology.folds) + 1
    diameter = model.source.targets.diameter_mm
    if not math.isfinite(minimum_straight_mm) or minimum_straight_mm < 0:
        raise ValueError("Use a finite nonnegative native straight minimum")
    minimum = minimum_coordinate(minimum_straight_mm, diameter) if minimum_straight_mm else None
    if minimum_straight_mm and minimum is None:
        raise ValueError("Native straight floor cannot be represented")
    maximum_sum = maximum_straight_mm / diameter if maximum_straight_mm is not None else None
    best: Closure | None = None
    for size in range(4):
        for support in combinations(range(count), size):
            checkpoint()
            rows = [[columns[2 * i][a] for i in support] for a in range(3)]
            values = (
                native_projection(rows, list(right), size, minimum, maximum_sum, checkpoint)
                if minimum is not None
                else least_squares([], [], rows, list(right), size, maximum_sum=maximum_sum)
            )
            if values is None or min(values, default=0) < -1e-9:
                continue
            allocation = [0.0] * model.size
            for i, value in zip(support, values):
                allocation[2 * i] = max(0.0, value)
            if maximum_straight_mm is not None and (
                math.fsum(allocation[::2]) * model.source.targets.diameter_mm
                > maximum_straight_mm + 1e-8 * model.source.targets.diameter_mm
            ):
                continue
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


def reframed(
    boundary: Boundary,
    original: Chain,
    references: tuple[Pose, ...],
    *,
    branch_policy: BranchPolicy = BranchPolicy.INDEX,
) -> Chain | None:
    """
    Recompute exact factors under the selected index or physical-continuation policy.

    Logical roots and group sizes remain fixed. Record any legacy index jump in
    factor rotations so reclosure can consider a continuous alternative explicitly.
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
    begin = 0
    discontinuity = original.factor_discontinuity
    for a, b, root, size in zip(sequence, sequence[1:], original.roots, sizes):
        try:
            choices = rotation_choices(a, b, boundary.radius_mm, boundary.half_width_mm * 2)
        except ValueError:
            return None
        if root >= len(choices) or len(choices[root]) != size:
            return None
        previous = original.topology.folds[begin : begin + size]
        matched = closest(previous, choices)
        selected = matched if branch_policy is BranchPolicy.CONTINUOUS else choices[root]
        if selected is None:
            return None
        discontinuity = discontinuity or (
            branch_policy is BranchPolicy.INDEX and matched is not None and selected is not matched
        )
        groups.append(selected)
        begin += size
    return Chain(
        Topology(original.topology.identifier, tuple(p for group in groups for p in group), None),
        original.group_ends,
        references,
        original.feature_count,
        original.roots,
        discontinuity,
    )


def changed(
    references: tuple[Pose, ...],
    delta: list[float],
    scale: float,
    *,
    goal: ClosureGoal = ClosureGoal.ROUTE,
) -> tuple[Pose, ...]:
    """
    Apply a covariant angular correction at the existing shared sites, never moving their guide targets.
    """
    if not isinstance(goal, ClosureGoal):
        raise ValueError("Select an explicit angular closure goal")
    result = []
    for i, frame in enumerate(references):
        vector = delta[3 * i : 3 * i + 3]
        norm = math.sqrt(math.fsum(v * v for v in vector))
        result.append(
            moved(frame, (vector[0] / norm, vector[1] / norm, vector[2] / norm), scale * norm)
            if norm > goal.minimum_angular_norm
            else frame
        )
    return tuple(result)


def correction(
    boundary: Boundary,
    chain: Chain,
    closure: Closure,
    checkpoint: Callable[[], None],
    *,
    straight_motion: StraightMotion = StraightMotion.FIXED,
    branch_policy: BranchPolicy = BranchPolicy.INDEX,
    maximum_straight_mm: float | None = None,
    minimum_straight_mm: float = 0.0,
    goal: ClosureGoal = ClosureGoal.ROUTE,
) -> list[float] | None:
    """
    Derive a minimum-norm linearized endpoint correction from six probes per shared joint.

    Exact terminal orientation is eliminated algebraically. Straight allocation is
    held for differentiation. Reallocatable mode jointly respects positive slots'
    finite shortening and the original total straight budget when eliminating
    their transfers. Zero slots remain constrained. Actual nonnegative lengths are globally
    re-projected after every finite step. The angular norm is capped at pi/4;
    no trial orientation bank or extra correction step is introduced.
    At most16 algebraic faces replace unbounded span elimination; no extra
    derivative probes or nonlinear correction steps are introduced.
    """
    if not isinstance(goal, ClosureGoal):
        raise ValueError("Select an explicit angular closure goal")
    if not math.isfinite(minimum_straight_mm) or minimum_straight_mm < 0:
        raise ValueError("Use a finite nonnegative native straight minimum")
    minimum = (
        minimum_coordinate(minimum_straight_mm, boundary.targets.diameter_mm)
        if minimum_straight_mm > 0
        else 0.0
    )
    if minimum is None:
        raise ValueError("Native straight floor cannot be represented")
    columns = []
    count = len(chain.targets) * 3
    step = 1e-5
    for axis in range(count):
        delta = [float(i == axis) for i in range(count)]
        positions = []
        for sign in (-1, 1):
            checkpoint()
            probe = reframed(
                boundary,
                chain,
                changed(chain.targets, delta, sign * step),
                branch_policy=branch_policy,
            )
            if probe is None:
                return None
            positions.append(Model(boundary, probe.topology).endpoint(closure.values).origin)
        rate = difference(positions[1], positions[0])
        columns.append(
            tuple(getattr(rate, a) / (2 * step * boundary.targets.diameter_mm) for a in "xyz")
        )
    if straight_motion is StraightMotion.REALLOCATABLE:
        checkpoint()
        rays, _ = Model(boundary, chain.topology).equations()
        active = [i for i in range(0, len(closure.values), 2) if closure.values[i] > 0]
        delta = bounded_correction(
            columns,
            closure.residual,
            tuple(rays[i] for i in active),
            tuple(closure.values[i] for i in active),
            maximum_straight_mm / boundary.targets.diameter_mm
            if maximum_straight_mm is not None
            else None,
            checkpoint,
            minimum_length=minimum,
        )
    else:
        delta = affine_projection(
            [[column[a] for column in columns] for a in range(3)],
            [-v for v in closure.residual],
            [0.0] * count,
        )
    if delta is None:
        return None
    norm = math.sqrt(math.fsum(v * v for v in delta))
    if norm <= goal.minimum_angular_norm:
        return None
    return [v * min(1.0, math.pi / (4 * norm)) for v in delta]
