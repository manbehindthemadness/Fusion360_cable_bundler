"""
Add one deficit-derived material direction while retaining exact steering and cap frames.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Callable

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_feature_insertion.allocation import (
    Allocation,
    closure_allocation,
)
from experiments.experiment_ribbon_feature_insertion.closure_goal import ClosureGoal
from experiments.experiment_ribbon_feature_insertion.continuation import BranchPolicy
from experiments.experiment_ribbon_feature_insertion.features import Chain
from experiments.experiment_ribbon_feature_insertion.reclosure import (
    ReclosureAllocation,
    Unclosed,
    refine,
)
from experiments.experiment_ribbon_feature_insertion.repair import Closure, nearest
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology, rotation_choices

from .adaptive_event_construction import Roots


@dataclass(frozen=True)
class Escape:
    """
    Bind one added fold and its exact compensation choices to the measured source boundary.
    """

    boundary: Boundary
    prefix: CylindricalFold
    windows: tuple[Chain, ...]
    deficit: Vector3
    tangent: Vector3


def plan(boundary: Boundary, source: Unclosed, checkpoint: Callable[[], None]) -> Escape | None:
    """
    Derive a regular bank-zero turn only for a strict measured missing-ray direction.

    Remaining original steering factors stay unchanged. This proposes one
    construction, never proves global infeasibility or the fewest required folds.
    """
    checkpoint()
    chain = source.chain
    if not chain.targets or not chain.group_ends:
        return None
    target = boundary.targets
    deficit = Vector3(*(-v * target.diameter_mm for v in source.closure.residual))
    columns, _ = Model(boundary, chain.topology).straight_equations()
    if any(not math.isfinite(v) for v in (deficit.x, deficit.y, deficit.z)) or not all(
        math.fsum(a * b for a, b in zip(column, (deficit.x, deficit.y, deficit.z))) < 0.0
        for column in columns
    ):
        return None
    projected = deficit.translated(target.start_width, -dot(deficit, target.start_width))
    if magnitude(projected) <= 1e-12:
        return None
    tangent = unit(projected)
    start = Pose(target.start, target.start_tangent, target.start_width)
    angle = math.atan2(dot(tangent, cross(start.tangent, start.width)), dot(tangent, start.tangent))
    if abs(angle) <= 1e-12 or dot(deficit, tangent) <= 0:
        return None
    prefix = fold(boundary.radius_mm, 2 * boundary.half_width_mm, angle, 0.0, 0.0)
    cursor = PlacedPiece(start, prefix, "Measured cone escape").end_pose()
    if magnitude(difference(cursor.tangent, tangent)) > 1e-9:
        raise ArithmeticError("Cone escape lost its measured departure direction")
    first_end = chain.group_ends[0]
    choices = rotation_choices(
        cursor, chain.targets[0], boundary.radius_mm, 2 * boundary.half_width_mm
    )
    windows = []
    for root, compensation in enumerate(choices):
        checkpoint()
        if not compensation:
            continue
        ends = tuple(end - first_end + len(compensation) for end in chain.group_ends)
        windows.append(
            Chain(
                Topology(
                    "cone_escape_" + str(root),
                    compensation + chain.topology.folds[first_end:],
                    None,
                ),
                ends,
                chain.targets,
                chain.feature_count,
                (root, *chain.roots[1:]),
            )
        )
    return Escape(boundary, prefix, tuple(windows), deficit, tangent) if windows else None


def _valid(route: FoldRoute, minimum: float) -> bool:
    """
    Require actual ordered mating, material compatibility and every positive native straight.
    """
    return (
        ordered_mating_caps(route.pieces, route.targets)
        and cap_error(route) <= 1e-7
        and material_error(route) <= 1e-10
        and all(
            piece.geometry.material_length_mm > minimum
            for piece in route.pieces
            if isinstance(piece.geometry, Straight)
        )
    )


def construct(
    escape: Escape,
    minimum_straight_mm: float,
    maximum_straight_mm: float,
    roots: Roots,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> FoldRoute | None:
    """
    Project each exact compensation once, then correct only the closest fixed-prefix window.

    One original construction update owns all choices and at most four actual
    local corrections. Original quality travel, native sizes and physical caps
    stay fixed; no alternate prefix, direction or guide follows a decline.
    """
    boundary = escape.boundary
    pending: list[tuple[Chain, Closure]] = []
    closed: list[FoldRoute] = []
    for window in escape.windows:
        checkpoint()
        if roots.attempted >= 8:
            break
        roots.attempted += 1
        chain = replace(
            window,
            topology=Topology(
                window.topology.identifier, (escape.prefix, *window.topology.folds), None
            ),
            group_ends=tuple(end + 1 for end in window.group_ends),
        )
        closure = nearest(
            Model(boundary, chain.topology),
            checkpoint,
            maximum_straight_mm=maximum_straight_mm,
            minimum_straight_mm=minimum_straight_mm,
        )
        record(
            {
                "stage": "initial_cone_escape",
                "status": "root",
                "roots": chain.roots,
                "position_error_diameters": closure.error,
            }
        )
        if closure.error <= ClosureGoal.MATING.normalized_limit(boundary.targets.diameter_mm):
            allocation = closure_allocation(
                boundary,
                chain,
                closure.values,
                minimum_straight_mm,
                checkpoint,
                record,
                maximum_straight_mm=maximum_straight_mm,
            )
            if allocation is not None and _valid(allocation.route, minimum_straight_mm):
                closed.append(allocation.route)
        pending.append((window, closure))
        roots.declined += 1
    if closed:
        return min(closed, key=lambda route: route.material_length_mm)
    if not pending or roots.newton_steps >= roots.newton_limit:
        return None
    window, closure = min(pending, key=lambda item: (item[1].error, item[0].roots))
    start = Pose(
        boundary.targets.start, boundary.targets.start_tangent, boundary.targets.start_width
    )
    lead = closure.values[0] * boundary.targets.diameter_mm
    prefix: tuple[PlacedPiece, ...] = ()
    if lead > 0:
        if lead <= minimum_straight_mm:
            return None
        straight = PlacedPiece(start, Straight(lead), "Fixed escape runway")
        prefix, start = (straight,), straight.end_pose()
    turn = PlacedPiece(start, escape.prefix, "Fixed cone escape")
    prefix += (turn,)
    pose = turn.end_pose()
    targets = replace(
        boundary.targets, start=pose.origin, start_tangent=pose.tangent, start_width=pose.width
    )
    local = Boundary(targets, boundary.radius_mm)
    values = closure.values[2:]
    delta = difference(Model(local, window.topology).endpoint(values).origin, targets.end)
    residual = tuple(getattr(delta, axis) / targets.diameter_mm for axis in "xyz")
    initial = Unclosed(
        window,
        Closure(values, residual, math.hypot(*residual)),
        branch_policy=BranchPolicy.CONTINUOUS,
        goal=ClosureGoal.MATING,
        allocation_policy=ReclosureAllocation.MEASURED,
    )

    def charged(event: dict[str, Any]) -> None:
        """
        Debit started local corrections before forwarding their original evidence.
        """
        if event.get("stage") == "feature_reclosure_step" and event.get("status") == "started":
            if roots.newton_steps >= roots.newton_limit:
                raise ArithmeticError("Cone escape renewed its local correction allowance")
            roots.newton_steps += 1
        record(event)

    roots.reclosures += 1
    outcome = refine(
        local,
        initial,
        minimum_straight_mm,
        min(4, roots.newton_limit - roots.newton_steps),
        checkpoint,
        charged,
        maximum_straight_mm=maximum_straight_mm - lead,
    )
    if not isinstance(outcome, Allocation):
        return None
    route = FoldRoute(boundary.targets, prefix + outcome.route.pieces, boundary.radius_mm)
    checkpoint()
    if not _valid(route, minimum_straight_mm):
        return None
    record({"stage": "initial_cone_escape", "status": "closed", "route": snapshot(route)})
    return route
