"""
Share normalized exploration and actual ordered-cap certification across material retractions.
"""

from __future__ import annotations

from enum import Enum

from experiments.experiment_ribbon_fold_route.geometry import Pose, pose_error

from .flexible import FlexibleModel


class ClosurePolicy(Enum):
    """
    Distinguish normalized exploratory retraction from actual ordered-cap certification.
    """

    NORMALIZED = "normalized"
    ORDERED_CAPS = "ordered_caps"


def ordered_caps_closed(model: FlexibleModel, values: tuple[float, ...]) -> bool:
    """
    Require actual fixed cap poses at the accuracy used by analytic mating proofs.

    Position is measured in millimeters, while the ordered tangent and width use
    their vector residuals. Do not replace this with the model's length-normalized
    Newton residual or local rotation vector, which can also vanish at a half-turn.
    """
    pieces = model.pieces(values)
    if not pieces:
        return False
    target = model.original.targets
    start = Pose(target.start, target.start_tangent, target.start_width)
    end = Pose(target.end, target.end_tangent, target.end_width)
    errors = pose_error(pieces[0].pose, start) + pose_error(pieces[-1].end_pose(), end)
    return max(errors) < 1e-10
