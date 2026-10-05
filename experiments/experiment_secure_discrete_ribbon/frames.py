"""
Build a stable, smoothly banked width frame for one discrete ribbon route.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, lerp, magnitude, unit
from cable_bundler.routing.parallel import RoutePreview
from cable_bundler.routing.smooth import sample_centerline


@dataclass(frozen=True)
class RibbonFrame:
    """
    Locate one perpendicular ribbon section in route traversal order.
    """

    origin: Vector3
    tangent: Vector3
    width: Vector3
    thickness: Vector3


def _project_width(direction: Vector3, tangent: Vector3) -> Vector3:
    """
    Project one guide width into the route section plane.
    """
    projected = difference(
        direction,
        Vector3(
            tangent.x * dot(direction, tangent),
            tangent.y * dot(direction, tangent),
            tangent.z * dot(direction, tangent),
        ),
    )
    if magnitude(projected) <= 1e-8:
        axis = min(
            (Vector3(1.0, 0.0, 0.0), Vector3(0.0, 1.0, 0.0), Vector3(0.0, 0.0, 1.0)),
            key=lambda candidate: abs(dot(candidate, tangent)),
        )
        projected = cross(tangent, axis)
    return unit(projected)


def _tangent(points: tuple[Vector3, ...], index: int) -> Vector3:
    """
    Estimate one local section tangent from neighboring route samples.
    """
    left = points[max(0, index - 1)]
    right = points[min(len(points) - 1, index + 1)]
    return unit(difference(right, left))


def ribbon_frames(
    route: RoutePreview,
    start_width: Vector3,
    end_width: Vector3,
    *,
    maximum_sections: int = 32,
) -> tuple[RibbonFrame, ...]:
    """
    Parallel-transport width and distribute the end-guide bank over route length.

    Width directions retain their signs so lane one cannot silently swap ends.
    """
    sampled = sample_centerline(route, 0.2)
    if len(sampled) < 2:
        raise ValueError("A ribbon needs at least two route positions.")
    if maximum_sections < 2:
        raise ValueError("A ribbon needs at least two section samples.")
    distances = [0.0]
    for start, end in zip(sampled, sampled[1:]):
        distances.append(distances[-1] + magnitude(difference(end, start)))
    total = distances[-1]
    if total <= 1e-8:
        raise ValueError("A ribbon route has no length.")
    positions = []
    segment = 0
    for index in range(maximum_sections):
        distance = total * index / (maximum_sections - 1)
        while segment < len(distances) - 2 and distances[segment + 1] < distance:
            segment += 1
        span = distances[segment + 1] - distances[segment]
        fraction = (distance - distances[segment]) / span if span > 1e-12 else 0.0
        positions.append(lerp(sampled[segment], sampled[segment + 1], fraction))
    sampled = tuple(positions)
    tangents = tuple(_tangent(sampled, index) for index in range(len(sampled)))
    transported = [_project_width(start_width, tangents[0])]
    for tangent in tangents[1:]:
        transported.append(_project_width(transported[-1], tangent))
    target = _project_width(end_width, tangents[-1])
    end_angle = math.atan2(
        dot(cross(transported[-1], target), tangents[-1]),
        dot(transported[-1], target),
    )
    distances = [0.0]
    for start, end in zip(sampled, sampled[1:]):
        distances.append(distances[-1] + magnitude(difference(end, start)))
    total = distances[-1]
    frames = []
    for point, tangent, width, distance in zip(sampled, tangents, transported, distances):
        angle = end_angle * distance / total
        side = cross(tangent, width)
        banked = unit(
            Vector3(
                width.x * math.cos(angle) + side.x * math.sin(angle),
                width.y * math.cos(angle) + side.y * math.sin(angle),
                width.z * math.cos(angle) + side.z * math.sin(angle),
            )
        )
        frames.append(RibbonFrame(point, tangent, banked, unit(cross(tangent, banked))))
    return tuple(frames)


def ribbon_lane_points(
    frames: tuple[RibbonFrame, ...], line_count: int, line_diameter_mm: float
) -> tuple[tuple[Vector3, ...], ...]:
    """
    Return stable left-to-right lane centerlines for lightweight preview graphics.
    """
    return tuple(
        tuple(
            frame.origin.translated(
                frame.width, (index - (line_count - 1) / 2.0) * line_diameter_mm
            )
            for frame in frames
        )
        for index in range(line_count)
    )


def ribbon_has_hard_axis_bend(frames: tuple[RibbonFrame, ...]) -> bool:
    """
    Detect route turns predominantly across the broad, stiff ribbon width.
    """
    for left, right in zip(frames, frames[1:]):
        turn = difference(right.tangent, left.tangent)
        if magnitude(turn) < 0.05:
            continue
        hard = abs(dot(turn, left.width))
        easy = abs(dot(turn, left.thickness))
        if hard > 2.0 * easy:
            return True
    return False
