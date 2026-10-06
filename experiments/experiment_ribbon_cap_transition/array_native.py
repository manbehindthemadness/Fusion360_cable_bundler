"""
Freeze and schedule the approved three-case full-turn array one native call at a time.

No solver changes, retries, tuning or document closing. Stop on any known hard
geometry finding, incomplete construction/audit, source drift or resource limit.
All dispositions remain recorded; display copies do not add geometry coverage.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT, verify_sources
from experiments.experiment_secure_discrete_ribbon.reporting import matrix_fingerprint

from .array_fixtures import ArrayFixture, array_fixtures
from .native import NativeGeometryPolicy, NativeProcedure, _run_case
from .native_budget import NativeBudget
from .planning import ShortConnectionFixture, freeze_targets
from .screen import _fingerprints, _fits

DOCUMENT_NAMES = (
    "Tube ribbon array - 1 tight U-turn 360",
    "Tube ribbon array - 2 spatial S 360",
    "Tube ribbon array - 3 orthogonal bends 360",
)


@dataclass
class ArrayBatch:
    """
    Retain frozen inputs, disposition rows and a latched scheduling stop.
    """

    directory: Path
    fixtures: tuple[ArrayFixture, ...]
    sources: dict[str, str]
    production: dict[str, str]
    rows: list[dict[str, object]]
    started: float
    stop_reason: str | None = None


_state: ArrayBatch | None = None


def _checkpoint(state: ArrayBatch) -> None:
    """
    Preserve all rows, including failures and unattempted cases, without overwriting history.
    """
    report = {
        "planned": len(state.fixtures),
        "cases": state.rows,
        "stop_reason": state.stop_reason,
        "elapsed_seconds": perf_counter() - state.started,
    }
    (state.directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    latest = PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/array-native-latest.json"
    latest.write_text(json.dumps({"directory": str(state.directory)}), encoding="utf-8")


def _freeze() -> ArrayBatch:
    """
    Register every case, cap and branch target before the first complete-ribbon solve.
    """
    started = perf_counter()
    fixtures = array_fixtures()
    directory = (
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/array_native" / uuid4().hex
    )
    directory.mkdir(parents=True, exist_ok=False)
    sources, production = _fingerprints(), verify_sources()
    inputs = []
    for fixture in fixtures:
        case = fixture.case
        fits = _fits(case)
        targets = freeze_targets(case, *fits, fixture=ShortConnectionFixture(case, turn_degrees=15))
        inputs.append(
            {
                "fixture": asdict(fixture),
                "caps": [asdict(fit) for fit in fits],
                "targets": asdict(targets),
            }
        )
    plan = {
        "question": "Does the unchanged tube-first full-turn diagnostic construct three distinct bend families with both ending sets?",
        "procedure": NativeProcedure.MASTER_TUBE_FULL_TURN.value,
        "inputs": inputs,
        "matrix_sha256": matrix_fingerprint(tuple(fixture.case for fixture in fixtures)),
        "sources": sources,
        "production": production,
        "limits": {
            "cases": 3,
            "shape_solves": 3,
            "native_attempts": 3,
            "retries": 0,
            "refinements": 0,
            "case_seconds": 120,
            "batch_seconds": 360,
            "fusion_rss_kib": 2097152,
        },
        "estimate": "Two to three minutes from prior 47-49 second native diagnostics; new families uncalibrated.",
        "native_predictions": {fixture.case.name: "unknown" for fixture in fixtures},
        "authoring": "Two scaffold-only calls freeze transported B-roll before targets; zero full ribbon solves or radius searches during authoring.",
        "retention": "Retain all existing/new documents; display copies only after successful batch, no new coverage.",
        "display": "Three rigid, sphere-centered placements at X=-140,0,+140 mm; no geometric deformation.",
        "scope": "One repeated development reference plus two new roll variants from distinct bend families; no unseen holdouts or full master-rule acceptance.",
        "exceptions": "Explicit bank-rate diagnostic exception ONLY. Length goals warn; spacing, curvature, containment, identities, exact cap flow and end allowance unchanged.",
        "stops": "Any hard finding, incomplete construction/named audit, unexpected error, resource ceiling or source drift; no repair/retry.",
    }
    (directory / "plan.json").write_text(json.dumps(plan, indent=2, default=str), encoding="utf-8")
    state = ArrayBatch(
        directory,
        fixtures,
        sources,
        production,
        [{"case_id": fixture.case.name, "status": "not_attempted"} for fixture in fixtures],
        started,
    )
    _checkpoint(state)
    return state


def run_next(_context: object) -> None:
    """
    Schedule one selected configuration and stop the remaining array on failure.

    Unexpected host exceptions are an intentional fail-soft reporting boundary:
    record the original error, preserve partial documents, latch stop and re-raise.
    """
    global _state
    if _state is None:
        _state = _freeze()
    state = _state
    if state.stop_reason is not None:
        raise RuntimeError(state.stop_reason)
    index = sum(row["status"] != "not_attempted" for row in state.rows)
    if index >= len(state.fixtures):
        raise RuntimeError("Approved array exhausted; no retry.")
    remaining = 360 - (perf_counter() - state.started)
    if remaining <= 0 or _fingerprints() != state.sources or verify_sources() != state.production:
        state.stop_reason = "Array scheduling ceiling or source drift."
        _checkpoint(state)
        raise RuntimeError(state.stop_reason)
    row, fixture = state.rows[index], state.fixtures[index]
    row["status"] = "started"
    _checkpoint(state)
    try:
        directory = _run_case(
            fixture.case,
            DOCUMENT_NAMES[index],
            None,
            estimated_seconds=None,
            procedure=NativeProcedure.MASTER_TUBE_FULL_TURN,
            sphere_diameter_widths=4.0,
            geometry_policy=NativeGeometryPolicy.STOP_ON_KNOWN_FINDINGS,
            budget=NativeBudget(maximum_seconds=min(120.0, remaining)),
            fixture_authoring={
                "parent_case": fixture.parent_case,
                "batch_plan": str(state.directory / "plan.json"),
                "purpose": fixture.purpose,
                "boundary_note": "Complete array inputs authored and frozen upfront; B-width matches unrolled transport for explicit360 winding.",
            },
        )
        result = json.loads((directory / "report.json").read_text(encoding="utf-8"))
        row.update(status="completed", report_directory=str(directory), result=result)
        if (
            result["built"] != 1
            or result["preflight"]["failures"]
            or result["native_result"]["status"] != "built_and_audited"
        ):
            state.stop_reason = "Array hard finding, incomplete construction or named audit failure; remaining cases not attempted."
    except Exception as error:
        row.update(status="error", error=f"{type(error).__name__}: {error}")
        state.stop_reason = "Array harness error; remaining cases not attempted."
        raise
    finally:
        _checkpoint(state)
    print(
        json.dumps(
            {
                "batch_directory": str(state.directory),
                "case_id": fixture.case.name,
                "built": result["built"],
                "stop_reason": state.stop_reason,
            }
        )
    )


def show_array(_context: object) -> None:
    """
    Assemble rigid display copies only after three complete cases and clean named audits.
    """
    if (
        _state is None
        or _state.stop_reason is not None
        or any(row["status"] != "completed" for row in _state.rows)
    ):
        raise RuntimeError("The array batch is incomplete or stopped; no display copy scheduling.")
    from .array_display import create_array

    if _fingerprints() != _state.sources or verify_sources() != _state.production:
        raise RuntimeError("Array source drift; no display copy scheduling.")
    remaining = 360 - (perf_counter() - _state.started)
    if remaining <= 0:
        raise RuntimeError("Array scheduling cap reached; source documents retained.")
    create_array(
        DOCUMENT_NAMES,
        tuple(fixture.case.end_boundary.center for fixture in _state.fixtures),
        _state.directory,
        NativeBudget(maximum_seconds=remaining),
    )
