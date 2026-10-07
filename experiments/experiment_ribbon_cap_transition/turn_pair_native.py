"""
Build the approved90/180-turn pair with requested360 twist reduced to0.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT, verify_sources

from .native import NativeGeometryPolicy, NativeProcedure, _run_case
from .native_budget import NativeBudget
from .planning import ShortConnectionFixture, freeze_targets
from .prescribed_twist import PrescribedTwistDiagnostic
from .reflected_twist import ReflectedTwistDiagnostic
from .screen import _fingerprints, _fits
from .turn_pair import CERTIFICATE_RADIUS_MM, TurnFixture, turn_fixtures

ARRAY_NAME = "Tube ribbon 4x - 90 and180 turns - requested360 bounded0"


@dataclass(frozen=True)
class TurnExperiment:
    """
    Name a roll-policy experiment without changing the fixed boundary layouts.
    """

    name: str
    array_name: str
    policy: PrescribedTwistDiagnostic


ZERO_ROLL = TurnExperiment("turn_pair", ARRAY_NAME, PrescribedTwistDiagnostic(0))
REFLECTED_ROLL = TurnExperiment(
    "turn_pair_reflected",
    "Tube ribbon 4x - 90 and180 turns - roll0 to180 to0",
    ReflectedTwistDiagnostic(360),
)


@dataclass
class TurnBatch:
    """
    Retain two frozen configurations and every outcome including unattempted slots.
    """

    directory: Path
    fixtures: tuple[TurnFixture, ...]
    plan: dict[str, object]
    rows: list[dict[str, object]]
    started: float
    experiment: TurnExperiment
    array_started: bool = False
    finished: bool = False
    stop_reason: str | None = None
    display_seconds: float = 0.0
    resource_samples: list[dict[str, object]] = field(default_factory=list)


_state: TurnBatch | None = None


def _checkpoint(state: TurnBatch) -> None:
    """
    Write only this batch's new evidence, preserving every historical report.
    """
    report = {
        "planned": 2,
        "cases": state.rows,
        "elapsed_seconds": perf_counter() - state.started,
        "display_seconds": state.display_seconds,
        "resource_samples": state.resource_samples,
        "stop_reason": state.stop_reason,
        "finished": state.finished,
    }
    (state.directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def _start(experiment: TurnExperiment = ZERO_ROLL) -> TurnBatch:
    """
    Freeze both complete cap/connection layouts before either shape solve or build.
    """
    started = perf_counter()
    fixtures = turn_fixtures()
    inputs: list[dict[str, object]] = []
    for fixture in fixtures:
        case = fixture.case
        fits = _fits(case)
        targets = freeze_targets(case, *fits, fixture=ShortConnectionFixture(case, turn_degrees=15))
        inputs.append(
            {
                "fixture": asdict(fixture),
                "caps": [asdict(f) for f in fits],
                "targets": asdict(targets),
            }
        )
    directory = (
        PROJECT_ROOT
        / "artifacts/verification/ribbon_cap_transition"
        / experiment.name
        / uuid4().hex
    )
    directory.mkdir(parents=True, exist_ok=False)
    baseline = (
        PROJECT_ROOT
        / "artifacts/verification/ribbon_cap_transition/turn_pair/df07c6c851004737b3ece9c552c61942/plan.json"
    )
    baseline_bytes = baseline.read_bytes()
    if json.loads(json.dumps(inputs, default=str)) != json.loads(baseline_bytes)["inputs"]:
        raise RuntimeError("Zero-roll control inputs changed; no native scheduling.")
    plan = {
        "question": "Can tight90-degree and180-degree path turns build with undeformed planar sections and the declared bounded longitudinal roll field?",
        "roll_field": experiment.policy.field_description,
        "policy_requested_degrees": experiment.policy.degrees,
        "baseline_plan": str(baseline),
        "baseline_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
        "inputs": inputs,
        "sources": _fingerprints(),
        "production": verify_sources(),
        "radius_mm": CERTIFICATE_RADIUS_MM,
        "radius_provenance": "Existing curve_limit/8591cac8b216442d80c05e2a8513ff43 passing semicircle radius;90 uses its first quarter-arc. No new search.",
        "procedure": "Same master tube/shared exact caps/32 planar original lobe sections/19x1.5mm material/4x114mm sphere/both reverse-loft ending sets. Fixed authored centerlines and targets;declared roll field;no warp,rerouting,search,fallback or tolerance change.",
        "native_prediction": "Two complete builds predicted; unproven hypothesis, stop first incomplete build.",
        "authorization": "User approved2 builds,120s/case,300s overall,2GiB sampledRSS,no search/retries;warnings diagnostic/nonblocking;all findings retained.",
        "policy_revision": "Continue user planar/bounded-twist experiment on this two-case scope only;requested360 ends at0 with declared intermediate motion,ordered endpoint orientation preserved,extra winding removed. Reflected mode was explicitly confirmed as longitudinal0 ->180 ->0 rather than an erased zero-roll field. Historical bank-rate diagnostic policy retained explicitly,not a new rate certificate.",
        "limits": {
            "cases": 2,
            "shape_solves": 2,
            "native_attempts": 2,
            "search_probes": 0,
            "retries": 0,
            "case_seconds": 120,
            "batch_seconds": 300,
            "display_seconds": 60,
            "rss_kib": 2097152,
        },
        "coverage": "Two fixed planar-turn development layouts sharing arc lineage;not two distinct broad families,untouched holdouts or full mechanical certification. Requested360 is not actual360 winding.",
        "retention": "New side-by-side array stays open;archive/close only new successful scratch after rigid39-solid copy;failed scratch retained. All prior documents untouched.",
        "timing": "Shape solve includes input certificate,excludes historical radius search;preflight,native trunk/endings,diagnostic audits,display/archive,total separate. Expected about2minutes,hard5minute scheduling limit;in-flight kernel cannot be cancelled by this gate.",
    }
    plan = json.loads(json.dumps(plan, default=str))
    (directory / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    state = TurnBatch(
        directory,
        fixtures,
        plan,
        [{"case_id": f.case.name, "status": "not_attempted"} for f in fixtures],
        started,
        experiment,
    )
    _checkpoint(state)
    return state


def start_reflected(_context: object) -> None:
    """
    Register the corrected two-case scope once; build only on a later run_next.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Turn batch already initialized; no replacement or retry.")
    _state = _start(REFLECTED_ROLL)


