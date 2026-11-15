"""
Refine one witnessed signed half-turn boundary before restoring the actual external caps.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_relocation.model import MovableBends, retract_active
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_feature_insertion.reclosure import Unclosed
from experiments.experiment_ribbon_fold_relaxation.closure_policy import ClosurePolicy
from experiments.experiment_ribbon_fold_route.geometry import (
    FoldRoute,
    PlacedPiece,
    Pose,
    Straight,
    pose_error,
)
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary

from .adaptive_event_construction import Roots


def split(route: FoldRoute, selected: int) -> FoldRoute:
    """
    Replace one ordered bend by two same-axis half turns, preserving radius and orientation.

    Required planar fold leads remain on both new pieces, so positional closure
    does not transfer. The new material must be reclosed and independently checked.
    This operation has no parent event-count limit and selects no alternate bend.
    """
    folds = tuple(piece for piece in route.pieces if isinstance(piece.geometry, CylindricalFold))
    if type(selected) is not int or not 0 <= selected < len(folds):
        raise ValueError("Refine one existing ordered material fold")
    pose = Pose(route.targets.start, route.targets.start_tangent, route.targets.start_width)
    pieces = []
    ordinal = 0
    for original in route.pieces:
        geometry = original.geometry
        geometries = (geometry,)
        if isinstance(geometry, CylindricalFold):
            if ordinal == selected:
                half = replace(geometry, angle_radians=geometry.angle_radians / 2)
                geometries = (half, half)
            ordinal += 1
        for member in geometries:
            piece = PlacedPiece(pose, member, "Evidence-directed refined material")
            pieces.append(piece)
            pose = piece.end_pose()
    if pose_error(pose, route.pieces[-1].end_pose())[1] > 1e-10:
        raise ArithmeticError("Half-turn refinement changed the combined ordered orientation")
    return FoldRoute(route.targets, tuple(pieces), route.radius_mm)


def construct(
    boundary: Boundary,
    source: Unclosed,
    minimum_straight_mm: float,
    roots: Roots,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> FoldRoute | None:
    """
    Spend one original action on the first recorded alias and at most six cap corrections.

    No orientation root, alternate split, radius or target is tried. Zero runways
    remain absent; positive material is never deleted. Every started correction
    debits the caller before projection or its original four halving trials.
    Closure grants neither contact nor hardware clearance.
    """
    checkpoint()
    if not source.alias_folds:
        return None
    route = FoldRoute(
        boundary.targets,
        Model(boundary, source.chain.topology).pieces(source.closure.values),
        boundary.radius_mm,
    )
    selected = source.alias_folds[0]
    refined = split(route, selected)
    record(
        {
            "stage": "initial_alias_refinement",
            "status": "split",
            "fold": selected,
            "route": snapshot(refined),
        }
    )
    model = MovableBends(refined)
    roots.reclosures += 1

    def charged() -> None:
        """
        Debit a started correction before the shared kernel can project or decline.
        """
        roots.newton_steps += 1
        record(
            {
                "stage": "initial_alias_refinement",
                "status": "newton",
                "step": roots.newton_steps,
            }
        )

    values = retract_active(
        model,
        model.initial,
        checkpoint,
        closure_policy=ClosurePolicy.ORDERED_CAPS,
        maximum_steps=min(6, roots.newton_limit - roots.newton_steps),
        on_step=charged,
    )
    if values is None:
        return None
    candidate = FoldRoute(boundary.targets, model.pieces(values), boundary.radius_mm)
    checkpoint()
    if (
        not ordered_mating_caps(candidate.pieces, candidate.targets)
        or cap_error(candidate) > 1e-7
        or material_error(candidate) > 1e-10
        or any(
            piece.geometry.material_length_mm <= minimum_straight_mm
            for piece in candidate.pieces
            if isinstance(piece.geometry, Straight)
        )
    ):
        return None
    record(
        {
            "stage": "initial_alias_refinement",
            "status": "closed",
            "newton_steps": roots.newton_steps,
            "route": snapshot(candidate),
        }
    )
    return candidate
