"""
Host-independent procedural stripe surface geometry.
"""

from __future__ import annotations

import math

from ..domain import StripePattern, WireStripe
from .geometry import cross, difference, dot, linear_combination, magnitude, unit
from .parallel import RoutePreview, Vector3
from .smooth import sample_centerline


# noinspection DuplicatedCode
def build_stripe_mesh(
    route: RoutePreview,
    stripe: WireStripe,
    body_radius_mm: float,
) -> tuple[tuple[Vector3, ...], list[int]]:
    """
    Build a triangulated surface band around a routed circular body.
    """
    if body_radius_mm <= 0:
        return (), []
    points, tangents, normals, distances = _stripe_frame_samples(route, stripe, body_radius_mm)
    if len(points) < 2:
        return (), []
    surface_radius = body_radius_mm + max(0.02, body_radius_mm * 0.01)
    half_angle = min(stripe.width_mm / (2.0 * surface_radius), math.pi * 0.49)
    width_segments = max(1, math.ceil(half_angle * 2.0 / math.radians(10.0)))
    section_size = width_segments + 1
    vertices: list[Vector3] = []
    for point, tangent, normal, distance in zip(points, tangents, normals, distances):
        center_angle = math.radians(stripe.angle_deg)
        if stripe.pattern is StripePattern.HELICAL and stripe.repeat_mm is not None:
            center_angle += math.tau * distance / stripe.repeat_mm
        for width_index in range(section_size):
            angle = center_angle - half_angle + 2.0 * half_angle * width_index / width_segments
            vertices.append(
                point.translated(_stripe_radial(tangent, normal, angle), surface_radius)
            )
    indices: list[int] = []
    for index in range(len(points) - 1):
        midpoint = (distances[index] + distances[index + 1]) / 2.0
        if (
            stripe.pattern is StripePattern.DASHED
            and stripe.repeat_mm is not None
            and midpoint % stripe.repeat_mm >= stripe.repeat_mm / 2.0
        ):
            continue
        section_start = index * section_size
        next_section = section_start + section_size
        for width_index in range(width_segments):
            left = section_start + width_index
            next_left = next_section + width_index
            indices.extend((left, left + 1, next_left, left + 1, next_left + 1, next_left))
    return tuple(vertices), indices


# noinspection DuplicatedCode
def _stripe_frame_samples(
    route: RoutePreview,
    stripe: WireStripe,
    body_radius_mm: float,
) -> tuple[
    tuple[Vector3, ...],
    tuple[Vector3, ...],
    tuple[Vector3, ...],
    tuple[float, ...],
]:
    """
    Sample the centerline and parallel-transport a circumferential frame.
    """
    tolerance = min(0.005, max(0.0005, body_radius_mm * 0.005))
    points = sample_centerline(route, tolerance)
    step_mm = 1.0
    if stripe.pattern is StripePattern.HELICAL and stripe.repeat_mm is not None:
        step_mm = min(step_mm, stripe.repeat_mm / 32.0)
    elif stripe.repeat_mm is not None:
        step_mm = min(step_mm, stripe.repeat_mm / 8.0)
    points = _densify_polyline(points, max(step_mm, 0.01))
    if len(points) < 2:
        return (), (), (), ()
    tangents = tuple(_polyline_tangent(points, index) for index in range(len(points)))
    normal = _initial_normal(tangents[0])
    normals = [normal]
    for tangent in tangents[1:]:
        projected = Vector3(
            normal.x - tangent.x * dot(normal, tangent),
            normal.y - tangent.y * dot(normal, tangent),
            normal.z - tangent.z * dot(normal, tangent),
        )
        normal = unit(projected) if magnitude(projected) > 1e-9 else _initial_normal(tangent)
        normals.append(normal)
    distances = [0.0]
    for start, end in zip(points, points[1:]):
        distances.append(distances[-1] + magnitude(difference(end, start)))
    return points, tangents, tuple(normals), tuple(distances)


def _densify_polyline(points: tuple[Vector3, ...], step_mm: float) -> tuple[Vector3, ...]:
    """
    Insert linear samples so procedural repeats remain visible on straight spans.
    """
    dense = [points[0]]
    for start, end in zip(points, points[1:]):
        delta = difference(end, start)
        divisions = max(1, math.ceil(magnitude(delta) / step_mm))
        for index in range(1, divisions + 1):
            fraction = index / divisions
            dense.append(
                Vector3(
                    start.x + delta.x * fraction,
                    start.y + delta.y * fraction,
                    start.z + delta.z * fraction,
                )
            )
    return tuple(dense)


# noinspection DuplicatedCode
def _polyline_tangent(points: tuple[Vector3, ...], index: int) -> Vector3:
    """
    Return a centered tangent for one sampled point.
    """
    if index == 0:
        return unit(difference(points[1], points[0]))
    if index == len(points) - 1:
        return unit(difference(points[-1], points[-2]))
    return unit(difference(points[index + 1], points[index - 1]))


def _initial_normal(tangent: Vector3) -> Vector3:
    """
    Choose a deterministic perpendicular route-start direction.
    """
    axis = min(
        (Vector3(1.0, 0.0, 0.0), Vector3(0.0, 1.0, 0.0), Vector3(0.0, 0.0, 1.0)),
        key=lambda candidate: abs(dot(tangent, candidate)),
    )
    return unit(cross(tangent, axis))


def _stripe_radial(tangent: Vector3, normal: Vector3, angle: float) -> Vector3:
    """
    Rotate a transported normal around the centerline tangent.
    """
    binormal = unit(cross(tangent, normal))
    return linear_combination(normal, math.cos(angle), binormal, math.sin(angle))
