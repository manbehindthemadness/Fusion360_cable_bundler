"""
Share normalized exploration and actual ordered-cap certification across material retractions.
"""

from __future__ import annotations

from enum import Enum

from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps

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
    return ordered_mating_caps(model.pieces(values), model.original.targets)
