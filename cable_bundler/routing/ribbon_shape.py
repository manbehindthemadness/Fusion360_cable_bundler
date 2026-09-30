"""
Fit modest local folds to the conductor paths of a joined discrete ribbon.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import Vector3, difference, magnitude
from .ribbon import RibbonFrame, ribbon_lane_points

RIBBON_LENGTH_SPREAD_LIMIT = 0.01
RIBBON_NEIGHBOR_PITCH_LIMIT = 1.10


@dataclass(frozen=True)
class RibbonShape:
    """
    Keep the preview, solid sections, and length report on one sampled shape.
    """

    frames: tuple[RibbonFrame, ...]
    lanes: tuple[tuple[Vector3, ...], ...]
    lengths_mm: tuple[float, ...]
    spread: float
    folded: bool
    maximum_pitch_ratio: float

    @property
    def meets_length_target(self) -> bool:
        """
        Report whether the longest and shortest lines differ by at most 1%.
        """
        return self.spread <= RIBBON_LENGTH_SPREAD_LIMIT + 1e-9


def _line_length(points: tuple[Vector3, ...]) -> float:
    """
    Measure the visible sampled line without substituting the route centerline.
    """
    return sum(magnitude(difference(right, left)) for left, right in zip(points, points[1:]))


def ribbon_line_lengths(lanes: tuple[tuple[Vector3, ...], ...]) -> tuple[float, ...]:
    """
    Measure ordered physical conductor paths in millimeters.
    """
    return tuple(_line_length(lane) for lane in lanes)


def _maximum_pitch_ratio(lanes: tuple[tuple[Vector3, ...], ...], diameter_mm: float) -> float:
    """
    Bound deformation of the joined web between neighboring conductors.
    """
    if len(lanes) < 2:
        return 1.0
    return max(
        magnitude(difference(right, left)) / diameter_mm
        for left_lane, right_lane in zip(lanes, lanes[1:])
        for left, right in zip(left_lane, right_lane)
    )


def _folded_lane(
    frames: tuple[RibbonFrame, ...],
    base: tuple[Vector3, ...],
    fractions: tuple[float, ...],
    cycles: int,
    amplitude_mm: float,
) -> tuple[Vector3, ...]:
    """
    Add a zero-displacement, zero-slope-ended buckle in the flexible direction.
    """
    return tuple(
        point
        if fraction <= 0.0 or fraction >= 1.0
        else point.translated(
            frame.thickness,
            amplitude_mm
            * math.sin(math.pi * fraction) ** 2
            * math.sin(2.0 * math.pi * cycles * fraction),
        )
        for point, frame, fraction in zip(base, frames, fractions)
    )


def solve_ribbon_shape(
    frames: tuple[RibbonFrame, ...], line_count: int, line_diameter_mm: float
) -> RibbonShape:
    """
    Match shorter lines to the longest path using bounded, joined local folds.

    The fit is deliberately approximate: it limits displacement and leaves an
    honest measured warning for routes that cannot be equalized plausibly.
    """
    if len(frames) < 2 or line_count < 1 or not math.isfinite(line_diameter_mm):
        raise ValueError("A ribbon needs frames, at least one line, and a finite line diameter.")
    if line_diameter_mm <= 0.0:
        raise ValueError("Ribbon line diameter must be positive.")
    base_lanes = ribbon_lane_points(frames, line_count, line_diameter_mm)
    base_lengths = ribbon_line_lengths(base_lanes)
    longest = max(base_lengths)
    if longest <= 1e-8:
        raise ValueError("A ribbon route has no usable length.")
    spread = (longest - min(base_lengths)) / longest
    if spread <= RIBBON_LENGTH_SPREAD_LIMIT:
        return RibbonShape(
            frames,
            base_lanes,
            base_lengths,
            spread,
            False,
            _maximum_pitch_ratio(base_lanes, line_diameter_mm),
        )

    distances = [0.0]
    for left, right in zip(frames, frames[1:]):
        distances.append(distances[-1] + magnitude(difference(right.origin, left.origin)))
    route_length = distances[-1]
    if route_length <= 1e-8:
        raise ValueError("A ribbon route has no usable centerline length.")
    fractions = tuple(distance / route_length for distance in distances)
    width = line_count * line_diameter_mm
    cycles = 3 if route_length < 3.0 * width else 4
    maximum_amplitude = min(0.2 * route_length, max(2.0 * line_diameter_mm, 0.25 * width))
    fitted_lanes = []
    for base, base_length in zip(base_lanes, base_lengths):
        if (longest - base_length) / longest <= 1e-5:
            fitted_lanes.append(base)
            continue
        upper_lane = _folded_lane(frames, base, fractions, cycles, maximum_amplitude)
        if _line_length(upper_lane) < longest:
            fitted_lanes.append(upper_lane)
            continue
        lower, upper = 0.0, maximum_amplitude
        for _ in range(28):
            middle = (lower + upper) / 2.0
            candidate = _folded_lane(frames, base, fractions, cycles, middle)
            if _line_length(candidate) < longest:
                lower = middle
            else:
                upper = middle
        fitted_lanes.append(_folded_lane(frames, base, fractions, cycles, upper))
    lanes = tuple(fitted_lanes)
    maximum_pitch_ratio = _maximum_pitch_ratio(lanes, line_diameter_mm)
    if maximum_pitch_ratio > RIBBON_NEIGHBOR_PITCH_LIMIT:
        lower, upper = 0.0, 1.0
        for _ in range(24):
            scale = (lower + upper) / 2.0
            scaled = tuple(
                tuple(
                    Vector3(
                        original.x + scale * (folded.x - original.x),
                        original.y + scale * (folded.y - original.y),
                        original.z + scale * (folded.z - original.z),
                    )
                    for original, folded in zip(base, fitted)
                )
                for base, fitted in zip(base_lanes, lanes)
            )
            if _maximum_pitch_ratio(scaled, line_diameter_mm) <= RIBBON_NEIGHBOR_PITCH_LIMIT:
                lower = scale
            else:
                upper = scale
        lanes = tuple(
            tuple(
                Vector3(
                    original.x + lower * (folded.x - original.x),
                    original.y + lower * (folded.y - original.y),
                    original.z + lower * (folded.z - original.z),
                )
                for original, folded in zip(base, fitted)
            )
            for base, fitted in zip(base_lanes, lanes)
        )
        maximum_pitch_ratio = _maximum_pitch_ratio(lanes, line_diameter_mm)
    lengths = ribbon_line_lengths(lanes)
    spread = (max(lengths) - min(lengths)) / max(lengths)
    return RibbonShape(frames, lanes, lengths, spread, True, maximum_pitch_ratio)
