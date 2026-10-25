"""
Separate analytic offset-lane curvature from unchanged cubic interpolation error.

Four fixed development cases, one generation each, thirty seconds/two GiB,
no searches, retries, native builds or report files. Finite observations exhibit
violations but cannot establish continuous compliance or global minima.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, process_time
from typing import Any

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon

from .clamped_comparison import _sources
from .endpoint_clamped import analytic_paths, clamped_controls
from .endpoint_first import EndpointCase, derivative, endpoint_cases, evaluate
from .endpoint_lateral import lateral_cases
from .endpoint_reference import reference_cases
from .endpoint_trace_paths import TracePath
from .native_budget import NativeBudget
from .trace_diagnostic import curvature_radius, shared_lane_jet

_state: dict[str, Any] | None = None


def _heading_error(left: Vector3, right: Vector3) -> float:
    """
    Measure the directed angular difference between regular curve derivatives.
    """
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(unit(left), unit(right))))))


def compare_paths(
    case: EndpointCase,
    points: tuple[Vector3, ...],
    paths: tuple[TracePath, ...],
    budget: NativeBudget,
) -> dict[str, Any]:
    """
    Compare both fields at nine points/cubic, including both sides of every knot.

    Cache257shared jets and exploit their linear dependence on lane offset. Cubic
    derivatives are rescaled into the shared global parameter before comparison.
    Keep the analytic radius at the worst cubic observation to localize distortion.
    """
    if len(paths) != case.lines or any(len(path.curves) != 32 for path in paths):
        raise ValueError("Expected every ordered lane with32cubics.")
    straight = all(
        magnitude(cross(difference(p, case.start), difference(case.end, case.start))) < 1e-8
        for p in points
    )
    first = derivative(points)
    second = derivative(first)
    shared = []
    for sample in range(257):
        if sample % 32 == 0:
            budget.check(f"shared_{case.name}_{sample}")
        u = sample / 256
        base = (evaluate(points, u), evaluate(first, u), evaluate(second, u))
        if straight:
            offsets = (case.start_width, Vector3(0, 0, 0), Vector3(0, 0, 0))
        else:
            shifted = shared_lane_jet(points, u, 1)
            offsets = tuple(difference(a, b) for a, b in zip(shifted, base))
        shared.append((base, offsets))
    analytic_worst: dict[str, Any] = {"radius_mm": math.inf}
    cubic_worst: dict[str, Any] = {"radius_mm": math.inf}
    position_error, heading_error, acceleration_error = 0.0, 0.0, 0.0
    caps = []
    for lane, path in enumerate(paths):
        budget.check(f"paired_{case.name}_lane{lane + 1}")
        offset = (lane - (case.lines - 1) / 2) * case.diameter_mm
        for segment, curve in enumerate(path.curves):
            for sample in range(9):
                u = sample / 8
                base, offsets = shared[segment * 8 + sample]
                position, velocity, acceleration = (
                    a.translated(b, offset) for a, b in zip(base, offsets)
                )
                analytic_radius = curvature_radius(velocity, acceleration)
                cubic_radius = curvature_radius(curve.derivative(u), curve.second_derivative(u))
                location = {
                    "trace": path.number,
                    "segment": segment + 1,
                    "local_parameter": u,
                    "global_parameter": (segment + u) / 32,
                }
                if analytic_radius < analytic_worst["radius_mm"]:
                    analytic_worst = {"radius_mm": analytic_radius, **location}
                if cubic_radius < cubic_worst["radius_mm"]:
                    cubic_worst = {
                        "radius_mm": cubic_radius,
                        "analytic_radius_here_mm": analytic_radius,
                        **location,
                    }
                position_error = max(
                    position_error, magnitude(difference(curve.point(u), position))
                )
                heading_error = max(heading_error, _heading_error(curve.derivative(u), velocity))
                cubic_acceleration = Vector3(0, 0, 0).translated(curve.second_derivative(u), 32**2)
                acceleration_error = max(
                    acceleration_error, magnitude(difference(cubic_acceleration, acceleration))
                )
                if (segment == 0 and sample == 0) or (segment == 31 and sample == 8):
                    caps.append(
                        {
                            "trace": path.number,
                            "end": segment == 31,
                            "analytic_radius_mm": analytic_radius,
                            "cubic_radius_mm": cubic_radius,
                        }
                    )
    return {
        "analytic_smallest_observed": analytic_worst,
        "cubic_smallest_observed": cubic_worst,
        "max_position_error_mm": position_error,
        "max_heading_error_degrees": heading_error,
        "max_global_acceleration_error_mm": acceleration_error,
        "caps": caps,
        "observations_per_field": case.lines * 32 * 9,
        "required_radius_mm": case.diameter_mm * 3,
    }


def run() -> dict[str, Any]:
    """
    Diagnose exactly the previous four-case clamped policy, stopping on harness gates.

    Known radius failures are the subject, not a reason to omit subsequent controls.
    Stop on source changes, singular evaluations, resource limits or harness errors.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Diagnostic already started; no retry.")
    sources = _sources()
    if (
        sources["endpoint_clamped.py"]
        != "7d0fd440afdbfee0d006eaad7d9cc7312448decc57e55f89cf3c0076d0c101a5"
    ):
        raise RuntimeError("The previously compared clamped policy changed.")
    cases = (reference_cases()[1], endpoint_cases()[0], lateral_cases()[-1], reference_cases()[0])
    budget = NativeBudget(maximum_seconds=30)
    _state = {
        "plan": {
            "cases": [asdict(c) for c in cases],
            "sources": sources,
            "diagnostic_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "seconds": 30,
            "rss_kib": 2097152,
            "samples_per_cubic": 9,
            "solves_per_case": 1,
            "native_attempts": 0,
            "search": 0,
            "retries": 0,
        },
        "cases": [],
        "stop_reason": None,
    }
    for case in cases:
        started, cpu = perf_counter(), process_time()
        row: dict[str, Any] = {"case": case.name}
        try:
            budget.check(case.name)
            if _sources() != sources:
                raise RuntimeError("Source fingerprint changed.")
            paths, _certificate = analytic_paths(case)
            row["generation_seconds"] = perf_counter() - started
            audit_started = perf_counter()
            row.update(compare_paths(case, clamped_controls(case), paths, budget))
            row["audit_seconds"] = perf_counter() - audit_started
        except (RuntimeError, ValueError, UnsafeRibbon) as error:
            _state["stop_reason"] = str(error)
        row["wall_seconds"], row["cpu_seconds"] = perf_counter() - started, process_time() - cpu
        _state["cases"].append(row)
        if _state["stop_reason"]:
            break
    _state["overall_seconds"] = perf_counter() - budget.started
    _state["maximum_sampled_rss_kib"] = max(
        (int(s["rss_kib"]) for s in budget.samples), default=None
    )
    return _state
