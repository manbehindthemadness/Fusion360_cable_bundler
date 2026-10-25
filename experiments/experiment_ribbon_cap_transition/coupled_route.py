"""
Connect fixed ribbon poses with three coupled bend/rotation motions in one pass.

Only three segment lengths are solved after a fixed orientation factorization.
Singular systems, negative lengths and hard findings are retained as failures;
no alternate decomposition, target movement, length repair or refinement exists.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, lerp, magnitude, unit

from .biarc_route import biarc
from .coupled_motion import ZERO, AngleLaw, CoupledMotion, orientation_angles
from .endpoint_first import EndpointCase, controls, endpoint_cases
from .endpoint_lateral import lateral_cases
from .endpoint_reference import reference_cases


class CoupledRejection(ValueError):
    """
    Identify a known limitation of the fixed motion basis, distinct from a bug.
    """


def cases() -> tuple[EndpointCase, ...]:
    """
    Freeze two triggers, two controls and three different collateral configurations.

    Collateral cases retain existing quarter-plus, quarter-minus and half-oblique
    endpoint poses; they test roll signs, displaced endpoints and oblique approach.
    All seven are examined development inputs, not untouched validation cases.
    """
    original = endpoint_cases()
    return (
        reference_cases()[1],
        lateral_cases()[-1],
        original[0],
        reference_cases()[0],
        *original[1:],
    )


def construct(case: EndpointCase) -> tuple[CoupledMotion, ...]:
    """
    Solve orientation first and three positive travel lengths by one linear solve.

    Compatible straight and constant-width circular biarcs are exact control
    branches. They retain their original geometry rather than being replaced by
    an unnecessary helical route. General pose coverage is explicitly limited by
    the chosen three-motion basis; failure is not evidence of physical infeasibility.
    """
    controls(case)  # Reuse fixed-pose/dimension validation, not its polynomial path.
    chord = difference(case.end, case.start)
    if (
        magnitude(difference(case.start_width, case.end_width)) <= 1e-10
        and abs(dot(chord, case.start_width)) <= 1e-10
    ):
        arcs = biarc(case)
        if all(
            arc.normal is None or abs(dot(arc.normal, case.start_width)) >= 1 - 1e-10
            for arc in arcs
        ):
            return tuple(
                CoupledMotion(
                    arc.start,
                    arc.tangent(0),
                    case.start_width,
                    arc.normal if arc.normal is not None else case.start_width,
                    arc.sweep,
                    arc.radius * arc.sweep
                    if math.isfinite(arc.radius)
                    else magnitude(difference(arc.end, arc.start)),
                    AngleLaw.LINEAR,
                )
                for arc in arcs
            )
    angles = orientation_angles(
        case.start_tangent, case.start_width, case.end_tangent, case.end_width
    )
    tangent, width = case.start_tangent, case.start_width
    prototypes = []
    for angle, sign in zip(angles, (1, -1, 1)):
        axis = unit(tangent.translated(width, sign))
        motion = CoupledMotion(ZERO, tangent, width, axis, angle, 1)
        prototypes.append(motion)
        tangent, width = motion.frame(1)
    columns = tuple(motion.displacement(1) for motion in prototypes)
    determinant = dot(columns[0], cross(columns[1], columns[2]))
    if abs(determinant) <= 1e-10:
        raise CoupledRejection(
            "Fixed three-motion position system is singular; no alternate branch."
        )
    lengths = (
        dot(chord, cross(columns[1], columns[2])) / determinant,
        dot(columns[0], cross(chord, columns[2])) / determinant,
        dot(columns[0], cross(columns[1], chord)) / determinant,
    )
    if min(lengths) <= 1e-8:
        raise CoupledRejection(
            f"Fixed three-motion solve requires nonpositive travel {lengths}; no repair."
        )
    result, start = [], case.start
    for prototype, length in zip(prototypes, lengths):
        motion = replace(prototype, start=start, length=length)
        result.append(motion)
        start = motion.jet(1)[0]
    if (
        max(
            magnitude(difference(start, case.end)),
            magnitude(difference(tangent, case.end_tangent)),
            magnitude(difference(width, case.end_width)),
        )
        > 1e-8
    ):
        raise RuntimeError("Coupled integration failed fixed endpoint closure; no repair.")
    return tuple(result)


def audit(case: EndpointCase, motions: tuple[CoupledMotion, ...]) -> dict[str, Any]:
    """
    Separate analytic frame/curvature facts from sampled lane and envelope checks.

    No native, material, nearest-lane clearance or elastic compliance is inferred.
    Even a clean numerical row remains unresolved until the required native audits.
    """
    reach = math.hypot(
        case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1, case.diameter_mm / 2
    )
    center = lerp(case.start, case.end, 0.5)
    maximum_curvature = max(m.maximum_curvature() for m in motions)
    minimum_lane_radius, maximum_distance, maximum_width_bending = math.inf, 0.0, 0.0
    lane_lengths = [0.0] * case.lines
    for motion in motions:
        for index in range(65):
            u = index / 64
            tangent, width = motion.frame(u)
            p, _, acceleration = motion.jet(u)
            maximum_distance = max(maximum_distance, magnitude(difference(p, center)))
            maximum_width_bending = max(
                maximum_width_bending, abs(dot(acceleration, width)) / motion.length**2
            )
            _, rate, angular_acceleration = motion.angle_jet(u)
            width_rate = cross(motion.axis, width)
            for lane in range(case.lines):
                offset = (lane - (case.lines - 1) / 2) * case.diameter_mm
                # Lane curvature depends on frame derivatives, not its integrated position.
                velocity = ZERO.translated(tangent, motion.length).translated(
                    width_rate, offset * rate
                )
                weight = 1 if index in (0, 64) else (4 if index % 2 else 2)
                lane_lengths[lane] += weight * magnitude(velocity) / 192
                lane_acceleration = (
                    ZERO.translated(cross(motion.axis, tangent), motion.length * rate)
                    .translated(width_rate, offset * angular_acceleration)
                    .translated(cross(motion.axis, width_rate), offset * rate * rate)
                )
                numerator = magnitude(cross(velocity, lane_acceleration))
                if numerator > 1e-12:
                    minimum_lane_radius = min(
                        minimum_lane_radius, magnitude(velocity) ** 3 / numerator
                    )
    jumps = [
        magnitude(
            difference(
                ZERO.translated(a.jet(1)[2], 1 / a.length**2),
                ZERO.translated(b.jet(0)[2], 1 / b.length**2),
            )
        )
        for a, b in zip(motions, motions[1:])
    ]
    findings = []
    if maximum_curvature * reach > 0.8:
        findings.append("analytic macaroni curvature limit")
    if maximum_distance + reach > 2.5 * case.lines * case.diameter_mm:
        findings.append("sampled occupied sphere limit")
    if minimum_lane_radius < 3 * case.diameter_mm:
        findings.append("sampled per-lane radius")
    if max(jumps, default=0) > 1e-8:
        findings.append("curvature jump")
    spread = (max(lane_lengths) - min(lane_lengths)) / max(lane_lengths)
    return {
        "lengths_mm": [m.length for m in motions],
        "angles_radians": [m.angle for m in motions],
        "analytic_maximum_curvature_ratio": maximum_curvature * reach,
        "sampled_minimum_lane_radius_mm": minimum_lane_radius,
        "sampled_occupied_sphere_reach_mm": maximum_distance + reach,
        "sphere_radius_mm": 2.5 * case.lines * case.diameter_mm,
        "sampled_maximum_width_axis_curvature": maximum_width_bending,
        "analytic_width_axis_rule": "zero by axis construction, up to floating-point arithmetic",
        "maximum_curvature_join_jump": max(jumps, default=0),
        "endpoint_position_error_mm": magnitude(difference(motions[-1].jet(1)[0], case.end)),
        "findings": findings,
        "sampled_lane_lengths_mm": lane_lengths,
        "sampled_lane_length_spread": spread,
        "warnings": ["sampled lane length spread exceeds 1% goal"] if spread > 0.01 else [],
        "overall": "failed" if findings else "unresolved",
        "unmeasured": [
            "continuous lane radius/clearance/containment",
            "material strain/equilibrium",
            "native spline banking and complete compliance",
        ],
    }


def spline_controls(
    motions: tuple[CoupledMotion, ...], offset: float
) -> tuple[tuple[Vector3, ...], tuple[float, ...]]:
    """
    Produce 32 cubic Hermite spans per motion for a visible diagnostic curve.

    Positions/derivatives come from the coupled motion. The cubic representation
    approximates that motion and does not inherit its exact banking invariant.
    Internal knots have multiplicity three; no Fusion fit interpolation is used.
    """
    points = [motions[0].jet(0, offset)[0]]
    count = 0
    for motion in motions:
        for index in range(32):
            p, v, _ = motion.jet(index / 32, offset)
            q, w, _ = motion.jet((index + 1) / 32, offset)
            points.extend((p.translated(v, 1 / 96), q.translated(w, -1 / 96), q))
            count += 1
    knots = (0.0,) * 4 + tuple(i / count for i in range(1, count) for _ in range(3)) + (1.0,) * 4
    return tuple(points), knots
