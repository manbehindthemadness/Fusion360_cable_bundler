"""
Run two remaining reference configurations with per-trace sweeps under renewed bounds.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT

from .endpoint_reference import REFERENCE_IMAGES, reference_cases
from .endpoint_timing import timing_values
from .lateral_native import _bodies, _design, finish_batch
from .native_budget import NativeBudget, resident_kib
from .trace_sweep_native import build_candidate

_state: dict[str, Any] | None = None


def _fingerprints() -> dict[str, str]:
    """
    Freeze the exact solver, interpolation, construction, cap and resource code.
    """
    names = (
        "endpoint_first.py",
        "endpoint_trace_paths.py",
        "endpoint_caps.py",
        "endpoint_timing.py",
        "endpoint_reference.py",
        "trace_sweep_native.py",
        "sweep_reference_native.py",
        "lateral_native.py",
        "native_budget.py",
    )
    paths = [Path(__file__).with_name(name) for name in names]
    paths.extend(
        PROJECT_ROOT / name
        for name in (
            *REFERENCE_IMAGES,
            "experiment_testing_rules.txt",
            "rollback_end_loft_notes.txt",
        )
    )
    paths.extend(
        PROJECT_ROOT / name
        for name in (
            "experiments/experiment_secure_discrete_ribbon/contract.py",
            "cable_bundler/routing/geometry.py",
        )
    )
    return {
        str(p.relative_to(PROJECT_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
    }


def start() -> dict[str, object]:
    """
    Freeze two endpoint configurations and the new sweep-interpolation policy.

    Preserve all eight existing solids. This is a new construction experiment,
    not a comparable replay of historical one-body lobe loft timings.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Sweep batch already registered; no restart.")
    document, design = _design()
    baseline = _bodies(design)
    if len(baseline) != 8 or resident_kib() >= 2097152:
        raise RuntimeError("Expected eight retained bodies below the memory ceiling.")
    cases = reference_cases()[1:]
    plan = {
        "question": "Can the two remaining fixed reference endpoint configurations construct as19ordered circular trace sweeps?",
        "cases": [asdict(c) for c in cases],
        "native_predictions": ["unknown", "unknown"],
        "sources": _fingerprints(),
        "limits": {
            "cases": 2,
            "solves": 2,
            "native_attempts": 2,
            "case_seconds": 120,
            "batch_seconds": 300,
            "rss_kib": 2097152,
            "search": 0,
            "retries": 0,
        },
        "construction": "Shared33-node binormal scaffold; cubic Hermite traces with exact endpoint headings; one exact NURBS and circular sweep per trace. No loft or bonded lobe outline.",
        "preflight": "Original input certificate and sampled lane-radius gate, plus a bounded4096-interval/depth12 continuous3diameter-radius check on all interpolated trace paths. Continuous spacing remains unmeasured.",
        "audit": "Only feature-provided start/end faces and solid validity; no face-wide search or integrated volumes. Timing readout here, no new report files.",
        "stop": "First rule/build/cap/source/resource failure; preserve partial traces and unattempted configurations.",
    }
    _state = {
        "document": document,
        "plan": plan,
        "cases": cases,
        "rows": [
            {
                "case_id": c.name,
                "evaluated": False,
                "native_attempted": False,
                "built": False,
                "fully_audited": False,
                "status": "not_attempted",
            }
            for c in cases
        ],
        "started": perf_counter(),
        "baseline_bodies": baseline,
        "stop_reason": None,
        "finished": False,
    }
    return plan


def run_next() -> dict[str, Any]:
    """
    Attempt one complete candidate with fail-soft retention and strict stop latching.
    """
    state = _state
    if state is None or state["stop_reason"] or state["finished"]:
        raise RuntimeError("No schedulable sweep batch.")
    index = next((i for i, r in enumerate(state["rows"]) if r["status"] == "not_attempted"), None)
    if index is None:
        raise RuntimeError("Approved sweep slots exhausted.")
    row = state["rows"][index]
    started = perf_counter()
    budget = NativeBudget()
    try:
        if _fingerprints() != state["plan"]["sources"] or perf_counter() - state["started"] >= 270:
            raise RuntimeError("Source or batch scheduling gate reached.")
        if not state["document"].activate():
            raise RuntimeError("Owned document activation failed.")
        build_candidate(state["cases"][index], row, 8 + index, budget)
        budget.check("post_case")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        row.update(status="stopped", error=str(error))
        state["stop_reason"] = f"{row['case_id']}: {error}"
    finally:
        row["total_seconds"] = perf_counter() - started
        row["memory_samples"] = budget.samples
        row["timing"] = timing_values(row)
    return row


def finish() -> dict[str, object]:
    """
    Export the combined model and return timings without writing a report.
    """
    if _state is None:
        raise RuntimeError("No sweep batch.")
    return finish_batch(_state)
