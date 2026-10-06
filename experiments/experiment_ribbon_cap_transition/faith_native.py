"""
Test six fixed certificate-boundary predictions with individual cost accounting.

No retries or target repairs. Geometry findings are non-blocking diagnostics;
construction/host failures, source drift and resource ceilings latch a stop.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT, verify_sources
from experiments.experiment_secure_discrete_ribbon.reporting import matrix_fingerprint

from .array_limits import scaled_case, select_scale
from .faith_fixtures import FaithFixture, faith_fixtures
from .native import NativeGeometryPolicy, NativeProcedure, _run_case
from .native_budget import NativeBudget
from .planning import ShortConnectionFixture, freeze_targets
from .prescribed_twist import PrescribedTwistDiagnostic
from .screen import _fingerprints, _fits

DOCUMENT_NAMES = tuple(
    f"Tube faith - {index + 1} - {label}"
    for index, label in enumerate(
        (
            "shallow 0",
            "quarter +90",
            "arch -90",
            "planar S +180",
            "spatial S -180",
            "skew return -360",
        )
    )
)


@dataclass
class FaithBatch:
    """
    Retain immutable inputs and every disposition, including unattempted slots.
    """

    directory: Path
    fixtures: tuple[FaithFixture, ...]
    sources: dict[str, str]
    production: dict[str, str]
    plan: dict[str, object]
    rows: list[dict[str, object]]
    started: float
    prepared: bool = False
    array_started: bool = False
    finished: bool = False
    stop_reason: str | None = None
    display_seconds: float = 0.0
    display_rows: list[dict[str, object]] = field(default_factory=list)


_state: FaithBatch | None = None


def _checkpoint(state: FaithBatch) -> None:
    """
    Persist plan, case results and timings without overwriting any historical batch.
    """
    (state.directory / "plan.json").write_text(
        json.dumps(state.plan, indent=2, default=str), encoding="utf-8"
    )
    report = {
        "planned": 6,
        "cases": state.rows,
        "stop_reason": state.stop_reason,
        "elapsed_seconds": perf_counter() - state.started,
        "display_seconds": state.display_seconds,
        "display_components": state.display_rows,
        "finished": state.finished,
    }
    (state.directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/faith-native-latest.json"
    ).write_text(json.dumps({"directory": str(state.directory)}), encoding="utf-8")


def _start() -> FaithBatch:
    """
    Register six authored parents and hypothesis before any certificate probes.
    """
    started = perf_counter()
    fixtures = faith_fixtures()
    directory = (
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/faith_native" / uuid4().hex
    )
    directory.mkdir(parents=True, exist_ok=False)
    sources, production = _fingerprints(), verify_sources()
    plan = {
        "question": "Does input tube-certificate acceptance predict complete native construction for six distinct packed curve/twist/end layouts?",
        "parents": [asdict(item) for item in fixtures],
        "sources": sources,
        "production": production,
        "native_predictions": {
            item.case.name + "_certificate_limit": "build_if_curve_certificate_passes"
            for item in fixtures
        },
        "limits": {
            "cases": 6,
            "certificate_probes_per_case": 24,
            "authoring_seconds_per_case": 10,
            "native_attempts": 6,
            "shape_solves": 6,
            "retries": 0,
            "case_seconds": 120,
            "display_seconds": 60,
            "batch_seconds": 840,
            "fusion_rss_kib": 2097152,
        },
        "procedure": "Same master tube,32 nodes,quintic signed diagnostic roll,shared exact caps; original0.8/depth16 curve certificate. No rerouting or bank search.",
        "authoring": "Uniform centerline scaling about fixed sphere center only;19x1.5material,114mm sphere and authored widths fixed. All six selected caps/connection targets freeze before any solve.",
        "authorization": "User-approved six-case absolute-faith construction diagnostic; all geometry/audit findings recorded but non-blocking. Stop at first incomplete/native/host failure or cap/drift; no repair.",
        "retention": "Only result array left open; import rigid39-solid display copies then close each archived owned scratch. Unrelated designs untouched.",
        "scope": "Development variants; no untouched holdouts or full mechanical-compliance claim. Hypothesis, not a proven native certificate.",
        "estimate": "5-7minutes from47-54s prior diagnostic cases; new families uncalibrated; hard14minute scheduling cap.",
        "timing": "Search selection,shape solve(includes input certificate),preflight,native trunk/endings,audits,display/archive/cleanup,total recorded individually; audit cost not solver cost.",
        "selections": [],
        "inputs": [],
    }
    state = FaithBatch(
        directory,
        fixtures,
        sources,
        production,
        plan,
        [
            {"case_id": item.case.name + "_certificate_limit", "status": "not_attempted"}
            for item in fixtures
        ],
        started,
    )
    _checkpoint(state)
    return state


def _remaining(state: FaithBatch) -> float:
    """
    Fail closed on frozen source drift or the approved overall scheduling ceiling.
    """
    remaining = 840 - (perf_counter() - state.started)
    if remaining <= 0 or _fingerprints() != state.sources or verify_sources() != state.production:
        raise RuntimeError("Absolute-faith scheduling cap or frozen source drift.")
    return remaining


def _prepare(state: FaithBatch) -> None:
    """
    Freeze all selected cases and exact targets using at most144 certificate probes.
    """
    selected: list[FaithFixture] = []
    selections: list[dict[str, object]] = []
    inputs: list[dict[str, object]] = []
    for index, fixture in enumerate(state.fixtures):
        NativeBudget(maximum_seconds=_remaining(state)).check("certificate_authoring")
        selection = select_scale(fixture.case)
        case = scaled_case(fixture.case, selection.scale)
        selected.append(replace(fixture, case=case))
        fits = _fits(case)
        targets = freeze_targets(case, *fits, fixture=ShortConnectionFixture(case, turn_degrees=15))
        selections.append({"case_id": case.name, **asdict(selection)})
        inputs.append(
            {
                "fixture": asdict(selected[-1]),
                "caps": [asdict(fit) for fit in fits],
                "targets": asdict(targets),
            }
        )
        state.plan.update(selections=selections, inputs=inputs)
        state.rows[index]["certificate_search_seconds"] = selection.elapsed_seconds
        _checkpoint(state)
    state.fixtures = tuple(selected)
    state.plan["matrix_sha256"] = matrix_fingerprint(tuple(item.case for item in selected))
    state.prepared = True
    _checkpoint(state)


def run_next(_context: object) -> None:
    """
    Schedule one build and import it before closing the archived owned scratch.

    Broad exception handling is an intentional experiment boundary: checkpoint
    the original authoring/host error, preserve partial evidence and latch a stop.
    """
    global _state
    if _state is None:
        _state = _start()
    state = _state
    if state.stop_reason or state.finished:
        raise RuntimeError(state.stop_reason or "Absolute-faith scope finished; no retries.")
    index = sum(row["status"] != "not_attempted" for row in state.rows)
    if index >= 6:
        raise RuntimeError("Absolute-faith builds exhausted; no retries.")
    row = state.rows[index]
    try:
        if not state.prepared:
            _prepare(state)
        from .faith_display import append_and_close, start_array

        if not state.array_started:
            display_start = perf_counter()
            start_array(
                NativeBudget(maximum_seconds=min(60 - state.display_seconds, _remaining(state)))
            )
            state.display_seconds += perf_counter() - display_start
            state.array_started = True
        fixture = state.fixtures[index]
        row["status"] = "started"
        _checkpoint(state)
        budget = NativeBudget(maximum_seconds=min(120.0, _remaining(state)))
        directory = _run_case(
            fixture.case,
            DOCUMENT_NAMES[index],
            None,
            estimated_seconds=None,
            procedure=NativeProcedure.MASTER_TUBE_SHARED_CAPS,
            geometry_policy=NativeGeometryPolicy.OBSERVE_REJECTIONS,
            sphere_diameter_widths=4.0,
            twist_policy=PrescribedTwistDiagnostic(fixture.twist_degrees),
            budget=budget,
            fixture_authoring={
                "parent_case": fixture.parent_case,
                "batch_plan": str(state.directory / "plan.json"),
                "purpose": fixture.purpose,
                "boundary_note": "Six certificate-selected layouts,guide rolls and exact targets frozen before all builds.",
            },
        )
        result = json.loads((directory / "report.json").read_text(encoding="utf-8"))
        row.update(status="completed", report_directory=str(directory), result=result)
        timings = result["timings_seconds"]
        row["individual_times_seconds"] = {
            "certificate_search": row["certificate_search_seconds"],
            "shape_solve": timings.get("search_shape", 0),
            "preflight": timings.get("numerical_validation", 0),
            "native_trunk": timings.get("native_trunk", 0),
            "native_endings": timings.get("native_endings", 0),
            "native_build": result["timing_groups_seconds"]["native_construction"],
            "diagnostic_audits": result["timing_groups_seconds"]["diagnostic_audits"],
            "total_case": result["overall_seconds"],
        }
        if result["built"] != 1:
            state.stop_reason = "Certificate-passing configuration did not completely construct; false acceptance hypothesis, remaining cases not attempted."
        else:
            display_start = perf_counter()
            display = append_and_close(
                DOCUMENT_NAMES[index],
                fixture.case.end_boundary.center,
                index,
                directory,
                NativeBudget(maximum_seconds=min(60 - state.display_seconds, _remaining(state))),
            )
            duration = perf_counter() - display_start
            state.display_seconds += duration
            row["individual_times_seconds"]["display_copy_close"] = duration
            state.display_rows.append(display)
    except Exception as error:
        if row["status"] != "completed":
            row.update(status="error", error=f"{type(error).__name__}: {error}")
        state.stop_reason = f"Absolute-faith authoring/host/display error: {type(error).__name__}: {error}; no retries."
        raise
    finally:
        _checkpoint(state)
    print(
        json.dumps(
            {
                "directory": str(state.directory),
                "case": row["case_id"],
                "built": result["built"],
                "times": row["individual_times_seconds"],
                "stop": state.stop_reason,
            }
        )
    )


def finish(_context: object) -> None:
    """
    Archive the complete or stopped array, leaving its source evidence unchanged.
    """
    if _state is None or not _state.array_started or _state.finished:
        raise RuntimeError("No unfinished owned array is available.")
    if not _state.stop_reason and any(row["status"] == "not_attempted" for row in _state.rows):
        raise RuntimeError("Approved builds remain; array finish not yet scheduled.")
    from .faith_display import finish_array

    start = perf_counter()
    finish_array(
        _state.directory,
        NativeBudget(maximum_seconds=min(60 - _state.display_seconds, _remaining(_state))),
    )
    _state.display_seconds += perf_counter() - start
    _state.finished = True
    _checkpoint(_state)
    print(
        json.dumps(
            {
                "directory": str(_state.directory),
                "display_seconds": _state.display_seconds,
                "stop": _state.stop_reason,
            }
        )
    )
