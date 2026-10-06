"""
Intersect sampled lanes with local section planes without projecting their points.

This host-only candidate is not installed in the native builder. Intersections
lie on the input polylines, but reconnecting them changes the sampled polylines;
neither continuous conductor geometry nor native cap tangency is certified.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from cable_bundler.routing.geometry import Vector3, difference, dot, lerp, magnitude, unit
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame
from experiments.experiment_secure_discrete_ribbon.shape import (
    RibbonShape,
    _maximum_pitch_ratio,
    _minimum_end_radius,
    ribbon_line_lengths,
)

PLANE_TOLERANCE_MM = 1e-9


class SectionSamplingRejected(ValueError):
    """
    Reject a missing, ambiguous or traversal-reversing local intersection.
    """


@dataclass(frozen=True)
class SectionSampling:
    """
    Retain section samples and their source-polyline coordinates in lane order.
    """

    shape: RibbonShape
    source_parameters: tuple[tuple[float, ...], ...]
    maximum_same_index_displacement_mm: float


def _intersection(
    lane: tuple[Vector3, ...], frame: RibbonFrame, station: int
) -> tuple[Vector3, float]:
    """
    Require one crossing in the two source segments adjoining an interior station.

    Shared-vertex crossings are deduplicated by source coordinate. A segment
    contained in the plane is ambiguous. No remote crossing or fallback is used.
    """
    normal = unit(frame.tangent)
    hits: dict[float, Vector3] = {}
    for index in (station - 1, station):
        left, right = lane[index : index + 2]
        a = dot(difference(left, frame.origin), normal)
        b = dot(difference(right, frame.origin), normal)
        if abs(a) <= PLANE_TOLERANCE_MM and abs(b) <= PLANE_TOLERANCE_MM:
            raise SectionSamplingRejected(f"Station {station}: coplanar source segment.")
        if abs(a) <= PLANE_TOLERANCE_MM:
            hits[float(index)] = left
        elif abs(b) <= PLANE_TOLERANCE_MM:
            hits[float(index + 1)] = right
        elif a * b < 0:
            fraction = a / (a - b)
            hits[index + fraction] = lerp(left, right, fraction)
    if len(hits) != 1:
        raise SectionSamplingRejected(f"Station {station}: {len(hits)} local crossings.")
    parameter, point = next(iter(hits.items()))
    return point, parameter


def sample_section_planes(shape: RibbonShape, diameter_mm: float) -> SectionSampling:
    """
    Preserve exact cap samples and resample interior lanes on their frame planes.

    Frame count, bank, cap fits, support, conductor indices and targets stay fixed.
    Reject nonfinite inputs, nonplanar caps, ambiguous crossings and reversed
    source traversal. Recompute sampled metrics using the existing definitions;
    no solver search, target movement, normal correction or native calls occur.
    """
    frames = shape.frames
    if len(frames) < 3 or not shape.lanes or any(len(lane) != len(frames) for lane in shape.lanes):
        raise ValueError("Section sampling needs equal lane/frame counts and three stations.")
    if not math.isfinite(diameter_mm) or diameter_mm <= 0:
        raise ValueError("Section sampling needs a positive finite diameter.")
    vectors = [point for lane in shape.lanes for point in lane]
    vectors.extend(vector for frame in frames for vector in (frame.origin, frame.tangent))
    if any(not all(math.isfinite(v) for v in (p.x, p.y, p.z)) for p in vectors):
        raise ValueError("Section sampling inputs must be finite.")
    if any(magnitude(frame.tangent) <= 1e-12 for frame in frames):
        raise ValueError("Section planes require nonzero normals.")
    lanes = []
    coordinates = []
    displacement = 0.0
    for lane in shape.lanes:
        for index in (0, -1):
            frame = frames[index]
            if (
                abs(dot(difference(lane[index], frame.origin), unit(frame.tangent)))
                > PLANE_TOLERANCE_MM
            ):
                raise SectionSamplingRejected("A fixed cap sample is off its section plane.")
        points = [lane[0]]
        parameters = [0.0]
        for station in range(1, len(frames) - 1):
            point, parameter = _intersection(lane, frames[station], station)
            if parameter <= parameters[-1] + 1e-10:
                raise SectionSamplingRejected(f"Station {station}: source traversal reversed.")
            displacement = max(displacement, magnitude(difference(point, lane[station])))
            points.append(point)
            parameters.append(parameter)
        if parameters[-1] >= len(lane) - 1 - 1e-10:
            raise SectionSamplingRejected("The last crossing reaches or passes the fixed cap.")
        lanes.append((*points, lane[-1]))
        coordinates.append((*parameters, float(len(lane) - 1)))
    sampled_lanes = tuple(lanes)
    lengths = ribbon_line_lengths(sampled_lanes)
    if min(lengths) <= 1e-12:
        raise SectionSamplingRejected("A resampled lane has no usable length.")
    distances = [0.0]
    for left, right in zip(frames, frames[1:]):
        distances.append(distances[-1] + magnitude(difference(right.origin, left.origin)))
    sampled = replace(
        shape,
        lanes=sampled_lanes,
        lengths_mm=lengths,
        spread=(max(lengths) - min(lengths)) / max(lengths),
        maximum_pitch_ratio=_maximum_pitch_ratio(sampled_lanes, diameter_mm),
        minimum_end_radius_mm=_minimum_end_radius(
            sampled_lanes,
            tuple(distances),
            shape.end_lead_mm,
            shape.start_fit is not None,
            shape.end_fit is not None,
        ),
    )
    return SectionSampling(sampled, tuple(coordinates), displacement)


def section_metrics(shape: RibbonShape, diameter_mm: float) -> dict[str, float]:
    """
    Measure finite section planarity, signed lane order and neighboring spacing.

    These metrics do not inspect lobe intersections or native interpolation.
    Interior lobe normals remain frame thickness directions in the builder.
    """
    gaps = [
        magnitude(difference(right[i], left[i])) / diameter_mm
        for i in range(len(shape.frames))
        for left, right in zip(shape.lanes, shape.lanes[1:])
    ]
    order = [
        dot(difference(right[i], left[i]), frame.width)
        for i, frame in enumerate(shape.frames)
        for left, right in zip(shape.lanes, shape.lanes[1:])
    ]
    return {
        "maximum_center_off_plane_mm": max(
            abs(dot(difference(lane[i], frame.origin), unit(frame.tangent)))
            for i, frame in enumerate(shape.frames)
            for lane in shape.lanes
        ),
        "minimum_neighbor_pitch_ratio": min(gaps, default=1.0),
        "maximum_neighbor_pitch_ratio": max(gaps, default=1.0),
        "minimum_signed_neighbor_order_mm": min(order, default=diameter_mm),
    }
