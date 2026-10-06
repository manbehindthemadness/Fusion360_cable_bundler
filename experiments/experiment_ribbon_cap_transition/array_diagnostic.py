"""
Renew only the two unbuilt array specimens under the user's diagnostic waiver.

Keep numerical and audit findings, fixed inputs and historical reports. No retries,
tuning or document closing; incomplete native construction still stops scheduling.
"""

from __future__ import annotations

import json
from time import perf_counter

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT, verify_sources

from .array_native import DOCUMENT_NAMES, ArrayBatch, _checkpoint, _freeze
from .native import NativeGeometryPolicy, NativeProcedure, _run_case
from .native_budget import NativeBudget
from .screen import _fingerprints

ORIGINAL = "160505c123a84fe1a4df7fd69eaf68a8"
DIAGNOSTIC_NAMES = (DOCUMENT_NAMES[0], *(name + " - diagnostic" for name in DOCUMENT_NAMES[1:]))
_state: ArrayBatch | None = None


def _renew() -> ArrayBatch:
    """
    Compare every frozen input with the stopped batch before scheduling two builds.
    """
    original = PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/array_native" / ORIGINAL
    old_plan = json.loads((original / "plan.json").read_text(encoding="utf-8"))
    old_report = json.loads((original / "report.json").read_text(encoding="utf-8"))
    state = _freeze()
    path = state.directory / "plan.json"
    plan = json.loads(path.read_text(encoding="utf-8"))
    if plan["inputs"] != old_plan["inputs"] or old_report["cases"][0]["result"]["built"] != 1:
        raise RuntimeError("Renewal inputs or completed U-turn evidence differ; no build.")
    plan.update(
        renewal_of=str(original),
        authorization="User: ignore the violations and build the solids. Numerical/audit findings remain reported, not construction gates.",
        reused_case=old_report["cases"][0],
        stops="Incomplete native construction, host error, source drift or resource cap; no retries.",
    )
    plan["limits"].update(cases=2, shape_solves=2, native_attempts=2, batch_seconds=240)
    state.fixtures = state.fixtures[1:]
    state.rows = state.rows[1:]
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    _checkpoint(state)
    return state


def run_next(_context: object) -> None:
    """
    Build one remaining specimen despite recorded rule findings, retaining failures.

    The broad exception boundary intentionally checkpoints host errors and prevents
    subsequent scheduling while preserving every partial scratch document.
    """
    global _state
    if _state is None:
        _state = _renew()
    state = _state
    if state.stop_reason is not None:
        raise RuntimeError(state.stop_reason)
    index = sum(row["status"] != "not_attempted" for row in state.rows)
    if index >= 2:
        raise RuntimeError("Diagnostic renewal exhausted; no retry.")
    remaining = 240 - (perf_counter() - state.started)
    if remaining <= 0 or _fingerprints() != state.sources or verify_sources() != state.production:
        state.stop_reason = "Diagnostic resource ceiling or source drift."
        _checkpoint(state)
        raise RuntimeError(state.stop_reason)
    row, fixture = state.rows[index], state.fixtures[index]
    row["status"] = "started"
    _checkpoint(state)
    try:
        directory = _run_case(
            fixture.case,
            DIAGNOSTIC_NAMES[index + 1],
            None,
            estimated_seconds=None,
            procedure=NativeProcedure.MASTER_TUBE_FULL_TURN,
            sphere_diameter_widths=4.0,
            geometry_policy=NativeGeometryPolicy.OBSERVE_REJECTIONS,
            budget=NativeBudget(maximum_seconds=min(120.0, remaining)),
            fixture_authoring={
                "parent_case": fixture.parent_case,
                "batch_plan": str(state.directory / "plan.json"),
                "purpose": fixture.purpose,
                "boundary_note": "Unchanged stopped-array inputs; user-authorized diagnostic construction despite findings.",
            },
        )
        result = json.loads((directory / "report.json").read_text(encoding="utf-8"))
        row.update(status="completed", report_directory=str(directory), result=result)
        if result["built"] != 1:
            state.stop_reason = "Incomplete diagnostic construction; remaining cases not attempted."
    except Exception as error:
        row.update(status="error", error=f"{type(error).__name__}: {error}")
        state.stop_reason = "Diagnostic host error; remaining cases not attempted."
        raise
    finally:
        _checkpoint(state)
    print(
        json.dumps(
            {
                "directory": str(state.directory),
                "case": fixture.case.name,
                "built": result["built"],
                "stop": state.stop_reason,
            }
        )
    )


def show_array(_context: object) -> None:
    """
    Display the reused U-turn and two complete diagnostic builds without acceptance claims.
    """
    if (
        _state is None
        or _state.stop_reason
        or any(row["status"] != "completed" for row in _state.rows)
    ):
        raise RuntimeError("Diagnostic builds incomplete; no display assembly.")
    if _fingerprints() != _state.sources or verify_sources() != _state.production:
        raise RuntimeError("Diagnostic source drift; no display assembly.")
    from .array_display import create_array
    from .array_fixtures import array_fixtures

    remaining = 240 - (perf_counter() - _state.started)
    if remaining <= 0:
        raise RuntimeError("Diagnostic resource ceiling; source documents retained.")
    create_array(
        DIAGNOSTIC_NAMES,
        tuple(item.case.end_boundary.center for item in array_fixtures()),
        _state.directory,
        NativeBudget(maximum_seconds=remaining),
    )
