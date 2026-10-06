"""
Run the user-approved three-case native tube diagnostic without closing documents.

Requires idle Fusion and the local development server. Invoke run_next once per
case; failures stop the batch, preserving partial documents and all dispositions.
No tuning, retries, production writes or automatic continuation are permitted.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT, verify_sources
from experiments.experiment_secure_discrete_ribbon.reporting import matrix_fingerprint

from .native import NativeProcedure, _run_case
from .native_budget import NativeBudget
from .planning import ShortConnectionFixture, freeze_targets
from .regression_cases import comparison_cases
from .screen import _fingerprints, _fits

CASE_IDS = (
    "spatial_s_twist45_19x1.5",
    "regression_asymmetric_arch",
    "regression_twisted_quarter",
)
DOCUMENT_NAMES = (
    "Tube ribbon 5x - spatial S +45",
    "Tube ribbon 5x - asymmetric arch",
    "Tube ribbon 5x - twisted quarter",
)
_state: dict[str, object] | None = None


def _write(path: Path, value: dict[str, object]) -> None:
    """
    Checkpoint unique generated evidence, including unattempted configurations.
    """
    path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")


def run_next(_context: object) -> None:
    """
    Schedule exactly one approved case, retaining every old and new document.

    A known twisted-quarter numerical rejection is explicitly diagnostic. Any
    construction failure, unexpected exception or resource/source gate stops
    further calls. Native prediction is unknown for all three configurations.
    """
    global _state
    cases_by_id = {case.name: case for case in comparison_cases()}
    cases = tuple(cases_by_id[name] for name in CASE_IDS)
    if _state is None:
        directory = (
            PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/tube_native" / uuid4().hex
        )
        directory.mkdir(parents=True, exist_ok=False)
        inputs = []
        for case in cases:
            fits = _fits(case)
            targets = freeze_targets(
                case, *fits, fixture=ShortConnectionFixture(case, turn_degrees=15)
            )
            inputs.append(
                {
                    "case": asdict(case),
                    "caps": [asdict(fit) for fit in fits],
                    "targets": asdict(targets),
                }
            )
        plan = {
            "question": "Can the unchanged cold master-tube solver construct the preselected original, translated-lane control and known-rejected twist challenge?",
            "procedure": NativeProcedure.MASTER_TUBE.value,
            "inputs": inputs,
            "matrix_sha256": matrix_fingerprint(cases),
            "sources": _fingerprints(),
            "production": verify_sources(),
            "native_predictions": {name: "unknown" for name in CASE_IDS},
            "known_rejections": {
                CASE_IDS[
                    2
                ]: "Sampled lane radius below 4.5 mm and combined end allowance; diagnostic only."
            },
            "limits": {
                "shape_solves": 3,
                "native_attempts": 3,
                "refinements": 0,
                "case_seconds": 120,
                "batch_seconds": 360,
                "fusion_rss_kib": 2 * 1024 * 1024,
            },
            "estimate": "Prior native diagnostics 16–36 seconds; first tube case calibrates. In-flight kernel cancellation is not guaranteed.",
            "retention": "User explicitly overrides one-scratch policy: retain every new document, including partial failures; never close existing documents.",
            "coverage": "Three examined development configurations, no untouched validation cases. Five-width sphere, unchanged spacing/macaronic/cap rules, length accuracy warn-but-proceed.",
            "stops": "Construction failure, unexpected error/regression, source drift, scheduling or memory ceiling; no retry or repair.",
        }
        _write(directory / "plan.json", plan)
        _state = {
            "directory": str(directory),
            "plan": plan,
            "started": perf_counter(),
            "stop_reason": None,
            "cases": [{"case_id": name, "status": "not_attempted"} for name in CASE_IDS],
        }
    state = _state
    directory = Path(str(state["directory"]))
    rows = state["cases"]
    if not isinstance(rows, list):
        raise TypeError("Batch cases must be a list.")
    if state["stop_reason"] is not None:
        raise RuntimeError(str(state["stop_reason"]))
    index = sum(row["status"] != "not_attempted" for row in rows)
    if index >= len(cases):
        raise RuntimeError("Approved three-case batch exhausted; no retry.")
    plan = state["plan"]
    remaining = 360 - (perf_counter() - float(state["started"]))
    if (
        remaining <= 0
        or _fingerprints() != plan["sources"]
        or verify_sources() != plan["production"]
    ):
        state["stop_reason"] = "Batch scheduling ceiling or source drift."
        _write(directory / "report.json", state)
        raise RuntimeError(str(state["stop_reason"]))
    row = rows[index]
    row["status"] = "started"
    _write(directory / "report.json", state)
    try:
        result_directory = _run_case(
            cases[index],
            DOCUMENT_NAMES[index],
            None,
            estimated_seconds=None,
            procedure=NativeProcedure.MASTER_TUBE,
            budget=NativeBudget(maximum_seconds=min(120.0, remaining)),
        )
        result = json.loads((result_directory / "report.json").read_text(encoding="utf-8"))
        row.update(status="completed", report_directory=str(result_directory), result=result)
        if result["built"] != 1:
            state["stop_reason"] = (
                "Complete native construction failed; remaining cases not attempted."
            )
    except Exception as error:
        # Diagnostic fail-soft boundary: retain the partial design and stop,
        # recording the original exception rather than retrying or concealing it.
        row.update(status="error", error=f"{type(error).__name__}: {error}")
        state["stop_reason"] = "Native harness error; remaining cases not attempted."
        raise
    finally:
        state["elapsed_seconds"] = perf_counter() - float(state["started"])
        _write(directory / "report.json", state)
        _write(
            PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/tube-native-latest.json",
            {"directory": str(directory)},
        )
    print(
        json.dumps(
            {
                "batch_directory": str(directory),
                "case_id": cases[index].name,
                "built": row["result"]["built"],
                "stop_reason": state["stop_reason"],
            }
        )
    )
