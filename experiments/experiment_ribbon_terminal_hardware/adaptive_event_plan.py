"""
Select one local escape reference from strictly revalidated current-pose geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import Vector3, difference, dot, unit
from experiments.experiment_ribbon_feature_insertion.deviation_guide import DeviationGuide
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.separation import Side
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import ZERO, FoldRoute

from .adaptive_event_window import Window, select
from .check import Report, Witness
from .feature_plane import FeatureCoverage, FeaturePlane, SignedJoints
from .material_constraint import MaterialConstraint
from .model import Hardware


@dataclass(frozen=True)
class Proposal:
    """
    Attach a single geometric escape aim to its immutable local boundary contract.
    """

    window: Window
    frames: Frames
    offset_mm: Vector3


def plan(
    source: FoldRoute,
    evidence: Report | ContactResult,
    hardware: Hardware,
    checkpoint: Callable[[], None],
) -> Proposal | None:
    """
    Decline uncertainty or stale witnesses before deriving any new bend geometry.

    Every occupied point is checked against its exact original inverse map.
    Hardware also requires the same fixed proxy interior. The direction bounds
    complete members; a guide is an aim only, never a clearance certificate.
    """
    checkpoint()
    witness = evidence.witness
    if (
        evidence.status != ("blocked" if isinstance(evidence, Report) else "penetration")
        or witness is None
    ):
        return None
    if isinstance(evidence, ContactResult) and evidence.limit is not None:
        return None
    if hardware.targets != source.targets:
        raise ValueError("Adaptive geometry must retain both original hardware targets")
    members = (witness.piece,) if isinstance(witness, Witness) else witness.pieces
    coordinates = (
        (witness.material,) if isinstance(witness, Witness) else (witness.first, witness.second)
    )
    if any(type(i) is not int or not 0 <= i < len(source.pieces) for i in members):
        return None
    for index, expected in zip(members, coordinates):
        checkpoint()
        actual = occupied_coordinates(
            source.pieces[index], witness.point, source.targets.lines, source.targets.diameter_mm
        )
        if actual is None or actual != expected:
            return None
    model = SignedJoints(source)
    window = select(source, members)
    if isinstance(witness, Witness):
        assert isinstance(evidence, Report)
        box = next((box for box in hardware.boxes if box.terminal.value == witness.terminal), None)
        if box is None or not all(
            span.low < dot(difference(witness.point, box.pose.origin), axis) < span.high
            for span, axis in zip(box.bounds, box.axes)
        ):
            return None
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
        direction, gap = plane.separation_direction(model.initial), plane.gap(model.initial)
    else:
        bound = MaterialConstraint.from_witness(model, source, witness)
        if bound is None:
            return None
        before, after = bound.gap(model.initial, Side.BEFORE), bound.gap(model.initial, Side.AFTER)
        first_moves = window.begin <= members[0] < window.end
        sign = (1 if after > before else -1) * (1 if first_moves else -1)
        direction, gap = ZERO.translated(unit(bound.bound.axis), sign), max(before, after)
    amplitude = max(2 * source.half_width_mm, -gap * model.scale + source.targets.diameter_mm)
    offset = ZERO.translated(direction, amplitude)
    checkpoint()
    try:
        guide = DeviationGuide.deviated(window.route.targets, offset)
        frames = Frames.from_guide(window.route.targets, guide)
    except ValueError:
        return None
    return Proposal(window, frames, offset)
