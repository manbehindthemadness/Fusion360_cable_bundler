"""
Compare one frozen endpoint rule across four development configurations numerically.

Baseline all cases before the revised policy. No solid builds, search, retries,
report files or claims of continuous lane compliance. Stop on a sampled regression,
resource/source gate or harness error; retain known baseline failures as diagnostics.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, process_time
from typing import Any

from cable_bundler.routing.geometry import difference, dot, lerp, magnitude, unit
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon

from .endpoint_clamped import analytic_paths
from .endpoint_first import EndpointCase, construct, endpoint_cases
from .endpoint_lateral import lateral_cases
from .endpoint_reference import reference_cases
from .endpoint_trace_paths import TracePath, interpolate_trace
from .native_budget import NativeBudget
from .trace_diagnostic import curvature_radius

_state: dict[str, Any] | None = None


def _sources() -> dict[str, str]:
    """
    Freeze this procedure, policies, fixtures and mathematical dependencies.
    """
    root = Path(__file__).parent
    sources = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in (
            "clamped_comparison.py",
            "endpoint_clamped.py",
            "endpoint_first.py",
            "endpoint_lateral.py",
            "endpoint_reference.py",
            "endpoint_trace_paths.py",
            "trace_diagnostic.py",
            "native_budget.py",
        )
    }
    for name in (
        "cable_bundler/routing/geometry.py",
        "experiments/experiment_secure_discrete_ribbon/contract.py",
    ):
        sources[name] = hashlib.sha256((root.parent.parent / name).read_bytes()).hexdigest()
    return sources


def _baseline(case: EndpointCase) -> tuple[TracePath, ...]:
    """
    Recreate the historical shared-node interpolation without modifying its policy.
    """
    frames, _record = construct(case)
    return tuple(
        interpolate_trace(
            lane + 1,
            tuple(
                f.origin.translated(f.width, (lane - (case.lines - 1) / 2) * case.diameter_mm)
                for f in frames
            ),
            case.start_tangent,
            case.end_tangent,
        )
        for lane in range(case.lines)
    )


def _measure(
    case: EndpointCase, paths: tuple[TracePath, ...], budget: NativeBudget
) -> dict[str, Any]:
    """
    Observe nine points per cubic and hull containment, preserving every lane.
    """
    minimum, heading_error, cap_error = math.inf, 0.0, 0.0
    lengths = []
    for lane, path in enumerate(paths):
        budget.check(f"sample_{case.name}_lane{lane + 1}")
        length = 0.0
        for curve in path.curves:
            previous = curve.start
            for sample in range(9):
                u = sample / 8
                minimum = min(
                    minimum, curvature_radius(curve.derivative(u), curve.second_derivative(u))
                )
                position = curve.point(u)
                length += magnitude(difference(position, previous))
                previous = position
        lengths.append(length)
        offset = (lane - (case.lines - 1) / 2) * case.diameter_mm
        for curve, u, endpoint, heading, width in (
            (path.curves[0], 0.0, case.start, case.start_tangent, case.start_width),
            (path.curves[-1], 1.0, case.end, case.end_tangent, case.end_width),
        ):
            heading_error = max(
                heading_error,
                math.degrees(
                    math.acos(max(-1.0, min(1.0, dot(unit(curve.derivative(u)), heading))))
                ),
            )
            cap_error = max(
                cap_error, magnitude(difference(curve.point(u), endpoint.translated(width, offset)))
            )
    center = lerp(case.start, case.end, 0.5)
    hull_inside = all(
        magnitude(difference(p, center)) + case.diameter_mm / 2
        <= 2.5 * case.lines * case.diameter_mm
        for path in paths
        for p in path.controls
    )
    return {
        "smallest_observed_radius_mm": minimum if math.isfinite(minimum) else None,
        "sampled_radius_ok": minimum >= 3 * case.diameter_mm,
        "cap_heading_error_degrees": heading_error,
        "cap_position_error_mm": cap_error,
        "hulls_inside_sphere": hull_inside,
        "sampled_length_spread": (max(lengths) - min(lengths)) / max(lengths),
        "curvature_observations": len(paths) * 32 * 9,
    }


def run() -> dict[str, Any]:
    """
    Execute one four-case paired comparison within30seconds/2GiB and then stop.

    The fixed centerline policy changes quintic to septic; it may change interior
    shape but never targets, dimensions, rule limits or sphere. All four cases are
    examined development evidence. No native predictions or compliance acceptance.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Comparison already run; no retry.")
    cases = (reference_cases()[1], endpoint_cases()[0], lateral_cases()[-1], reference_cases()[0])
    budget = NativeBudget(maximum_seconds=30)
    sources = _sources()
    _state = {
        "plan": {
            "cases": [asdict(case) for case in cases],
            "sources": sources,
            "policy": "septic-zero-cap-jerk-analytic-hermite-v1",
            "seconds": 30,
            "rss_kib": 2097152,
            "solves_per_policy_per_case": 1,
            "native_attempts": 0,
            "search": 0,
            "retries": 0,
            "samples_per_cubic": 9,
        },
        "baseline": [],
        "revised": [],
        "stop_reason": None,
    }
    for policy in ("baseline", "revised"):
        for index, case in enumerate(cases):
            started, cpu = perf_counter(), process_time()
            row: dict[str, Any] = {"case": case.name}
            try:
                budget.check(f"{policy}_{case.name}")
                if _sources() != sources:
                    raise RuntimeError("Source gate changed.")
                paths = _baseline(case) if policy == "baseline" else analytic_paths(case)[0]
                row["generation_seconds"] = perf_counter() - started
                audit_started = perf_counter()
                row.update(_measure(case, paths, budget))
                row["audit_seconds"] = perf_counter() - audit_started
            except (UnsafeRibbon, ValueError) as error:
                row["numerical_error"] = str(error)
            except RuntimeError as error:
                _state["stop_reason"] = str(error)
            row["wall_seconds"], row["cpu_seconds"] = perf_counter() - started, process_time() - cpu
            _state[policy].append(row)
            if policy == "revised":
                before = _state["baseline"][index]
                if before.get("sampled_radius_ok") and not row.get("sampled_radius_ok"):
                    _state["stop_reason"] = f"Sampled radius regression: {case.name}"
                if before.get("hulls_inside_sphere") and not row.get("hulls_inside_sphere"):
                    _state["stop_reason"] = f"Containment regression: {case.name}"
                if (
                    row.get("cap_heading_error_degrees", 0) > 1e-5
                    or row.get("cap_position_error_mm", 0) > 1e-7
                ):
                    _state["stop_reason"] = f"Endpoint regression: {case.name}"
            if _state["stop_reason"]:
                break
        if _state["stop_reason"]:
            break
    _state["overall_seconds"] = perf_counter() - budget.started
    _state["maximum_sampled_rss_kib"] = max(int(s["rss_kib"]) for s in budget.samples)
    return _state
