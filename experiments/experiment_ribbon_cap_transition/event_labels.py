"""
Compare observational event signals without splitting or changing a continuous strip.

Edge curvature difference is an uncalibrated proxy, not a physical resistance law.
Signed center bending is a separate comparison signal. Labels never alter a path,
create geometry joins, or rename material sides. Equal nonzero demand is balanced;
only negligible bend and twist is straight. Fixed sample persistence suppresses
short sign flicker without certifying a physical event boundary.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from enum import Enum

from cable_bundler.routing.geometry import cross, dot, magnitude

from .material_strip import MaterialStrip

SAMPLES = 257
ZERO_RATE = 1e-8
RELATIVE_EDGE_DIFFERENCE = 1e-3
PERSISTENCE = 3


class EventKind(Enum):
    """
    Identify proxy observations, not separate geometric objects or physical laws.
    """

    A = "A greater curvature"
    B = "B greater curvature"
    POSITIVE = "positive bend"
    NEGATIVE = "negative bend"
    BALANCED = "balanced spatial motion"
    STRAIGHT = "straight run"


@dataclass(frozen=True)
class EventRegion:
    """
    Retain a sampled interval of one persistent conceptual label.
    """

    kind: EventKind
    start_mm: float
    end_mm: float


@dataclass(frozen=True)
class EventReadout:
    """
    Keep both label hypotheses and bounded sampling diagnostics together.
    """

    edge_regions: tuple[EventRegion, ...]
    bend_regions: tuple[EventRegion, ...]
    maximum_relative_edge_difference: float
    sample_count: int


def _regions(labels: list[EventKind], length: float) -> tuple[EventRegion, ...]:
    """
    Require three consecutive labels to confirm a change and retain neutral regions.

    A confirmed change starts at its first supporting sample. Isolated samples
    retain the previous region. This finite sampling rule is a diagnostic choice,
    not a geometry tolerance or a continuous physical classification guarantee.
    """
    current, start = labels[0], 0
    pending, pending_start, count = current, 0, 0
    result = []
    for index, label in enumerate(labels[1:], 1):
        if label is current:
            pending, count = current, 0
            continue
        if label is not pending:
            pending, pending_start, count = label, index, 1
        else:
            count += 1
        if count == PERSISTENCE:
            boundary = pending_start * length / (len(labels) - 1)
            result.append(EventRegion(current, start * length / (len(labels) - 1), boundary))
            current, start, count = label, pending_start, 0
    result.append(EventRegion(current, start * length / (len(labels) - 1), length))
    return tuple(result)


def inspect(strip: MaterialStrip) -> EventReadout:
    """
    Observe257 common material stations, with no solver call or path modification.

    A/B always denote positive/negative material-width edges. Curvature magnitudes
    at matched material stations are compared using a0.1percent relative deadband.
    Center bend sign is measured against T cross W; twist is the width-frame rate.
    Zero-rate1e-8/mm is an observational deadband only. No local edge label is
    interpreted as a proved physical outside edge or force/tension measurement.
    """
    edge_labels, bend_labels, maximum_difference = [], [], 0.0
    boundaries = strip.boundaries(0)
    for index in range(SAMPLES):
        distance = strip.length_mm * index / (SAMPLES - 1)
        slot = min(bisect_right(boundaries, distance) - 1, len(strip.spans) - 1)
        span = strip.spans[slot]
        u = (distance - boundaries[slot]) / (boundaries[slot + 1] - boundaries[slot])
        tangent, width = span.motion.frame(u)
        _, rate, _ = span.motion.angle_jet(u)
        twist = abs(rate * dot(span.motion.axis, tangent) / span.motion.length)
        _, _, acceleration = strip.jet(distance)
        bend = dot(acceleration, cross(tangent, width))
        a = magnitude(strip.jet(distance, strip.half_width_mm)[2])
        b = magnitude(strip.jet(distance, -strip.half_width_mm)[2])
        relative = (a - b) / max(a, b, ZERO_RATE)
        maximum_difference = max(maximum_difference, abs(relative))
        if max(magnitude(acceleration), twist) <= ZERO_RATE:
            edge_labels.append(EventKind.STRAIGHT)
            bend_labels.append(EventKind.STRAIGHT)
        else:
            edge_labels.append(
                EventKind.A
                if relative > RELATIVE_EDGE_DIFFERENCE
                else EventKind.B
                if relative < -RELATIVE_EDGE_DIFFERENCE
                else EventKind.BALANCED
            )
            bend_labels.append(
                EventKind.POSITIVE
                if bend > ZERO_RATE
                else EventKind.NEGATIVE
                if bend < -ZERO_RATE
                else EventKind.BALANCED
            )
    return EventReadout(
        _regions(edge_labels, strip.length_mm),
        _regions(bend_labels, strip.length_mm),
        maximum_difference,
        SAMPLES,
    )
