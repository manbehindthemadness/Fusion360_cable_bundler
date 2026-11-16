"""
Intersect explicit taper and frame spans without changing the existing branch policy.

These exact boundary patches carry geometry provenance only. A scalar timing
certificate is not a material certificate for a rational profile or moving frame.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .branch_reference import validate_spans
from .profile_transition import TransitionEdge
from .spatial_frame import FrameSpan, restrict
from .taper_schedule import BlendInterval, TaperSchedule, plan
from .tensor_composition import Fields, Net, compose_fields


@dataclass(frozen=True)
class ScheduledPatch:
    """
    Bind one exact intersection to its original section, frame and scheduled blend.
    """

    section: TransitionEdge
    frame: FrameSpan
    blend: BlendInterval
    low: Fraction
    high: Fraction
    fields: Fields
    section_rows: Net
    rows: Net


def compose(
    section: TransitionEdge,
    frame: FrameSpan,
    blend: BlendInterval,
    checkpoint: Callable[[], None],
) -> ScheduledPatch:
    """
    Restrict both original sources to their exact global intersection before composition.

    Root and terminal homogeneous rows retain original control order and weights.
    Convex blending preserves positive denominators. Frame restriction remains
    rational throughout, including when intersection coordinates are not dyadic.
    Disjoint or malformed intervals are refused rather than silently skipped.
    """
    checkpoint()
    if (
        type(blend.low) is not Fraction
        or type(blend.high) is not Fraction
        or not Fraction(0) <= blend.low < blend.high <= Fraction(1)
        or not blend.controls
        or any(
            type(value) is not Fraction or not Fraction(0) <= value <= Fraction(1)
            for value in blend.controls
        )
    ):
        raise ValueError("An exact nonempty unit blend interval is required")
    low, high = max(frame.low, blend.low), min(frame.high, blend.high)
    if low >= high:
        raise ValueError("Frame and schedule must have a nonempty intersection")
    beta = restrict(
        blend.controls,
        (low - blend.low) / (blend.high - blend.low),
        (high - blend.low) / (blend.high - blend.low),
    )
    section_rows = tuple(
        tuple(
            tuple((1 - value) * start[k] + value * end[k] for k in range(3))
            for start, end in zip(section.rows[0], section.rows[-1])
        )
        for value in beta
    )
    a, b = (
        (low - frame.low) / (frame.high - frame.low),
        (high - frame.low) / (frame.high - frame.low),
    )

    def restricted(
        field: tuple[tuple[Fraction, ...], tuple[Fraction, ...], tuple[Fraction, ...]],
    ) -> tuple[tuple[Fraction, ...], tuple[Fraction, ...], tuple[Fraction, ...]]:
        """
        Retain three exact component polynomials without a float-vector round trip.
        """
        return restrict(field[0], a, b), restrict(field[1], a, b), restrict(field[2], a, b)

    original = frame.fields()
    fields = restricted(original[0]), restricted(original[1]), restricted(original[2])
    rows = compose_fields(section_rows, fields, checkpoint)
    return ScheduledPatch(section, frame, blend, low, high, fields, section_rows, rows)


def construct(
    sections: tuple[TransitionEdge, ...],
    frames: tuple[FrameSpan, ...],
    schedule: TaperSchedule,
    checkpoint: Callable[[], None],
) -> tuple[tuple[ScheduledPatch, ...], ...]:
    """
    Cover the whole branch once with ordered schedule/frame intersections.

    This explicit experimental entry point does not replace existing candidates.
    Only complete certified schedules with exact C2 joins and cap jets are accepted;
    the certificate's physical premises still require an independent caller audit.
    """
    checkpoint()
    if not sections or not frames or schedule.status != "certified" or not schedule.intervals:
        raise ValueError("Complete source edges, frames and a certified schedule are required")
    if plan(schedule.requirements, schedule.allowance_mm, checkpoint) != schedule:
        raise ValueError("Schedule must preserve its derived controls and certificate")
    for spans in (frames, schedule.intervals):
        if (
            spans[0].low != Fraction(0)
            or spans[-1].high != Fraction(1)
            or any(left.high != right.low for left, right in zip(spans, spans[1:]))
        ):
            raise ValueError("Ordered spans must cover the complete global interval")
    validate_spans(frames, checkpoint)
    output = []
    for frame in frames:
        for blend in schedule.intervals:
            checkpoint()
            if max(frame.low, blend.low) < min(frame.high, blend.high):
                output.append(
                    tuple(compose(section, frame, blend, checkpoint) for section in sections)
                )
    return tuple(output)
