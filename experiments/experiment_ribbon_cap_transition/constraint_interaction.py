"""
Inspect cached routing objectives and spatial usage without fitting new geometry.

Requirements: retained compatible-chart paths and matching immutable Evidence.
Rendering is performed separately in the owned idle Fusion design. Surface
curvature is a developable-model research diagnostic, not an acceptance rule.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from devtools.ribbon_analysis.api import Evidence

from .director_path_contracts import FramedPath
from .director_route_objective import free_penalties
from .director_shooting import residual
from .endpoint_first import EndpointCase


@dataclass(frozen=True)
class Station:
    """
    Retain jointly sampled local geometry, sphere occupancy and remaining arrival.
    """

    u: float
    point: Vector3
    sphere_use: float
    center_use: float
    minimum_j: float
    surface_curvature_per_mm: float | None
    target_distance_mm: float


@dataclass(frozen=True)
class Inspection:
    """
    Keep final-objective components distinct from unavailable rejected-step causes.
    """

    evidence_fingerprint: str
    stations: tuple[Station, ...]
    objective: tuple[tuple[str, float], ...]
    fine_scores: tuple[float, ...]
    sphere_radius_mm: float
    fine_unchanged_rounds: int


def inspect(
    path: FramedPath,
    case: EndpointCase,
    evidence: Evidence,
    metrics: Mapping[str, Any],
    checkpoint: Callable[[], None],
) -> Inspection:
    """
    Evaluate257fixed stations and the existing33station final objective once.

    No transport, derivative probes, fitting, threshold changes or repairs occur.
    Occupancy uses frozen A/center/B cubics with the existing thickness allowance.
    Surface principal curvature abs(k)*(1+eta**2)/J uses the retained intrinsic
    model, following Dias/Audoly2014equations15-16 with zero geodesic curvature.
    Missing/nonpositive J is unmeasured; no surface-curvature limit is adopted.
    """
    guides = {guide.number: guide for guide in evidence.guides}
    midpoint = case.start.translated(difference(case.end, case.start), 0.5)
    radius = 2.5 * case.lines * case.diameter_mm
    half = path.field.half_width_mm
    reach = math.hypot(half, case.diameter_mm / 2)
    stations = []
    for i in range(257):
        if i % 64 == 0:
            checkpoint()
        u = i / 256
        points = {}
        for number, guide in guides.items():
            index = min(int(u * len(guide.curves)), len(guide.curves) - 1)
            points[number] = guide.curves[index].point(u * len(guide.curves) - index)
        extent = max(magnitude(difference(p, midpoint)) for p in points.values())
        k, eta, eta_s = path.field.sample(u)
        minimum_j = 1 - half * abs(eta_s)
        stations.append(
            Station(
                u,
                points[0],
                (extent + case.diameter_mm / 2) / radius,
                abs(k) * reach / 0.8,
                minimum_j,
                abs(k) * (1 + eta * eta) / minimum_j if minimum_j > 1e-9 else None,
                magnitude(difference(points[0], case.end)),
            )
        )
    endpoint = residual(case, path)
    penalties = free_penalties(case, path)
    if len(endpoint) != 9 or len(penalties) != 132:
        raise ValueError("Existing objective contract changed; inspect before continuing.")
    objective = tuple(
        (name, sum(value * value for value in values))
        for name, values in (
            ("position", endpoint[:3]),
            ("tangent", endpoint[3:6]),
            ("width", endpoint[6:9]),
            ("material", penalties[0::4]),
            ("center", penalties[1::4]),
            ("lane", penalties[2::4]),
            ("sphere", penalties[3::4]),
        )
    )
    fine = tuple(float(v) for v in metrics["stages"][-1]["history"])
    if not math.isclose(sum(v for _, v in objective), fine[-1], abs_tol=1e-10, rel_tol=1e-9):
        raise ValueError("Final objective does not reproduce the retained fit score.")
    return Inspection(
        evidence.fingerprint,
        tuple(stations),
        objective,
        fine,
        radius,
        sum(a == b for a, b in zip(fine, fine[1:])),
    )
