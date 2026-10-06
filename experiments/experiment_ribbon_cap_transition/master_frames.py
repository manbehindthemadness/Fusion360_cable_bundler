"""
Sample exact master curves and choose one bounded, shared ribbon bank field.

The fixed arc-length lookup and greedy orientation pass are deterministic, not a
route search or an optimal bank solver. Sampled limits are not native certificates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import (
    Vector3,
    cross,
    difference,
    dot,
    magnitude,
    unit,
)
from cable_bundler.routing.parallel import RoutePreview
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame

from .full_turn import FullTurnDiagnostic

LOOKUP_INTERVALS_PER_CURVE = 128
SECTIONS = 32
QUINTIC_MAXIMUM_SLOPE = 1.875


@dataclass(frozen=True)
class MasterScaffold:
    """
    Keep exact node geometry, analytic curvature and bounded roll decisions.

    Distances are conservative chord-length coordinates, not exact arc length.
    The bank-rate policy borrows the existing width-scaled rate but reserves the
    quintic interpolation slope. It is a policy bound, not a Fusion-derived law.
    Minimal-rotation node transport approximates continuous parallel transport.
    """

    frames: tuple[RibbonFrame, ...]
    curvature_vectors: tuple[Vector3, ...]
    distances_mm: tuple[float, ...]
    bank_angles_radians: tuple[float, ...]
    bank_rate_limit_radians_per_mm: float


def transport_width(width: Vector3, previous: Vector3, tangent: Vector3) -> Vector3:
    """
    Apply the shortest tangent rotation without introducing an arbitrary roll.

    Reject antiparallel tangents; there is no unique shortest rotation axis.
    """
    axis = cross(previous, tangent)
    sine, cosine = magnitude(axis), max(-1.0, min(1.0, dot(previous, tangent)))
    if sine <= 1e-10:
        if cosine < 0:
            raise UnsafeRibbon("Master curve transport has antiparallel node tangents.")
        return width
    axis = unit(axis)
    side = cross(axis, width)
    rotated = Vector3(
        width.x * cosine + side.x * sine + axis.x * dot(axis, width) * (1 - cosine),
        width.y * cosine + side.y * sine + axis.y * dot(axis, width) * (1 - cosine),
        width.z * cosine + side.z * sine + axis.z * dot(axis, width) * (1 - cosine),
    )
    return unit(rotated)


def _angle(width: Vector3, target: Vector3, tangent: Vector3) -> float:
    """
    Measure signed roll about one shared node tangent.
    """
    return math.atan2(dot(cross(width, target), tangent), dot(width, target))


def sampled_roll(frames: tuple[RibbonFrame, ...]) -> dict[str, float]:
    """
    Measure unwrapped node roll and average span rate relative to tangent transport.

    Each principal increment must be below pi to resolve winding; the fixed
    32-node full-turn field meets this condition. This is finite-node evidence,
    not a bound on native skin twist or continuous transport/interpolation error.
    """
    if len(frames) < 3:
        raise ValueError("Sampled roll requires at least three frames.")
    roll = 0.0
    maximum_rate = 0.0
    for left, right in zip(frames, frames[1:]):
        span = magnitude(difference(right.origin, left.origin))
        if not math.isfinite(span) or span <= 1e-8:
            raise ValueError("Sampled roll requires finite positive frame spans.")
        width = transport_width(left.width, left.tangent, right.tangent)
        increment = _angle(width, right.width, right.tangent)
        roll += increment
        maximum_rate = max(maximum_rate, abs(increment) / span)
    return {
        "net_roll_degrees": math.degrees(roll),
        "maximum_average_rate_radians_per_mm": maximum_rate,
    }


def bounded_bank_angles(
    preferred: tuple[float, ...],
    distances_mm: tuple[float, ...],
    end_angle: float,
    rate_limit: float,
) -> tuple[float, ...]:
    """
    Make one forward bank pass with reserved reachability to the fixed end roll.

    Node increments reserve 1.875 times their average rate for quintic easing.
    No retries, lattice search, target movement or full-turn fallback occurs.
    This constrains authored roll only; transport error and strain remain unknown.
    """
    if len(preferred) != len(distances_mm) or len(preferred) < 3:
        raise ValueError("Bank decisions require matching three-node arrays.")
    values = (*preferred, *distances_mm, end_angle, rate_limit)
    if any(not math.isfinite(value) for value in values) or rate_limit <= 0:
        raise ValueError("Bank coordinates and rate must be finite with positive rate.")
    if distances_mm[0] != 0 or any(b <= a for a, b in zip(distances_mm, distances_mm[1:])):
        raise ValueError("Bank distances must start at zero and increase strictly.")
    allowed_rate = rate_limit / QUINTIC_MAXIMUM_SLOPE
    total = distances_mm[-1]
    if abs(end_angle) > allowed_rate * total + 1e-10:
        raise UnsafeRibbon("Fixed end roll exceeds the master bank-distance budget.")
    angles = [0.0]
    for index in range(1, len(preferred) - 1):
        step = allowed_rate * (distances_mm[index] - distances_mm[index - 1])
        remaining = allowed_rate * (total - distances_mm[index])
        lower = max(angles[-1] - step, end_angle - remaining)
        upper = min(angles[-1] + step, end_angle + remaining)
        if lower > upper + 1e-10:
            raise UnsafeRibbon("No reachable shared bank interval; no retry.")
        target = preferred[index]
        target += 2 * math.pi * round((angles[-1] - target) / (2 * math.pi))
        angles.append(max(lower, min(upper, target)))
    angles.append(end_angle)
    return tuple(angles)


def master_scaffold(
    route: RoutePreview,
    start_width: Vector3,
    end_width: Vector3,
    ribbon_width_mm: float,
    *,
    twist: FullTurnDiagnostic | None = None,
) -> MasterScaffold:
    """
    Evaluate 32 exact curve nodes from a fixed 128-interval-per-curve length table.

    Positions, tangents and curvature are evaluated analytically at lookup-derived
    parameters, never interpolated along the preview polyline. At each node the
    preferred width lies along the bend binormal, with its nearest signed branch.
    A zero-curvature node retains transported width rather than inventing a bend.
    Explicit full-turn diagnostics use their prescribed field instead of the
    bounded bank pass; the original rate remains recorded, not asserted satisfied.
    """
    if not route.curves or not math.isfinite(ribbon_width_mm) or ribbon_width_mm <= 0:
        raise ValueError("Master scaffold requires curves and positive finite width.")
    table: list[tuple[float, int, float]] = [(0.0, 0, 0.0)]
    total = 0.0
    for curve_index, curve in enumerate(route.curves):
        previous = curve.start
        for index in range(1, LOOKUP_INTERVALS_PER_CURVE + 1):
            parameter = index / LOOKUP_INTERVALS_PER_CURVE
            point = curve.point(parameter)
            total += magnitude(difference(point, previous))
            table.append((total, curve_index, parameter))
            previous = point
    if total <= 1e-8:
        raise ValueError("Master scaffold has no usable route length.")
    nodes: list[RibbonFrame] = []
    curvatures = []
    segment = 0
    width = unit(start_width)
    for index in range(SECTIONS):
        distance = total * index / (SECTIONS - 1)
        while segment < len(table) - 2 and table[segment + 1][0] < distance:
            segment += 1
        left_distance, left_curve, left_parameter = table[segment]
        right_distance, curve_index, right_parameter = table[segment + 1]
        if left_curve != curve_index:
            left_parameter = 0.0
        span = right_distance - left_distance
        parameter = left_parameter + (right_parameter - left_parameter) * (
            (distance - left_distance) / span if span > 1e-12 else 0
        )
        parameter = max(0.0, min(1.0, parameter))
        curve = route.curves[curve_index]
        velocity = curve.derivative(parameter)
        tangent = unit(velocity)
        if nodes:
            width = transport_width(width, nodes[-1].tangent, tangent)
        elif abs(dot(width, tangent)) > 1e-8:
            raise ValueError("Master start width is not in its cap plane.")
        acceleration = curve.second_derivative(parameter)
        normal_acceleration = acceleration.translated(tangent, -dot(acceleration, tangent))
        speed_squared = magnitude(velocity) ** 2
        curvatures.append(
            Vector3(
                normal_acceleration.x / speed_squared,
                normal_acceleration.y / speed_squared,
                normal_acceleration.z / speed_squared,
            )
        )
        nodes.append(
            RibbonFrame(curve.point(parameter), tangent, width, unit(cross(tangent, width)))
        )
    distances = [0.0]
    for left, right in zip(nodes, nodes[1:]):
        distances.append(distances[-1] + magnitude(difference(right.origin, left.origin)))
    target_width = unit(end_width)
    if abs(dot(target_width, nodes[-1].tangent)) > 1e-8:
        raise ValueError("Master end width is not in its cap plane.")
    end_angle = _angle(nodes[-1].width, target_width, nodes[-1].tangent)
    preferred = []
    for frame, curvature in zip(nodes, curvatures):
        if magnitude(curvature) <= 1e-10:
            preferred.append(0.0)
            continue
        desired = unit(cross(frame.tangent, curvature))
        if dot(desired, frame.width) < 0:
            desired = Vector3(-desired.x, -desired.y, -desired.z)
        preferred.append(_angle(frame.width, desired, frame.tangent))
    rate_limit = 2 * math.pi / (3 * ribbon_width_mm)
    angles = (
        bounded_bank_angles(tuple(preferred), tuple(distances), end_angle, rate_limit)
        if twist is None
        else twist.angles(tuple(distances), end_angle)
    )
    banked = []
    for index, (frame, angle) in enumerate(zip(nodes, angles)):
        bank_width = Vector3(
            frame.width.x * math.cos(angle) + frame.thickness.x * math.sin(angle),
            frame.width.y * math.cos(angle) + frame.thickness.y * math.sin(angle),
            frame.width.z * math.cos(angle) + frame.thickness.z * math.sin(angle),
        )
        if index == len(nodes) - 1:
            bank_width = target_width
        banked.append(
            RibbonFrame(
                frame.origin,
                frame.tangent,
                unit(bank_width),
                unit(cross(frame.tangent, bank_width)),
            )
        )
    return MasterScaffold(tuple(banked), tuple(curvatures), tuple(distances), angles, rate_limit)
