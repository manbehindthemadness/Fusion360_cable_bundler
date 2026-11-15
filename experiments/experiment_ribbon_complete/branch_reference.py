"""
Check explicit span assembly and full-curve correspondence to the frozen branch reference.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, elevate
from cable_bundler.routing import RoutePreview

from .spatial_frame import FrameSpan, components, differentiated, restrict
from .spatial_transition import SpatialPatch


@dataclass(frozen=True)
class SpanSeam:
    """
    Record source continuity facts without treating a derivative mismatch as geometric infeasibility.
    """

    coordinate: Fraction
    first_jets_equal: bool
    second_jets_equal: bool


def validate_patches(
    patches: tuple[tuple[SpatialPatch, ...], ...], checkpoint: Callable[[], None]
) -> tuple[FrameSpan, ...]:
    """
    Require complete closed ordered edge coverage and one common source frame per span.

    Material and length audits must share the same center reference on every
    boundary patch. This checks source-chart structure, not world-control fidelity,
    coordinates, isometry or native geometry. Those retain their separate checks.
    """
    checkpoint()
    if not patches or not patches[0] or any(len(span) != len(patches[0]) for span in patches):
        raise ValueError("Complete ordered boundary span and edge coverage is required")
    frames = tuple(span[0].frame for span in patches)
    validate_spans(frames, checkpoint)
    sections = tuple(patch.section for patch in patches[0])
    if any(
        first.source.geometry.controls[-1] != second.source.geometry.controls[0]
        or first.terminal.controls[-1] != second.terminal.controls[0]
        for first, second in zip(sections, sections[1:] + sections[:1])
    ):
        raise ValueError("Complete closed source and terminal boundaries are required")
    for span in patches:
        checkpoint()
        if tuple(patch.section for patch in span) != sections or any(
            patch.frame != span[0].frame for patch in span
        ):
            raise ValueError("Each span must preserve the same ordered section and frame coverage")
    return frames


def validate_spans(
    frames: tuple[FrameSpan, ...], checkpoint: Callable[[], None]
) -> tuple[SpanSeam, ...]:
    """
    Preserve supplied order, exact closed charts and one root orientation across all spans.

    Exact derivative equality is recorded as a representation fact. A mismatch
    remains unqualified for C2 construction until separately resolved; no smaller
    physical dimensional tolerance or automatic snapping is introduced.
    """
    checkpoint()
    if not frames or frames[0].low != Fraction(0) or frames[-1].high != Fraction(1):
        raise ValueError("Branch spans must cover the complete unit interval")
    seams = []
    for first, second in zip(frames, frames[1:]):
        checkpoint()
        if first.high != second.low or first.orientation is not second.orientation:
            raise ValueError("Ordered branch spans must share intervals and material orientation")
        if any(
            a[-1] != b[0]
            for a, b in zip(
                (first.center, first.width, first.thickness),
                (second.center, second.width, second.thickness),
            )
        ):
            raise ValueError("A material chart cannot contain an open source seam")
        matches = []
        for order in (1, 2):
            fields_a, fields_b = first.fields(), second.fields()
            for _ in range(order):
                fields_a = tuple(differentiated(field) for field in fields_a)
                fields_b = tuple(differentiated(field) for field in fields_b)
            matches.append(
                all(
                    a[-1] / (first.high - first.low) ** order
                    == b[0] / (second.high - second.low) ** order
                    for left, right in zip(fields_a, fields_b)
                    for a, b in zip(left, right)
                )
            )
        seams.append(SpanSeam(first.high, matches[0], matches[1]))
    return tuple(seams)


def center_error_squared(
    frames: tuple[FrameSpan, ...], reference: RoutePreview, checkpoint: Callable[[], None]
) -> Fraction:
    """
    Bound centreline displacement over every source cubic interval in reversed traversal.

    Global reference u follows the reversed cubic ordinal uniformly, explicitly
    a parameter convention rather than physical arc length. Degree elevation
    and exact restriction compare the complete curves, never just stations.
    """
    if not reference.curves:
        raise ValueError("A frozen branch curve reference is required")
    maximum = Fraction(0)
    count = len(reference.curves)
    for index, curve in enumerate(reversed(reference.curves)):
        source = components((curve.end, curve.control_b, curve.control_a, curve.start))
        low, high = Fraction(index, count), Fraction(index + 1, count)
        for frame in frames:
            checkpoint()
            a, b = max(low, frame.low), min(high, frame.high)
            if a >= b:
                continue
            candidate = components(frame.center)
            degree = max(len(frame.center) - 1, 3)
            errors = tuple(
                add(
                    elevate(
                        restrict(
                            candidate[k],
                            (a - frame.low) / (frame.high - frame.low),
                            (b - frame.low) / (frame.high - frame.low),
                        ),
                        degree,
                    ),
                    elevate(
                        restrict(source[k], (a - low) / (high - low), (b - low) / (high - low)),
                        degree,
                    ),
                    Fraction(-1),
                )
                for k in range(3)
            )
            maximum = max(
                maximum,
                max(
                    sum((errors[k][i] ** 2 for k in range(3)), Fraction(0))
                    for i in range(degree + 1)
                ),
            )
    return maximum
