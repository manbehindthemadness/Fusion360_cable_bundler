"""
Compare one width-aware arc-jet policy against the four retained degree-seven baselines.

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
from .clamped_comparison import _sources
from .clamped_diagnostic import compare_paths
from .distributed_bend import distributed_controls
from .endpoint_first import endpoint_cases
from .endpoint_lateral import lateral_cases
from .endpoint_reference import reference_cases
from .native_budget import NativeBudget

_state: dict[str, Any] | None = None


def run() -> dict[str, Any]:
    """
    Freeze all inputs/policies/baselines before one numerical comparison and stop.

    The measured degree-seven baseline has two known spatial radius failures and
    two sampled passing controls. The later degree-nine crossover's shared rejection
    remains preserved separately. Neither baseline provides native coverage.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Distributed bend comparison already started; no retry.")
    root = Path(__file__).parent
    sources = _sources()
    if (
        sources["endpoint_clamped.py"]
        != "7d0fd440afdbfee0d006eaad7d9cc7312448decc57e55f89cf3c0076d0c101a5"
    ):
        raise RuntimeError("Measured baseline policy changed.")
    for name in (
        "distributed_comparison.py",
        "distributed_bend.py",
        "analytic_scaffold.py",
        "clamped_diagnostic.py",
    ):
        sources[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    for name in ("experiment_testing_rules.txt", "rollback_end_loft_notes.txt"):
        sources[name] = hashlib.sha256((root.parent.parent / name).read_bytes()).hexdigest()
    cases = (reference_cases()[1], endpoint_cases()[0], lateral_cases()[-1], reference_cases()[0])
    baselines = (
        (1.1300078382807492, 1.2317788720457838),
        (math.inf, math.inf),
        (1.1300078382807492, 1.2274010098063317),
        (18.46633990125118, 18.4434597683784),
    )
    budget = NativeBudget(maximum_seconds=30)
    _state = {
        "plan": {
            "cases": [asdict(c) for c in cases],
            "sources": sources,
            "policy": "degree9-width-aware-circular-cap-jets-v1",
            "baseline_degree7_analytic_cubic_mm": baselines,
            "seconds": 30,
            "rss_kib": 2097152,
            "solves_per_case": 1,
            "samples_per_cubic": 9,
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
            points, metadata = distributed_controls(case)
            row["distribution"] = metadata
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
