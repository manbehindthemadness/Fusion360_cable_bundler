"""
Compare one combined bend-and-bank travel policy against the retained arc-jet baseline.

Thirty seconds/two GiB, one generation per case, no search/retries/native attempts.
Known spatial failures are retained and controls still run; stop on new control
rejection/regression, containment loss, resource/source gates or harness errors.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, process_time
from typing import Any

from cable_bundler.routing.geometry import difference, lerp, magnitude
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon

from .analytic_scaffold import scaffold_paths
from .bank_travel import travel_controls
from .clamped_comparison import _sources
from .clamped_diagnostic import compare_paths
from .endpoint_first import derivative, endpoint_cases, evaluate
from .endpoint_lateral import lateral_cases
from .endpoint_reference import reference_cases
from .native_budget import NativeBudget
from .trace_diagnostic import curvature_radius

_state: dict[str, Any] | None = None


def run() -> dict[str, Any]:
    """
    Freeze all inputs/policies/baselines before one numerical comparison and stop.

    The arc-jet baseline has two uncertified spatial cases and two sampled passing
    controls. Keep all four outcomes; the baseline provides no native coverage.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Bank travel comparison already started; no retry.")
    root = Path(__file__).parent
    sources = _sources()
    if (
        sources["endpoint_clamped.py"]
        != "7d0fd440afdbfee0d006eaad7d9cc7312448decc57e55f89cf3c0076d0c101a5"
    ):
        raise RuntimeError("Measured baseline policy changed.")
    for name in (
        "bank_travel_comparison.py",
        "bank_travel.py",
        "distributed_bend.py",
        "piecewise_bend.py",
        "analytic_scaffold.py",
        "clamped_diagnostic.py",
    ):
        sources[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    for name in ("experiment_testing_rules.txt", "rollback_end_loft_notes.txt"):
        sources[name] = hashlib.sha256((root.parent.parent / name).read_bytes()).hexdigest()
    if (
        sources["distributed_bend.py"]
        != "f7e94f76b15966ed17f1b18150c3d32b9a12d94ddcd5dd125cdb686bca373d9e"
    ):
        raise RuntimeError("Previously measured arc-jet policy changed.")
    cases = (reference_cases()[1], endpoint_cases()[0], lateral_cases()[-1], reference_cases()[0])
    baselines = (
        (None, None),
        (math.inf, math.inf),
        (None, None),
        (44.997057566403726, 44.96096290030089),
    )
    budget = NativeBudget(maximum_seconds=30)
    _state = {
        "plan": {
            "cases": [asdict(c) for c in cases],
            "sources": sources,
            "policy": "degree9-combined-bend-bank-travel-v1",
            "baseline_arc_jet_analytic_cubic_mm": baselines,
            "baseline_spatial_disposition": "Both uncertified in shared preflight; lane minima unmeasured.",
            "seconds": 30,
            "rss_kib": 2097152,
            "solves_per_case": 1,
            "samples_per_cubic": 9,
            "shared_preflight_samples": 33,
            "native_attempts": 0,
            "search": 0,
            "retries": 0,
        },
        "cases": [],
        "stop_reason": None,
    }
    for index, case in enumerate(cases):
        started, cpu = perf_counter(), process_time()
        row: dict[str, Any] = {"case": case.name}
        try:
            budget.check(case.name)
            for name, expected in sources.items():
                path = root / name if (root / name).is_file() else root.parent.parent / name
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise RuntimeError("Frozen source changed.")
            points, metadata = travel_controls(case)
            row["distribution"] = metadata
            first = derivative(points)
            second = derivative(first)
            worst: dict[str, Any] = {"curvature_times_reach": 0.0}
            reach = math.hypot(
                case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1, case.diameter_mm / 2
            )
            for sample in range(33):
                parameter = sample / 32
                radius = curvature_radius(evaluate(first, parameter), evaluate(second, parameter))
                ratio = reach / radius
                if ratio > worst["curvature_times_reach"]:
                    worst = {
                        "curvature_times_reach": ratio,
                        "radius_mm": radius,
                        "parameter": parameter,
                    }
            row["shared_smallest_observed"] = worst
            if worst["curvature_times_reach"] > 0.8:
                raise UnsafeRibbon(
                    "Observed shared curvature exceeds0.8; certificate and native builds unattempted."
                )
            paths, certificate = scaffold_paths(case, points)
            row["generation_seconds"] = perf_counter() - started
            row["shared_certificate"] = certificate
            audit_started = perf_counter()
            row.update(compare_paths(case, points, paths, budget))
            center = lerp(case.start, case.end, 0.5)
            row["hulls_inside_sphere"] = all(
                magnitude(difference(p, center)) + case.diameter_mm / 2
                <= 2.5 * case.lines * case.diameter_mm
                for path in paths
                for p in path.controls
            )
            lengths = [
                sum(
                    magnitude(difference(c.point((i + 1) / 8), c.point(i / 8)))
                    for c in path.curves
                    for i in range(8)
                )
                for path in paths
            ]
            row["sampled_length_spread"] = (max(lengths) - min(lengths)) / max(lengths)
            row["sampled_centerline_length_mm"] = lengths[case.lines // 2]
            row["audit_seconds"] = perf_counter() - audit_started
            if not row["hulls_inside_sphere"]:
                raise RuntimeError("Containment regression.")
            if index in (1, 3) and any(
                row[field]["radius_mm"] < 3 * case.diameter_mm
                for field in ("analytic_smallest_observed", "cubic_smallest_observed")
            ):
                raise RuntimeError("Previously passing control radius regressed.")
        except UnsafeRibbon as error:
            row["numerical_rejection"] = str(error)
            if index in (1, 3):
                _state["stop_reason"] = f"Control rejection: {case.name}"
        except (RuntimeError, ValueError) as error:
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
