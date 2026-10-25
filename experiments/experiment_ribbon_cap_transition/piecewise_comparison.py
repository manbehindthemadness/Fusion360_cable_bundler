"""
Evaluate one fixed three-region rule on the retained four-case development matrix.

Thirty seconds/two GiB, one generation/case, no search/retries/native/report files.
All regions use the existing shared rules, including both internal joins. Known
spatial rejections remain in results; controls still run unless a stop gate fires.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, process_time
from typing import Any

from cable_bundler.routing.geometry import lerp
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon

from .clamped_comparison import _sources
from .endpoint_first import certify, endpoint_cases
from .endpoint_lateral import lateral_cases
from .endpoint_reference import reference_cases
from .native_budget import NativeBudget
from .piecewise_bend import build_piecewise
from .piecewise_paths import compare_paths, trace_paths
from .trace_diagnostic import curvature_radius

_state: dict[str, Any] | None = None


def run() -> dict[str, Any]:
    """
    Freeze sources/cases/baselines and evaluate each once, retaining region failures.

    The prior midpoint policy's spatial cases were uncertified; controls retained
    straight geometry and approximately45mm return radius. No native baseline exists.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Piecewise comparison already started; no retry.")
    root = Path(__file__).parent
    sources = _sources()
    for name in (
        "piecewise_comparison.py",
        "piecewise_bend.py",
        "piecewise_paths.py",
        "distributed_bend.py",
        "coordinated_bend.py",
    ):
        sources[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    for name in ("experiment_testing_rules.txt", "rollback_end_loft_notes.txt"):
        sources[name] = hashlib.sha256((root.parent.parent / name).read_bytes()).hexdigest()
    if (
        sources["coordinated_bend.py"]
        != "bae2b39c2ce7faa22ff304d859615b187fe8067afb98f6905859e9a1bdd9a394"
        or sources["distributed_bend.py"]
        != "f7e94f76b15966ed17f1b18150c3d32b9a12d94ddcd5dd125cdb686bca373d9e"
    ):
        raise RuntimeError("Retained baseline or nominal circular rule changed.")
    cases = (reference_cases()[1], endpoint_cases()[0], lateral_cases()[-1], reference_cases()[0])
    budget = NativeBudget(maximum_seconds=30)
    _state = {
        "plan": {
            "cases": [asdict(c) for c in cases],
            "sources": sources,
            "policy": "three-region-circular-approaches-half-bridge-v1",
            "intervals": (0, 0.25, 0.75, 1),
            "seconds": 30,
            "rss_kib": 2097152,
            "solves_per_case": 1,
            "samples_per_cubic": 9,
            "shared_samples_per_region": 5,
            "baseline_disposition": (
                "uncertified",
                "straight",
                "uncertified",
                "sampled radius pass",
            ),
            "baseline_return_analytic_cubic_mm": (44.99999927115222, 44.963919492278535),
            "native_attempts": 0,
            "search": 0,
            "retries": 0,
        },
        "cases": [],
        "stop_reason": None,
    }
    for index, case in enumerate(cases):
        started, cpu = perf_counter(), process_time()
        row: dict[str, Any] = {
            "case": case.name,
            "stage": "generation",
            "region_certificates": [],
            "region_observations": [],
        }
        try:
            budget.check(case.name)
            for name, expected in sources.items():
                path = root / name if (root / name).is_file() else root.parent.parent / name
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise RuntimeError("Frozen source changed.")
            scaffold, metadata = build_piecewise(case)
            row["distribution"] = metadata
            reach = math.hypot(
                case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1, case.diameter_mm / 2
            )
            for number, piece in enumerate(scaffold.pieces, 1):
                row["stage"] = f"region_{number}_shared_preflight"
                budget.check(row["stage"])
                worst: dict[str, Any] = {"curvature_times_reach": 0.0}
                for sample in range(5):
                    parameter = (
                        piece.start_parameter
                        + (piece.end_parameter - piece.start_parameter) * sample / 4
                    )
                    _position, velocity, acceleration = piece.jet(parameter, 0)
                    radius = curvature_radius(velocity, acceleration)
                    ratio = reach / radius
                    if ratio > worst["curvature_times_reach"]:
                        worst = {
                            "curvature_times_reach": ratio,
                            "radius_mm": radius,
                            "parameter": parameter,
                        }
                row["region_observations"].append(worst)
                row["region_certificates"].append(
                    certify(
                        piece.controls,
                        reach,
                        lerp(case.start, case.end, 0.5),
                        2.5 * case.lines * case.diameter_mm,
                    )
                )
            row["stage"] = "trace_interpolation"
            paths = trace_paths(case, scaffold)
            row["generation_seconds"] = perf_counter() - started
            audit_started = perf_counter()
            row["stage"] = "paired_numerical_audit"
            row.update(compare_paths(case, scaffold, paths, budget))
            row["audit_seconds"] = perf_counter() - audit_started
            if not row["hulls_inside_sphere"] or row["cap_position_error_mm"] > 1e-7:
                raise RuntimeError("Containment or fixed-cap regression.")
            if index in (1, 3) and any(
                row[field]["radius_mm"] < 3 * case.diameter_mm
                for field in ("analytic_smallest_observed", "cubic_smallest_observed")
            ):
                raise RuntimeError("Previously passing control radius regressed.")
            row["stage"] = "complete_numerical_comparison"
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
