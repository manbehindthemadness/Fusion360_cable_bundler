"""
Select one local escape reference from strictly revalidated current-pose geometry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from experiments.experiment_ribbon_feature_insertion.deviation_guide import DeviationGuide
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.separation import Side
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_inverse import (
    occupied_coordinates,
    profile_height,
)
from experiments.experiment_ribbon_fold_route.geometry import ZERO, FoldRoute, PlacedPiece

from .adaptive_event_window import Window, select
from .check import Report, Witness
from .feature_plane import FeatureCoverage, FeaturePlane, SignedJoints
from .material_constraint import MaterialConstraint
from .model import Hardware

WindowSelector = Callable[[FoldRoute, tuple[int, ...]], Window]


@dataclass(frozen=True)
class Proposal:
    """
    Attach a single geometric escape aim to its immutable local boundary contract.
    """

    window: Window
    frames: Frames
    offset_mm: Vector3


def _matches_material(
    piece: PlacedPiece,
    point: Vector3,
    expected: tuple[float, float, float],
    lines: int,
    diameter: float,
) -> bool:
    """
    Match a strict material preimage by world reconstruction under the existing inverse guard.

    Inverse coordinates can differ by floating-point roundoff after a rigid
    transform. Exact tuple equality would discard valid witnesses. Require both
    a current strictly occupied inverse and strictly interior recorded coordinates,
    then reconstruct the recorded point using the same thick material map and
    positional guard as occupied_coordinates. This grants guidance eligibility,
    never a contact or hardware clearance certificate.
    """
    if len(expected) != 3 or any(not math.isfinite(value) for value in expected):
        return False
    guard = 1e-9 * max(1.0, diameter)
    u, q, height = expected
    length = piece.geometry.material_length_mm
    if (
        not guard < u * length < length - guard
        or profile_height(q, lines, diameter) - abs(height) <= guard
    ):
        return False
    if occupied_coordinates(piece, point, lines, diameter) is None:
        return False
    origin, velocity, across, _ = piece.surface(u, q)
    restored = origin.translated(unit(cross(velocity, across)), height)
    return magnitude(difference(restored, point)) <= guard


def plan(
    source: FoldRoute,
    evidence: Report | ContactResult,
    hardware: Hardware,
    checkpoint: Callable[[], None],
    *,
    select_window: WindowSelector = select,
) -> Proposal | None:
    """
    Decline uncertainty or stale witnesses before deriving any new bend geometry.

    Every occupied point is checked against its exact original inverse map.
    Hardware also requires the same fixed proxy interior. The direction bounds
    complete members; a guide is an aim only, never a clearance certificate.
    A supplied selector may reopen a larger current workspace after validation;
    it must preserve source ownership and contain at least one witnessed member.
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
        if not _matches_material(
            source.pieces[index],
            witness.point,
            expected,
            source.targets.lines,
            source.targets.diameter_mm,
        ):
            return None
    model = SignedJoints(source)
    window = select_window(source, members)
    if window.source is not source or not any(window.begin <= member < window.end for member in members):
        raise ValueError("Window strategy must cover a current witness in its owned route")
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
