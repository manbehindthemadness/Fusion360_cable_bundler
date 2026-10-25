"""
Evaluate one zero-cap-width-acceleration policy against four frozen baselines.

One generation/case, thirty seconds/two GiB, zero native attempts/search/retries.
Known spatial failures remain diagnostic outcomes; stop on control regression or
resource/provenance/harness gates. No separate report files are written.
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

from .clamped_comparison import _sources
from .clamped_diagnostic import compare_paths
from .endpoint_cap_acceleration import cap_acceleration_paths
from .endpoint_first import endpoint_cases
from .endpoint_lateral import lateral_cases
from .endpoint_reference import reference_cases
from .native_budget import NativeBudget

_state: dict[str, Any] | None = None


def run() -> dict[str, Any]:
    """
    Freeze sources, existing numerical baselines and targets before one fixed pass.

    Previously measured same-grid degree-seven minima are retained as baselines;
    they are not regenerated or treated as native baselines. Both fields are sampled
    at5472observations/case, with both one-sided cubic accelerations at joins.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Cap acceleration comparison already started; no retry.")
    sources = _sources()
    if (
        sources["endpoint_clamped.py"]
        != "7d0fd440afdbfee0d006eaad7d9cc7312448decc57e55f89cf3c0076d0c101a5"
    ):
        raise RuntimeError("Previously measured baseline policy changed.")
    root = Path(__file__).parent
    for name in (
        "cap_acceleration_comparison.py",
        "endpoint_cap_acceleration.py",
        "clamped_diagnostic.py",
    ):
        sources[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    cases = (reference_cases()[1], endpoint_cases()[0], lateral_cases()[-1], reference_cases()[0])
    baseline_radii = (
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
            "baselines_analytic_cubic_mm": baseline_radii,
            "policy": "degree9-zero-cap-jerk-snap-analytic-hermite-v1",
            "seconds": 30,
            "rss_kib": 2097152,
            "solves_per_case": 1,
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
            paths, points, certificate = cap_acceleration_paths(case)
            row["generation_seconds"] = perf_counter() - started
            row["scaffold_certificate"] = certificate
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
                row[field]["radius_mm"] < case.diameter_mm * 3
                for field in ("analytic_smallest_observed", "cubic_smallest_observed")
            ):
                raise RuntimeError("Previously passing control radius regressed.")
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
