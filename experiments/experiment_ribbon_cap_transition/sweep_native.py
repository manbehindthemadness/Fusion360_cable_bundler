"""
Replay the approved six-case four-width array with swept trunks and lofted endings.

Stop on the first incomplete build, host/source failure or resource cap. Retain
existing documents; archive/close only successful new owned case scratches.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT, verify_sources

from .faith_fixtures import FaithFixture
from .native import NativeProcedure, TrunkConstruction, _run_case
from .native_budget import NativeBudget
from .prescribed_twist import PrescribedTwistDiagnostic
from .screen import _fingerprints
from .sweep_replay import frozen_sweep_fixtures

PARENT = (
    PROJECT_ROOT
    / "artifacts/verification/ribbon_cap_transition/faith_native/435bedfe25f245cc86db435fc01dddf0/plan.json"
)
ARRAY_NAME = "Tube ribbon 4x - trunk sweep replay"


@dataclass
class SweepBatch:
    """
    Retain all six dispositions and original inputs, including unattempted cases.
    """

    directory: Path
    fixtures: tuple[FaithFixture, ...]
    sources: dict[str, str]
    parent_hash: str
    started: float
    rows: list[dict[str, object]] = field(default_factory=list)
    display_seconds: float = 0
    array_started: bool = False
    finished: bool = False
    stop_reason: str | None = None


_state: SweepBatch | None = None


def _checkpoint(state: SweepBatch) -> None:
    """
    Write new evidence only, preserving unsuccessful and unattempted slots.
    """
    report = {
        "planned": 6,
        "cases": state.rows,
        "elapsed_seconds": perf_counter() - state.started,
        "display_seconds": state.display_seconds,
        "stop_reason": state.stop_reason,
        "finished": state.finished,
    }
    (state.directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def _start() -> SweepBatch:
    """
    Freeze six original packed cases and explicit diagnostic scope before authoring.
    """
    started = perf_counter()
    fixtures = frozen_sweep_fixtures(PARENT)
    sources = _fingerprints()
    production = verify_sources()
    parent_hash = hashlib.sha256(PARENT.read_bytes()).hexdigest()
    directory = (
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/sweep_native" / uuid4().hex
    )
    directory.mkdir(parents=True, exist_ok=False)
    plan = {
        "question": "Replay the six open-array configurations with swept trunks, no total-roll limiter.",
        "inputs": [asdict(item) for item in fixtures],
        "parent": str(PARENT),
        "parent_sha256": parent_hash,
        "sources": sources,
        "production": production,
        "native_prediction": "unknown for all six; numerical findings are not kernel predictions",
        "procedure": "Fixed certificate-packed curves and exact caps/targets; single original lobe profile; perpendicular native sweep with requested signed total twist; unchanged reverse-loft endings. No rails, flex, search, retries or fallback.",
        "interpolation": "Native sweep roll distribution unknown; quintic numerical reference is not the native sweep field. Cap alignment checked by existing native ending handoff; interior native banking not certified.",
        "diagnostic": "Known rule findings recorded, not repaired or treated as compliance; includes no-wide-axis-bend reference checks. Historical4x scope, not current5x evidence.",
        "authorization": "User approved six cases,120s/case,840s total,2GiB RSS,no search/retries,first incomplete-build stop; preserve old array and retain new array.",
        "limits": {
            "cases": 6,
            "native_attempts": 6,
            "search": 0,
            "retries": 0,
            "case_seconds": 120,
            "batch_seconds": 840,
            "display_seconds": 60,
            "rss_kib": 2097152,
        },
        "timing": "Cached certificate-scale replay excludes search; shape/preflight, sweep/endings, diagnostic audits, archive/display and overall timings separate.",
    }
    (directory / "plan.json").write_text(json.dumps(plan, indent=2, default=str), encoding="utf-8")
    state = SweepBatch(directory, fixtures, sources, parent_hash, started)
    state.rows = [
        {"case_id": f.case.name, "twist_degrees": f.twist_degrees, "status": "not_attempted"}
        for f in fixtures
    ]
    _checkpoint(state)
    return state


def _budget(state: SweepBatch, seconds: float) -> NativeBudget:
    """
    Gate scheduling on approved cumulative time and immutable source/fixture state.
    """
    remaining = 840 - (perf_counter() - state.started)
    if (
        remaining <= 0
        or _fingerprints() != state.sources
        or hashlib.sha256(PARENT.read_bytes()).hexdigest() != state.parent_hash
    ):
        raise RuntimeError("Sweep replay time/source/fixture gate; no next operation.")
    verify_sources()
    budget = NativeBudget(maximum_seconds=min(seconds, remaining))
    budget.check("between_operations")
    return budget


def run_next(_context: object) -> None:
    """
    Attempt one complete configuration, preserving all errors without retries.

    Broad capture is intentional at the experiment transaction boundary so
    failed sketches/bodies remain inspectable and subsequent scheduling stops.
    """
    global _state
    if _state is None:
        _state = _start()
    state = _state
    if state.stop_reason or state.finished:
        raise RuntimeError("Sweep batch stopped or finished; no retry.")
    index = sum(row["status"] != "not_attempted" for row in state.rows)
    if index >= 6:
        raise RuntimeError("Six approved slots exhausted.")
    row = state.rows[index]
    try:
        from .faith_display import append_and_close, start_array

        if not state.array_started:
            started = perf_counter()
            start_array(_budget(state, 60), array_name=ARRAY_NAME)
            state.display_seconds += perf_counter() - started
            state.array_started = True
        fixture = state.fixtures[index]
        name = f"Trunk sweep replay {index + 1} - {fixture.twist_degrees:g}deg"
        row["status"] = "started"
        _checkpoint(state)
        directory = _run_case(
            fixture.case,
            name,
            None,
            estimated_seconds=None,
            procedure=NativeProcedure.MASTER_TUBE_SHARED_CAPS,
            sphere_diameter_widths=4,
            twist_policy=PrescribedTwistDiagnostic(fixture.twist_degrees),
            trunk_construction=TrunkConstruction.SWEEP,
            budget=_budget(state, 120),
            fixture_authoring={
                "batch_plan": str(state.directory / "plan.json"),
                "parent_case": fixture.case.name,
            },
        )
        result = json.loads((directory / "report.json").read_text(encoding="utf-8"))
        row.update(status="completed", report_directory=str(directory), result=result)
        if result["built"] != 1:
            state.stop_reason = "First incomplete construction; remaining cases unattempted."
        else:
            started = perf_counter()
            row["display"] = append_and_close(
                name,
                fixture.case.end_boundary.center,
                index,
                directory,
                _budget(state, 60 - state.display_seconds),
                array_name=ARRAY_NAME,
            )
            state.display_seconds += perf_counter() - started
    except Exception as error:
        row.update(status="error", error=f"{type(error).__name__}: {error}")
        state.stop_reason = str(row["error"])
    finally:
        _checkpoint(state)
    print(
        json.dumps(
            {
                "directory": str(state.directory),
                "case": row["case_id"],
                "status": row["status"],
                "stop": state.stop_reason,
            }
        )
    )


def finish(_context: object) -> None:
    """
    Archive/focus completed or stopped array without closing a failed scratch.
    """
    if _state is None or _state.finished or not _state.array_started:
        raise RuntimeError("No unfinished sweep array.")
    state = _state
    if not state.stop_reason and any(row["status"] == "not_attempted" for row in state.rows):
        raise RuntimeError("Approved sweep cases remain.")
    from .faith_display import finish_array

    started = perf_counter()
    finish_array(state.directory, _budget(state, 60 - state.display_seconds), array_name=ARRAY_NAME)
    state.display_seconds += perf_counter() - started
    state.finished = True
    _checkpoint(state)
    print(json.dumps({"directory": str(state.directory), "stop": state.stop_reason}))
