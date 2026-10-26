"""
Construct one fixed-target boundary before permitting companion ribbon paths.

A degree-seven boundary fixes endpoint position,tangent,binormal and zero
terminal ruling slope. Its Frenet frame supplies a developable material map.
Sampled compatibility can reject the family;arrival alone never establishes a
valid ribbon. Permanent material side A stays the reference,no event handoffs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit

from .coupled_motion import ZERO
from .endpoint_first import EndpointCase, controls, derivative, evaluate
from .material_allocation import MaterialPlan

STATIONS = 257
TOLERANCE_MM = 1e-8


@dataclass(frozen=True)
class BoundaryCurve:
    """
    Cache exact polynomial derivatives for a single endpoint-constrained edge.
    """

    points: tuple[Vector3, ...]
    derivatives: tuple[tuple[Vector3, ...], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """
        Retain derivatives through order four without repeated control conversion.
        """
        if len(self.points) not in (8, 10, 12):
            raise ValueError("Boundary requires degree seven,nine or eleven.")
        rows = [self.points]
        for _ in range(4):
            rows.append(derivative(rows[-1]))
        object.__setattr__(self, "derivatives", tuple(rows))

    def jet(self, u: float) -> tuple[Vector3, ...]:
        """
        Return position and first four parameter derivatives at a closed fraction.
        """
        return tuple(evaluate(row, u) for row in self.derivatives)


@dataclass(frozen=True)
class BoundaryFrame:
    """
    Retain a regular edge's frame,ruling ratio and parameter derivatives.
    """

    position: Vector3
    tangent: Vector3
    width: Vector3
    slope: float
    slope_rate: float
    speed: float
    curvature: float

    def lane(self, offset_mm: float) -> tuple[Vector3, Vector3]:
        """
        Return a material lane point and parameter velocity from boundary A.

        Offsets are0 at A,-half_width at center,-full_width at B. The map is
        R=e+q*(W+eta*T),with material coordinate x=s+q*eta. Its derivative is
        (speed+q*eta_u)*T;positive Jacobian is required separately across width.
        """
        point = self.position.translated(self.width, offset_mm).translated(
            self.tangent, offset_mm * self.slope
        )
        velocity = ZERO.translated(self.tangent, self.speed + offset_mm * self.slope_rate)
        return point, velocity


@dataclass(frozen=True)
class EdgeCandidate:
    """
    Keep an edge and explicit gate results without authorizing native solids.
    """

    case: EndpointCase
    curve: BoundaryCurve | None
    retained_control: MaterialPlan | None
    companion_allowed: bool
    metrics: dict[str, Any]


def _end_controls(
    point: Vector3, velocity: Vector3, acceleration: Vector3, jerk: Vector3
) -> tuple[Vector3, ...]:
    """
    Convert endpoint derivatives into the first four degree-seven controls.
    """
    return (
        point,
        point.translated(velocity, 1 / 7),
        point.translated(velocity, 2 / 7).translated(acceleration, 1 / 42),
        point.translated(velocity, 3 / 7)
        .translated(acceleration, 1 / 14)
        .translated(jerk, 1 / 210),
    )


def boundary(
    case: EndpointCase, endpoint_ratio: float | None = None, speed_ratio: float = 1.0
) -> BoundaryCurve:
    """
    Build one A-edge polynomial with prescribed endpoint poses,no search or tuning.

    Speed equals A-edge chord length D;acceleration is D*(W cross T),jerk=-D*T.
    Thus endpoint binormal=W and torsion=0 in exact arithmetic. Nonzero endpoint
    curvature is1/D,a declared prototype choice rather than measured mechanics.
    An optional fixed endpoint curvature*reach ratio supports controlled shape
    comparisons;it must lie strictly between0 and the retained0.8center budget.
    A positive speed ratio changes interior travel while retaining endpoint
    positions,directions and zero torsion;the original ratio1 arithmetic remains.
    """
    controls(case)
    half_width = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    start = case.start.translated(case.start_width, half_width)
    end = case.end.translated(case.end_width, half_width)
    distance = magnitude(difference(end, start))
    if distance <= TOLERANCE_MM:
        raise ValueError("Boundary endpoints coincide;no fallback.")
    if endpoint_ratio is not None and (
        not math.isfinite(endpoint_ratio) or not 0 < endpoint_ratio < 0.8
    ):
        raise ValueError("Endpoint curvature ratio must lie strictly within(0,0.8).")
    reach = math.hypot(half_width, case.diameter_mm / 2)
    if not math.isfinite(speed_ratio) or speed_ratio <= 0:
        raise ValueError("Boundary speed ratio must be finite and positive.")
    speed = distance * speed_ratio
    curvature = 1 / distance if endpoint_ratio is None else endpoint_ratio / reach
    unchanged = endpoint_ratio is None and speed_ratio == 1
    acceleration_scale = distance if unchanged else speed**2 * curvature
    jerk_scale = distance if unchanged else speed**3 * curvature**2
    first = _end_controls(
        start,
        ZERO.translated(case.start_tangent, speed),
        ZERO.translated(cross(case.start_width, case.start_tangent), acceleration_scale),
        ZERO.translated(case.start_tangent, -jerk_scale),
    )
    reverse = _end_controls(
        end,
        ZERO.translated(case.end_tangent, -speed),
        ZERO.translated(cross(case.end_width, case.end_tangent), acceleration_scale),
        ZERO.translated(case.end_tangent, jerk_scale),
    )
    return BoundaryCurve(first + tuple(reversed(reverse)))


def frame(curve: BoundaryCurve, u: float) -> BoundaryFrame:
    """
    Recover binormal width and eta=torsion/curvature with its exact derivative.

    Inflections and vanishing speed reject;there is no invented frame or twist
    through a singular Frenet point. These are numerical guards,not strain limits.
    """
    position, velocity, acceleration, jerk, snap = curve.jet(u)
    speed = magnitude(velocity)
    product = cross(velocity, acceleration)
    norm = magnitude(product)
    if speed <= 1e-10 or norm <= 1e-10:
        raise ValueError("Boundary has singular speed or bend frame.")
    tangent, width = unit(velocity), unit(product)
    numerator = dot(product, jerk)
    slope = numerator * speed**3 / norm**3
    speed_rate = dot(velocity, acceleration) / speed
    norm_rate = dot(product, cross(velocity, jerk)) / norm
    slope_rate = dot(product, snap) * speed**3 / norm**3 + slope * (
        3 * speed_rate / speed - 3 * norm_rate / norm
    )
    return BoundaryFrame(position, tangent, width, slope, slope_rate, speed, norm / speed**3)


def edge_gate(
    case: EndpointCase, start: Vector3, end: Vector3, t0: Vector3, t1: Vector3
) -> dict[str, Any]:
    """
    Measure permanent A-edge arrival before any companion reference calculation.
    """
    half_width = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    position_error = max(
        magnitude(difference(start, case.start.translated(case.start_width, half_width))),
        magnitude(difference(end, case.end.translated(case.end_width, half_width))),
    )
    tangent_error = max(
        magnitude(difference(unit(t0), case.start_tangent)),
        magnitude(difference(unit(t1), case.end_tangent)),
    )
    return {
        "edge_position_error_mm": position_error,
        "edge_tangent_error": tangent_error,
        "edge_gate_passed": max(position_error, tangent_error) <= TOLERANCE_MM,
    }


def construct(
    case: EndpointCase,
    retained_control: MaterialPlan | None = None,
    *,
    endpoint_ratio: float | None = None,
    speed_ratio: float = 1.0,
    reference_curve: BoundaryCurve | None = None,
) -> EdgeCandidate:
    """
    Check edge arrival,then at most257stations of full-width compatibility.

    Existing exact controls may be supplied for comparison;they are not rebuilt
    or relabeled as new solver successes. For new edges,positive sampled
    Jacobians precede companion derivation. Center macaroni,three-guide radius,
    containment and terminal poses then gate native companion paths. Sampling
    is not a continuous certificate,elastic model or complete cable audit.
    The optional endpoint ratio is fixed before comparison,never adapted from
    this candidate's outcomes. Retained controls ignore shape-profile changes.
    Speed ratio changes interior travel without any post-result target movement.
    A supplied reference curve is assessed without reconstruction or endpoint
    repair. It cannot be combined with a retained analytic control.
    """
    started = perf_counter()
    if retained_control is not None and reference_curve is not None:
        raise ValueError("Supply either a retained control or a boundary curve.")
    curve = None if retained_control is not None else reference_curve
    if curve is None and retained_control is None:
        curve = boundary(case, endpoint_ratio, speed_ratio)
    half_width = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    if retained_control is not None:
        strip = retained_control.strip
        p0, v0, _ = strip.jet(0, half_width)
        p1, v1, _ = strip.jet(strip.length_mm, half_width)
    else:
        assert curve is not None
        p0, v0, *_ = curve.jet(0)
        p1, v1, *_ = curve.jet(1)
    metrics = edge_gate(case, p0, p1, v0, v1)
    metrics["edge_seconds"] = perf_counter() - started
    metrics.update(
        {
            "findings": [],
            "compatibility_stations": 0,
            "control_reused": retained_control is not None,
        }
    )
    if not metrics["edge_gate_passed"]:
        metrics["findings"].append("A-edge endpoint gate failed")
        return EdgeCandidate(case, curve, retained_control, False, metrics)
    started = perf_counter()
    try:
        center = case.start.translated(difference(case.end, case.start), 0.5)
        reach = math.hypot(half_width, case.diameter_mm / 2)
        minimum_jacobian, minimum_radius, maximum_ratio, occupied = 1.0, math.inf, 0.0, 0.0
        if retained_control is None:
            assert curve is not None
            frames: list[BoundaryFrame] = []
            worst_fraction = 0.0
            for index in range(STATIONS):
                observed = frame(curve, index / (STATIONS - 1))
                metrics["compatibility_stations"] += 1
                jacobian = min(1.0, 1 - 2 * half_width * observed.slope_rate / observed.speed)
                if jacobian < minimum_jacobian:
                    minimum_jacobian = jacobian
                    worst_fraction = index / (STATIONS - 1)
                frames.append(observed)
            metrics["minimum_sampled_material_jacobian"] = minimum_jacobian
            metrics["minimum_jacobian_fraction"] = worst_fraction
            metrics["maximum_abs_ruling_slope"] = max(abs(observed.slope) for observed in frames)
            metrics["minimum_sampled_edge_curvature"] = min(
                observed.curvature for observed in frames
            )
            width_error = max(
                magnitude(difference(frames[0].width, case.start_width)),
                magnitude(difference(frames[-1].width, case.end_width)),
            )
            metrics["terminal_width_error"] = width_error
            metrics["terminal_ruling_slopes"] = (frames[0].slope, frames[-1].slope)
            if width_error > 1e-8 or max(abs(frames[0].slope), abs(frames[-1].slope)) > 1e-8:
                metrics["findings"].append("terminal material frame incompatible")
            if minimum_jacobian <= 0:
                metrics["findings"].append(
                    "sampled finite-width material coordinates reverse or collapse"
                )
            if metrics["findings"]:
                return EdgeCandidate(case, curve, None, False, metrics)
            for observed in frames:
                for offset in (0.0, -half_width, -2 * half_width):
                    point, _ = observed.lane(offset)
                    jacobian = 1 + offset * observed.slope_rate / observed.speed
                    curvature = observed.curvature / jacobian
                    minimum_radius = min(minimum_radius, 1 / curvature)
                    if offset == -half_width:
                        maximum_ratio = max(maximum_ratio, curvature * reach)
                    occupied = max(
                        occupied, magnitude(difference(point, center)) + case.diameter_mm / 2
                    )
            terminal_error = max(
                magnitude(difference(frames[0].lane(-half_width)[0], case.start)),
                magnitude(difference(frames[-1].lane(-half_width)[0], case.end)),
                magnitude(
                    difference(
                        frames[0].lane(-2 * half_width)[0],
                        case.start.translated(case.start_width, -half_width),
                    )
                ),
                magnitude(
                    difference(
                        frames[-1].lane(-2 * half_width)[0],
                        case.end.translated(case.end_width, -half_width),
                    )
                ),
            )
        else:
            strip = retained_control.strip
            for index in range(STATIONS):
                metrics["compatibility_stations"] += 1
                for offset in (-half_width, 0.0, half_width):
                    point, _, acceleration = strip.jet(
                        strip.length_mm * index / (STATIONS - 1), offset
                    )
                    curvature = magnitude(acceleration)
                    if curvature > 0:
                        minimum_radius = min(minimum_radius, 1 / curvature)
                    if offset == 0:
                        maximum_ratio = max(maximum_ratio, curvature * reach)
                    occupied = max(
                        occupied, magnitude(difference(point, center)) + case.diameter_mm / 2
                    )
            terminal_error = retained_control.endpoint_gap_mm
        metrics.update(
            {
                "sampled_minimum_lane_radius_mm": minimum_radius,
                "sampled_center_macaroni_ratio": maximum_ratio,
                "sampled_occupied_sphere_reach_mm": occupied,
                "sphere_radius_mm": 2.5 * case.lines * case.diameter_mm,
                "companion_endpoint_error_mm": terminal_error,
            }
        )
        if maximum_ratio > 0.8 or minimum_radius < 3 * case.diameter_mm:
            metrics["findings"].append("sampled retained curvature limit")
        if occupied > metrics["sphere_radius_mm"]:
            metrics["findings"].append("sampled three-guide sphere limit")
        if terminal_error > 1e-8:
            metrics["findings"].append("derived companion endpoint mismatch")
        return EdgeCandidate(case, curve, retained_control, not metrics["findings"], metrics)
    except ValueError as error:
        metrics["findings"].append(str(error))
        return EdgeCandidate(case, curve, retained_control, False, metrics)
    finally:
        metrics["compatibility_seconds"] = perf_counter() - started
