"""
Share the actual cap-frame precondition of analytic mating proofs without changing physical tolerances.
"""

from __future__ import annotations

import math

from devtools.ribbon_analysis.contracts import TargetPose

from .geometry import PlacedPiece, Pose, pose_error

MATING_FRAME_LIMIT = 1e-10


def matching_frame(actual: Pose, expected: Pose) -> bool:
    """
    Require finite positional millimeter and ordered-frame vector errors below the existing proof limit.
    """
    return all(
        math.isfinite(error) and error < MATING_FRAME_LIMIT
        for error in pose_error(actual, expected)
    )


def ordered_mating_caps(pieces: tuple[PlacedPiece, ...], targets: TargetPose) -> bool:
    """
    Check both real terminal frames without using a normalized Newton residual or moving a target.
    """
    if not pieces:
        return False
    start = Pose(targets.start, targets.start_tangent, targets.start_width)
    end = Pose(targets.end, targets.end_tangent, targets.end_width)
    return matching_frame(pieces[0].pose, start) and matching_frame(pieces[-1].end_pose(), end)
