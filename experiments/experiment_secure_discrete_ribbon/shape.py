"""
Fit modest local folds to the conductor paths of a joined discrete ribbon.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit

from .frames import RibbonFrame, ribbon_lane_points

RIBBON_LENGTH_SPREAD_LIMIT = 0.01
RIBBON_NEIGHBOR_PITCH_LIMIT = 1.03
RIBBON_END_BEND_RADIUS_FACTOR = 3.0


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
    start_fit: RibbonEndFit | None = None
    end_fit: RibbonEndFit | None = None
    end_lead_mm: float = 0.0
    minimum_end_radius_mm: float | None = None

    @property
    def meets_length_target(self) -> bool:
        """
        Report whether the longest and shortest lines differ by at most 1%.
        """
        return self.spread <= RIBBON_LENGTH_SPREAD_LIMIT + 1e-9


@dataclass(frozen=True)
class RibbonEndFit:
    """
    Specify ordered lane centers and in-plane lobe normals on an end guide.
    """

    centers: tuple[Vector3, ...]
    normals: tuple[Vector3, ...]
    edges: tuple[Vector3, ...] = ()
    edge_normals: tuple[Vector3, ...] = ()
    approach_normal: Vector3 | None = None


def _blend_end_fit(
    lanes: tuple[tuple[Vector3, ...], ...],
    fit: RibbonEndFit | None,
    *,
    at_start: bool,
    distances_mm: tuple[float, ...],
    lead_mm: float,
) -> tuple[tuple[Vector3, ...], ...]:
    """
    Blend positions and guide-normal entry tangents over a physical lead length.
    """
    if fit is None:
        return lanes
    if len(fit.centers) != len(lanes) or len(fit.normals) != len(lanes):
        raise ValueError("Ribbon end fit must supply every line in route order.")
    total = distances_mm[-1]
    end_index = 0 if at_start else -1
    next_index = 1 if at_start else -2
    first_span = distances_mm[1] if at_start else total - distances_mm[-2]
    center_lane = lanes[len(lanes) // 2]
    inward = difference(center_lane[next_index], center_lane[end_index])
    tangent_correction = Vector3(0.0, 0.0, 0.0)
    if (
        fit.approach_normal is not None
        and magnitude(fit.approach_normal) > 1e-8
        and first_span > 1e-8
        and magnitude(inward) > 1e-8
    ):
        guide_direction = fit.approach_normal
        if dot(guide_direction, inward) < 0.0:
            guide_direction = Vector3(-guide_direction.x, -guide_direction.y, -guide_direction.z)
        desired = unit(guide_direction)
        speed = magnitude(inward) / first_span
        tangent_correction = difference(
            Vector3(desired.x * speed, desired.y * speed, desired.z * speed),
            Vector3(inward.x / first_span, inward.y / first_span, inward.z / first_span),
        )
    adjusted = []
    for lane, target in zip(lanes, fit.centers):
        delta = difference(target, lane[end_index])
        points = list(lane)
        for index, point in enumerate(points):
            distance = distances_mm[index] if at_start else total - distances_mm[index]
            if distance >= lead_mm:
                continue
            fraction = distance / lead_mm
            position_weight = 1.0 - 10.0 * fraction**3 + 15.0 * fraction**4 - 6.0 * fraction**5
            tangent_weight = distance * (1.0 - fraction) ** 3
            points[index] = point.translated(delta, position_weight).translated(
                tangent_correction, tangent_weight
            )
        adjusted.append(tuple(points))
    return tuple(adjusted)


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


def _minimum_end_radius(
    lanes: tuple[tuple[Vector3, ...], ...],
    distances_mm: tuple[float, ...],
    lead_mm: float,
    start_fitted: bool,
    end_fitted: bool,
) -> float | None:
    """
    Measure the smallest sampled circumradius within either fitted lead-in.
    """
    if not start_fitted and not end_fitted:
        return None
    total = distances_mm[-1]
    radii = []
    for lane in lanes:
        for index in range(len(lane) - 2):
            middle_distance = distances_mm[index + 1]
            if not (
                (start_fitted and middle_distance <= lead_mm)
                or (end_fitted and total - middle_distance <= lead_mm)
            ):
                continue
            left = difference(lane[index + 1], lane[index])
            right = difference(lane[index + 2], lane[index + 1])
            chord = difference(lane[index + 2], lane[index])
            area_twice = magnitude(cross(left, right))
            if area_twice > 1e-9:
                radii.append(
                    magnitude(left) * magnitude(right) * magnitude(chord) / (2.0 * area_twice)
                )
    return min(radii) if radii else None


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
    terminal_fade_fraction: float,
) -> tuple[Vector3, ...]:
    """
    Add a zero-displacement, zero-slope-ended buckle in the flexible direction.
    """

    def fade(fraction: float) -> float:
        """
        Keep full fold amplitude out of the diameter-scaled end approach.
        """
        if terminal_fade_fraction <= 0.0:
            return 1.0
        distance = min(
            1.0,
            fraction / terminal_fade_fraction,
            (1.0 - fraction) / terminal_fade_fraction,
        )
        return distance * distance * (3.0 - 2.0 * distance)

    return tuple(
        point
        if fraction <= 0.0 or fraction >= 1.0
        else point.translated(
            frame.thickness,
            amplitude_mm
            * math.sin(math.pi * fraction) ** 2
            * math.sin(2.0 * math.pi * cycles * fraction)
            * fade(fraction),
        )
        for point, frame, fraction in zip(base, frames, fractions)
    )


def _scaled_folds(
    base_lanes: tuple[tuple[Vector3, ...], ...],
    folded_lanes: tuple[tuple[Vector3, ...], ...],
    scale: float,
) -> tuple[tuple[Vector3, ...], ...]:
    """
    Reduce differential folds without moving any terminal lane center.
    """
    return tuple(
        tuple(
            original.translated(difference(folded, original), scale)
            for original, folded in zip(base, fitted)
        )
        for base, fitted in zip(base_lanes, folded_lanes)
    )


def solve_ribbon_shape(
    frames: tuple[RibbonFrame, ...],
    line_count: int,
    line_diameter_mm: float,
    *,
    start_fit: RibbonEndFit | None = None,
    end_fit: RibbonEndFit | None = None,
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
    distances = [0.0]
    for left, right in zip(frames, frames[1:]):
        distances.append(distances[-1] + magnitude(difference(right.origin, left.origin)))
    route_length = distances[-1]
    if route_length <= 1e-8:
        raise ValueError("A ribbon route has no usable centerline length.")
    width = line_count * line_diameter_mm
    end_lead_mm = (
        min(max(width, 9.0 * line_diameter_mm), 0.45 * route_length)
        if start_fit or end_fit
        else 0.0
    )
    distances_mm = tuple(distances)
    base_lanes = ribbon_lane_points(frames, line_count, line_diameter_mm)
    base_lanes = _blend_end_fit(
        base_lanes, start_fit, at_start=True, distances_mm=distances_mm, lead_mm=end_lead_mm
    )
    base_lanes = _blend_end_fit(
        base_lanes, end_fit, at_start=False, distances_mm=distances_mm, lead_mm=end_lead_mm
    )
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
            start_fit,
            end_fit,
            end_lead_mm,
            _minimum_end_radius(
                base_lanes, distances_mm, end_lead_mm, start_fit is not None, end_fit is not None
            ),
        )

    fractions = tuple(distance / route_length for distance in distances)
    maximum_cycles = min(6, math.floor(route_length / width), (len(frames) - 1) // 8)
    maximum_amplitude = min(0.2 * route_length, max(2.0 * line_diameter_mm, 0.25 * width))
    pitch_limit = max(
        RIBBON_NEIGHBOR_PITCH_LIMIT, _maximum_pitch_ratio(base_lanes, line_diameter_mm)
    )
    best_lanes = base_lanes
    best_lengths = base_lengths
    best_spread = spread
    best_folded = False
    maximum_neighbor_amplitude_step = line_diameter_mm * math.sqrt(
        RIBBON_NEIGHBOR_PITCH_LIMIT**2 - 1.0
    )
    terminal_fade_fraction = end_lead_mm / route_length if start_fit or end_fit else 0.0
    for cycles in range(1, maximum_cycles + 1):
        target_amplitudes = []
        for base, base_length in zip(base_lanes, base_lengths):
            if (longest - base_length) / longest <= 1e-5:
                target_amplitudes.append(0.0)
                continue
            upper_lane = _folded_lane(
                frames, base, fractions, cycles, maximum_amplitude, terminal_fade_fraction
            )
            if _line_length(upper_lane) < longest:
                target_amplitudes.append(maximum_amplitude)
                continue
            lower, upper = 0.0, maximum_amplitude
            for _ in range(28):
                middle = (lower + upper) / 2.0
                candidate = _folded_lane(
                    frames, base, fractions, cycles, middle, terminal_fade_fraction
                )
                if _line_length(candidate) < longest:
                    lower = middle
                else:
                    upper = middle
            target_amplitudes.append(upper)
        bounded_amplitudes = tuple(
            min(
                target + maximum_neighbor_amplitude_step * abs(index - target_index)
                for target_index, target in enumerate(target_amplitudes)
            )
            for index in range(line_count)
        )
        candidate_lanes = tuple(
            _folded_lane(frames, base, fractions, cycles, amplitude, terminal_fade_fraction)
            for base, amplitude in zip(base_lanes, bounded_amplitudes)
        )
        if _maximum_pitch_ratio(candidate_lanes, line_diameter_mm) > pitch_limit + 1e-9:
            lower, upper = 0.0, 1.0
            for _ in range(24):
                middle = (lower + upper) / 2.0
                scaled = _scaled_folds(base_lanes, candidate_lanes, middle)
                if _maximum_pitch_ratio(scaled, line_diameter_mm) <= pitch_limit + 1e-9:
                    lower = middle
                else:
                    upper = middle
            candidate_lanes = _scaled_folds(base_lanes, candidate_lanes, lower)
        candidate_lengths = ribbon_line_lengths(candidate_lanes)
        candidate_spread = (max(candidate_lengths) - min(candidate_lengths)) / max(
            candidate_lengths
        )
        if candidate_spread < best_spread - 1e-9:
            best_lanes = candidate_lanes
            best_lengths = candidate_lengths
            best_spread = candidate_spread
            best_folded = True
    return RibbonShape(
        frames,
        best_lanes,
        best_lengths,
        best_spread,
        best_folded,
        _maximum_pitch_ratio(best_lanes, line_diameter_mm),
        start_fit,
        end_fit,
        end_lead_mm,
        _minimum_end_radius(
            best_lanes, distances_mm, end_lead_mm, start_fit is not None, end_fit is not None
        ),
    )