def _budget(state: TurnBatch, seconds: float) -> NativeBudget:
    """
    Check overall scheduling/source integrity and retain between-stage RSS evidence.
    """
    remaining = 300 - (perf_counter() - state.started)
    if (
        remaining <= 0
        or _fingerprints() != state.plan["sources"]
        or verify_sources() != state.plan["production"]
        or hashlib.sha256(Path(state.plan["baseline_plan"]).read_bytes()).hexdigest()
        != state.plan["baseline_sha256"]
    ):
        raise RuntimeError("Turn-pair budget or source drift; no further scheduling.")
    budget = NativeBudget(maximum_seconds=min(seconds, remaining))
    budget.check("between_stages")
    state.resource_samples.extend(budget.samples)
    return budget


def run_next(_context: object) -> None:
    """
    Schedule one complete configuration, latching all host/construction failures.

    Broad exception handling is intentional at this experiment boundary: preserve
    partial native evidence and the original error rather than rolling back it.
    """
    global _state
    if _state is None:
        _state = _start()
    state = _state
    if state.stop_reason or state.finished:
        raise RuntimeError("Turn-pair batch stopped or finished; no retries.")
    index = sum(row["status"] != "not_attempted" for row in state.rows)
    if index >= 2:
        raise RuntimeError("Both build slots exhausted.")
    row = state.rows[index]
    try:
        from .faith_display import append_and_close, start_array

        if not state.array_started:
            started = perf_counter()
            start_array(_budget(state, 60), array_name=state.experiment.array_name)
            state.display_seconds += perf_counter() - started
            state.array_started = True
        fixture = state.fixtures[index]
        name = f"{state.experiment.name} - turn{fixture.turn_degrees:g} - endroll0"
        row["status"] = "started"
        _checkpoint(state)
        directory = _run_case(
            fixture.case,
            name,
            None,
            estimated_seconds=None,
            procedure=NativeProcedure.MASTER_TUBE_SHARED_CAPS,
            budget=_budget(state, 120),
            sphere_diameter_widths=4.0,
            geometry_policy=NativeGeometryPolicy.OBSERVE_REJECTIONS,
            twist_policy=state.experiment.policy,
            fixture_authoring={
                "parent_case": fixture.parent_case,
                "batch_plan": str(state.directory / "plan.json"),
                "purpose": state.experiment.policy.field_description,
            },
        )
        result = json.loads((directory / "report.json").read_text(encoding="utf-8"))
        row.update(status="completed", report_directory=str(directory), result=result)
        if result["built"] != 1:
            state.stop_reason = (
                "First incomplete native construction; remaining case not attempted."
            )
        else:
            started = perf_counter()
            row["display"] = append_and_close(
                name,
                fixture.case.end_boundary.center,
                index,
                directory,
                _budget(state, 60 - state.display_seconds),
                array_name=state.experiment.array_name,
            )
            row["display_seconds"] = perf_counter() - started
            state.display_seconds += row["display_seconds"]
    except Exception as error:
        row.update(status="error", error=f"{type(error).__name__}: {error}")
        state.stop_reason = row["error"]
    finally:
        _checkpoint(state)
    print(
        json.dumps(
            {
                "directory": str(state.directory),
                "case": row["case_id"],
                "built": row.get("result", {}).get("built"),
                "stop": state.stop_reason,
            }
        )
    )


def finish(_context: object) -> None:
    """
    Archive/focus the completed or stopped array, leaving prior documents alone.
    """
    if _state is None or not _state.array_started or _state.finished:
        raise RuntimeError("No unfinished turn-pair array.")
    state = _state
    if not state.stop_reason and any(row["status"] == "not_attempted" for row in state.rows):
        raise RuntimeError("Approved build remains.")
    from .faith_display import finish_array

    started = perf_counter()
    finish_array(
        state.directory,
        _budget(state, 60 - state.display_seconds),
        array_name=state.experiment.array_name,
    )
    state.display_seconds += perf_counter() - started
    state.finished = True
    _checkpoint(state)
    print(json.dumps({"directory": str(state.directory), "stop": state.stop_reason}))
