"""
Measure local thickness pinching independently from frozen cubic geometry.
"""

from __future__ import annotations

import math
from typing import Any

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit

from ..pinch import PinchLimit
from ..traces import evaluate_jet
from .geometry import PathSnapshot


def _principal(
    velocity: Vector3, acceleration: Vector3, ruling: Vector3, ruling_rate: Vector3
) -> float:
    """
    Measure maximum absolute principal curvature of the sampled ruled surface.

    Use first/second fundamental forms, independently of the solver's eta/J
    formula. Normal offsets lose local regularity at half-thickness times either
    principal curvature of magnitude one. This is a sampled local check only.
    """
    e_metric, f_metric, g_metric = (
        dot(velocity, velocity),
        dot(velocity, ruling),
        dot(ruling, ruling),
    )
    determinant = e_metric * g_metric - f_metric * f_metric
    if determinant <= 1e-20:
        raise ValueError("Frozen material surface has a degenerate local metric.")
    normal = unit(cross(velocity, ruling))
    e_shape, f_shape = dot(normal, acceleration), dot(normal, ruling_rate)
    mean = (e_shape * g_metric - 2 * f_shape * f_metric) / (2 * determinant)
    gaussian = -f_shape * f_shape / determinant
    spread = math.sqrt(max(0.0, mean * mean - gaussian))
    return max(abs(mean + spread), abs(mean - spread))


def sample(snapshot: PathSnapshot, u: float, percent: float) -> dict[str, Any]:
    """
    Compare all material guides at one corresponding station and preserve order failures.
    """
    allowed = PinchLimit(percent)
    guides = {guide.number: evaluate_jet(guide, u) for guide in snapshot.guides}
    center = guides[0]
    h = snapshot.diameter_mm / 2
    labels = ((0, "centre"), (-1, "edge_a"), (-2, "edge_b"))
    radii: dict[str, float | None] = {}
    speeds = {number: magnitude(values[1]) for number, values in guides.items()}
    if min(speeds.values()) < 1e-12:
        raise ValueError("Frozen guide has stationary material progress.")
    for number, label in labels:
        if number not in guides:
            radii[label] = None
            continue
        _, velocity, acceleration = guides[number]
        curvature = magnitude(cross(velocity, acceleration)) / speeds[number] ** 3
        radii[label] = 1 / curvature if curvature > 1e-12 else None
    pinches: dict[str, float] = {}
    if snapshot.lines == 1:
        pinches["centre"] = h / radii["centre"] if radii["centre"] is not None else 0.0
        references = {"centre": h / allowed.fraction, "edge_a": None, "edge_b": None}
        maximum = pinches["centre"]
        ordered: bool | None = None
    else:
        a, b = guides[-1], guides[-2]
        ruling = difference(a[0], b[0])
        ruling = Vector3(ruling.x / 2, ruling.y / 2, ruling.z / 2)
        delta_rate = difference(a[1], b[1])
        ruling_rate = Vector3(delta_rate.x / 2, delta_rate.y / 2, delta_rate.z / 2)
        tangent = unit(center[1])
        across = ruling.translated(tangent, -dot(ruling, tangent))
        eta = dot(ruling, tangent) / magnitude(across)
        references = {
            label: h * (1 + eta * eta) / allowed.fraction * speeds[number] / min(speeds.values())
            for number, label in labels
        }
        for number, label in labels:
            values = guides[number]
            pinches[label] = h * _principal(values[1], values[2], ruling, ruling_rate)
        interior = []
        for weight in (-0.5, 0.5):
            velocity = center[1].translated(ruling_rate, weight)
            delta_acc = difference(a[2], b[2])
            acceleration = center[2].translated(delta_acc, weight / 2)
            interior.append(h * _principal(velocity, acceleration, ruling, ruling_rate))
        maximum = max(*pinches.values(), *interior)
        ra, rc, rb = radii["edge_a"], radii["centre"], radii["edge_b"]
        tolerance = (
            1e-5 * max(value for value in radii.values() if value is not None)
            if any(value is not None for value in radii.values())
            else 0.0
        )
        ordered = (
            min(ra, rb) - tolerance <= rc <= max(ra, rb) + tolerance
            if ra is not None and rc is not None and rb is not None
            else None
        )
    return {
        "u": u,
        "radii_mm": radii,
        "reference_radii_mm": references,
        "utilization": {key: value / allowed.fraction for key, value in pinches.items()},
        "pinch_percent": {key: value * 100 for key, value in pinches.items()},
        "maximum_percent": maximum * 100,
        "inside_remaining_percent": (1 - maximum) * 100,
        "ordered": ordered,
        "centre_edge_ratio": None,
    }


def inspect(snapshot: PathSnapshot, section: int, percent: float) -> dict[str, Any]:
    """
    Retain a 65-point graph and an independent four-samples-per-cubic local audit.

    Three guides and two interior width samples measure the nominal material
    sheet. Neither this sampling nor positive local Jacobians certify global
    clearance or the still-unspecified bonded contour.
    """
    samples = [sample(snapshot, index / 64, percent) for index in range(65)]
    maximum, worst_u, order_failures = 0.0, 0.0, 0
    for index in range(snapshot.intervals):
        for fraction in (0.0, 1 / 3, 2 / 3, 1.0):
            u = (index + fraction) / snapshot.intervals
            observed = sample(snapshot, u, percent)
            if observed["maximum_percent"] > maximum:
                maximum, worst_u = observed["maximum_percent"], u
            order_failures += observed["ordered"] is False
    return {
        "bend_model": "pinch percent",
        "allowed_percent": percent,
        "reference_radius_mm": snapshot.diameter_mm / 2 / PinchLimit(percent).fraction,
        "has_edges": snapshot.lines > 1,
        "selected": sample(snapshot, snapshot.sections[section].u, percent),
        "samples": samples,
        "maximum_percent": maximum,
        "worst_u": worst_u,
        "order_failures": order_failures,
        "scope": "Local thickness pinch: 100% reaches zero inside radius. Same-station circular/nominal ruled-surface measurements; full-thickness global contact and bonded contour remain unverified.",
    }
