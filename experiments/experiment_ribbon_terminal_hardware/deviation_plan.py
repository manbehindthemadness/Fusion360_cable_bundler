"""
Derive one spatial offset-and-return reference from complete witnessed material intrusion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_feature_insertion.deviation_guide import DeviationGuide
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_fold_route.geometry import ZERO, FoldRoute

from .check import Report
from .feature_plane import FeatureCoverage, FeaturePlane, SignedJoints
from .model import Hardware


@dataclass(frozen=True)
class DeviationPlan:
    """
    Keep the measured separating direction and exactly one endpoint-preserving steering reference.
    """

    frames: Frames
    offset_mm: Vector3
    source_gap_mm: float
    parameters: tuple[float, ...]


def plan(
    source: FoldRoute, evidence: Report, hardware: Hardware, checkpoint: Callable[[], None]
) -> DeviationPlan | None:
    """
    Move the whole witnessed feature toward its nearest separating halfspace, not only its contact point.

    Use one profile width or the required translation plus one thickness,
    whichever is larger. This scale-derived reference is not a physical proof.
    Missing intrusion, unsupported feature geometry or a nonregular reference
    declines without a route construction. Hard caller failures propagate.
    """
    checkpoint()
    if evidence.status != "blocked" or evidence.witness is None:
        return None
    model = SignedJoints(source)
    plane = FeaturePlane.create(
        model,
        source,
        evidence,
        hardware,
        model.initial,
        coverage=FeatureCoverage.ADJOINING_INTERNAL,
    )
    if plane is None:
        return None
    direction = plane.separation_direction(model.initial)
    gap_mm = plane.gap(model.initial) * model.scale
    amplitude = max(2 * source.half_width_mm, -gap_mm + source.targets.diameter_mm)
    offset = ZERO.translated(direction, amplitude)
    guide = DeviationGuide.deviated(source.targets, offset)
    checkpoint()
    try:
        frames = Frames.from_guide(source.targets, guide)
    except ValueError:
        return None
    checkpoint()
    return DeviationPlan(frames, offset, gap_mm, guide.stations())
