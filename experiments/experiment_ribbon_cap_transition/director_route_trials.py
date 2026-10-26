"""
Keep bounded fixed-target routing trials in Fusion memory without report files.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any, cast

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT

from .director_audit import measure
from .director_rotation_transport import integrate_rotation
from .director_shooting import (
    BASELINE,
    CORKSCREW,
    REGULAR,
    ROTATION,
    ShootingPolicy,
    TransportMethod,
    solve,
)
from .director_transport import DirectorPath, integrate
from .endpoint_first import EndpointCase
from .event_cases import cases
from .native_budget import NativeBudget

_trials: dict[str, dict[str, Any]] = {}
_paths: dict[str, list[DirectorPath]] = {}


def sources() -> dict[str, str]:
    """
    Fingerprint the fixed-target method and direct dependencies before solving.
    """
    names = (
        "director_routing_field.py",
        "director_route_objective.py",
        "director_route_seed.py",
        "director_seed_bank.py",
        "director_rotation_transport.py",
        "director_shooting.py",
        "director_routing_cases.py",
        "director_route_trials.py",
        "director_transport.py",
        "director_audit.py",
        "director_fields.py",
        "event_cases.py",
        "coupled_motion.py",
        "target_shooting.py",
        "endpoint_first.py",
        "native_budget.py",
    )
    paths = [Path(__file__).with_name(name) for name in names]
    return {
        str(p.relative_to(PROJECT_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
    }


def run_baseline() -> dict[str, Any]:
    """
    Retain the original bounded free-axis cold-start comparison entry point.
    """
    return _run("cold-baseline-v1", BASELINE)


def run_rotation() -> dict[str, Any]:
    """
    Compare structural unit rotations under the same eight fixed endpoint inputs.
    """
    return _run("cold-rotation-v1", ROTATION)


def run_regular(part: int) -> dict[str, Any]:
    """
    Evaluate two frozen four-case sub-batches under one regular-aware policy.
    """
    if part not in (0, 1):
        raise ValueError("Regular matrix has two registered parts.")
    return _run("cold-regular-v1-part" + str(part), REGULAR, tuple(range(part * 4, part * 4 + 4)))


def run_corkscrew(part: int) -> dict[str, Any]:
    """
    Compare one coupled-reversal seed under the unchanged regular-aware policy.
    """
    if part not in (0, 1):
        raise ValueError("Corkscrew matrix has two registered parts.")
    return _run(
        "cold-corkscrew-v1-part" + str(part), CORKSCREW, tuple(range(part * 4, part * 4 + 4))
    )


def _run(
    label: str,
    policy: ShootingPolicy,
    indices: tuple[int, ...] = tuple(range(8)),
    registered_cases: tuple[EndpointCase, ...] | None = None,
) -> dict[str, Any]:
    """
    Evaluate a frozen subset of examined endpoint configurations with one policy.

    No fixture reference curves or earlier solved parameters enter solve().
    At most8cases under the registered per-policy round cap,10s/2GiB sampledRSS.
    Strict1e-8actualAarrival precedes compatibility. No native geometry/search
    retry/report files. Stop resource/source/harness or retained-control regression.
    """
    if label in _trials:
        raise RuntimeError("Fixed-target baseline already started.")
    app = adsk.core.Application.get()
    if (
        adsk.fusion.Design.cast(app.activeProduct) is None
        or app.userInterface.activeCommand != "SelectCommand"
    ):
        raise RuntimeError("Expected idle current Fusion scratch.")
    all_inputs = cases() if registered_cases is None else registered_cases
    inputs = tuple(all_inputs[i] for i in indices)
    fingerprints = sources()
    budget = NativeBudget(maximum_seconds=10)
    budget.check("start")
    state: dict[str, Any] = {
        "plan": {
            "algorithm": label,
            "sources": fingerprints,
            "inputs": [asdict(c) for c in inputs],
            "hypothesis": "Cold smooth director fields can close fixed A-edge targets before companion construction.",
            "procedure": "Same deterministic geometry-only seed,10coordinates;registered coarse64/final512rounds;strict1e-8closure;259compatibility samples only after closure.",
            "transport": policy.transport.value,
            "seed_method": policy.seed_method.value,
            "policy": {
                "coarse_rounds": policy.coarse_rounds,
                "final_rounds": policy.final_rounds,
                "step": policy.maximum_step,
            },
            "case_indices": indices,
            "limits": {
                "cases": len(inputs),
                "maximum_evaluations_per_case": 2
                + 12 * (policy.coarse_rounds + policy.final_rounds),
                "seconds": 10,
                "rss_kib": 2 * 1024 * 1024,
                "native_attempts": 0,
                "reports": 0,
            },
            "scope": "Development fixed-target routing,not untouched validation. Fresh6reference-witness targets remain reserved and unexamined.",
            "native_prediction": "unknown;not attempted",
        },
        "rows": [
            {"case": c.name, "attempted": False, "evaluated": False, "overall": "unattempted"}
            for c in inputs
        ],
        "stop_reason": None,
    }
    _trials[label] = state
    paths: list[DirectorPath] = []
    _paths[label] = paths
    sampled_at = budget.started

    def checkpoint() -> None:
        """
        Bound time per evaluation and sample Fusion process memory every quarter-second.
        """
        nonlocal sampled_at
        now = perf_counter()
        if now - budget.started >= 10:
            raise RuntimeError("Fixed-target numerical time cap reached.")
        if now - sampled_at >= 0.25:
            budget.check("fixed_targets")
            sampled_at = now

    try:
        for case, row in zip(inputs, state["rows"]):
            checkpoint()
            if sources() != fingerprints:
                raise RuntimeError("Fixed-target source drift.")
            row.update(attempted=True, overall="interrupted during solve")
            path, metrics = solve(case, checkpoint, policy=policy, progress=row)
            paths.append(path)
            row.update(metrics, evaluated=True)
            row["overall"] = "failed target closure"
            if row["endpoint_gate_passed"]:
                started = perf_counter()
                transport = (
                    integrate if policy.transport is TransportMethod.AXES else integrate_rotation
                )
                coarse = transport(path.field, 256, checkpoint, initial=path.states[0])
                row["compatibility"] = measure(coarse, path, checkpoint)
                row["compatibility_seconds"] = perf_counter() - started
                row["overall"] = (
                    "sampled numerical gates pass;native unresolved"
                    if not row["compatibility"]["policy_findings"]
                    and not row["compatibility"]["numerical_findings"]
                    else "failed compatibility"
                )
            retained_names = {c.name for j, c in enumerate(cases()) if j in (2, 3, 7)}
            if case.name in retained_names and row["overall"].startswith("failed"):
                raise RuntimeError("Retained control regression:" + case.name)
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        state["stop_reason"] = str(error)
    state["seconds"] = perf_counter() - budget.started
    state["maximum_sampled_rss_kib"] = max(cast(int, s["rss_kib"]) for s in budget.samples)
    return state
