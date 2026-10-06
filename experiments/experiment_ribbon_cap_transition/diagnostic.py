"""
Run the approved eight-configuration numerical decomposition without native work.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT, verify_sources
from experiments.experiment_ribbon_diagnosis.preflight import EndPlan
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon
from experiments.experiment_secure_discrete_ribbon.reporting import matrix_fingerprint

from .accuracy import LENGTH_GOAL_FAILURES
from .fixtures import development_cases
from .planning import ShortConnectionFixture, freeze_targets, inspect_candidate
from .screen import _fingerprints, _fits
from .solver import solve_candidate
from .stages import StageRecorder

PREVIOUS_REPORT = (
    PROJECT_ROOT
    / "artifacts/verification/ribbon_cap_transition/d348e035ba3e4d9e967c224694c66668/report.json"
)


def run() -> Path:
    """
    Observe one unchanged solve per eligible case, retaining rejected/skipped rows.

    Freeze all fixtures and connection targets before the first solve. Compare
    final spreads and failures with saved v2 evidence; stop on drift, discrepancy,
    harness error or the scheduling cap. No refinement, retries or Fusion calls.
    """
    started = perf_counter()
    cases = development_cases()
    previous_bytes = PREVIOUS_REPORT.read_bytes()
    previous = {row["case_id"]: row["candidate"] for row in json.loads(previous_bytes)["cases"]}
    fingerprints = _fingerprints()
    inputs = []
    for case in cases:
        fits = _fits(case)
        turns = freeze_targets(case, *fits, fixture=ShortConnectionFixture(case, turn_degrees=15))
        inputs.append((case, fits, turns))
    directory = PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/stages" / uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    plan = {
        "question": "Where do lane-length spread and end-allowance failures arise: banking, cap correction or fold equalization?",
        "procedure": "Unchanged cap-transition-v2 with immutable stage observers; fixed centerlines and pre-authored short connections; no rerouting.",
        "classification": "Existing development cases; mixed pair reflection-related; no holdouts.",
        "matrix_sha256": matrix_fingerprint(cases),
        "cases_and_fixed_targets": [
            {
                "case": asdict(case),
                "targets": {name: asdict(route) for name, route in turns.fixed_routes.items()},
            }
            for case, _, turns in inputs
        ],
        "source_and_rule_sha256": fingerprints,
        "production_sha256": verify_sources(),
        "previous_report_sha256": hashlib.sha256(previous_bytes).hexdigest(),
        "limits": {
            "configurations": 8,
            "solves_per_case": 1,
            "refinements": 0,
            "native_attempts": 0,
            "schedule_wall_seconds": 60,
        },
        "estimated_seconds": 5,
        "memory_and_cost": "Unmeasured; no Fusion operations or agreed host-memory ceiling; token/cost data unavailable.",
        "stops": "60-second cap, five-second estimate exceeded, source drift, historical outcome discrepancy or harness error; retain all rows.",
        "native_prediction": "unknown; finite chords are not native loft tangency predictions",
        "sphere_diameter_widths": 5,
        "length_policy": "One percent is a nonblocking mechanical goal; historical length failures are compared as warnings, not geometry gates.",
    }
    (directory / "plan.json").write_text(json.dumps(plan, indent=2, default=str), encoding="utf-8")
    rows: list[dict[str, object]] = [
        {
            "case_id": case.name,
            "status": "not_attempted",
            "native": "not_attempted",
            "post_build_audit": "absent",
        }
        for case in cases
    ]
    report = {
        "plan": plan,
        "cases": rows,
        "native_attempts": 0,
        "built": 0,
        "fully_audited": 0,
        "native_failure_rate": "unmeasured",
    }
    stop_reason = None
    solves = 0
    for (case, fits, turns), row in zip(inputs, rows):
        elapsed = perf_counter() - started
        if elapsed >= 60 or elapsed > 5 or _fingerprints() != fingerprints:
            stop_reason = "Scheduling cap/estimate or source drift; no next solve."
            break
        recorder = StageRecorder(fits)
        solve_started = perf_counter()
        solves += 1
        try:
            shape = solve_candidate(case, *fits, observer=recorder)
        except UnsafeRibbon as error:
            row.update(
                status="rule_rejected",
                reason=str(error),
                solve_seconds=perf_counter() - solve_started,
            )
            if previous[case.name]["status"] != "rule_rejected":
                stop_reason = "Historical rule-rejection discrepancy."
                break
        except (ValueError, TypeError) as error:
            row.update(status="harness_error", reason=str(error), stages=recorder.stages)
            stop_reason = "Diagnostic harness error; no retry."
            break
        else:
            row["solve_with_observation_seconds"] = perf_counter() - solve_started
            inspect_started = perf_counter()
            try:
                preflight = inspect_candidate(shape, EndPlan(case, turns))
            except (UnsafeRibbon, ValueError, TypeError) as error:
                row.update(status="harness_error", reason=str(error), stages=recorder.stages)
                stop_reason = "Candidate inspection harness error; no retry."
                break
            row.update(
                status=preflight["verdict"],
                stages=recorder.stages,
                preflight=preflight,
                folded=shape.folded,
                end_lead_mm=shape.end_lead_mm,
                inspection_seconds=perf_counter() - inspect_started,
                prediction_gaps=[
                    "Analytic corrected-lane derivatives absent for spatial cases",
                    "Native trunk/cap/branch skin interpolation and junction curvature unmeasured",
                    "Connection skin tangency and continuous final-lane strain unmeasured",
                ],
            )
            old = previous[case.name]
            unchanged = abs(shape.spread - old["trunk_lane_spread"]) <= 1e-12 and sorted(
                preflight["failures"]
            ) == sorted(
                failure
                for failure in old["preflight"]["failures"]
                if failure not in LENGTH_GOAL_FAILURES
            )
            row["matches_saved_outcome"] = unchanged
            if not unchanged:
                stop_reason = "Historical outcome discrepancy; no refinement."
                break
        (directory / "report.json").write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8"
        )
    for row in rows:
        if row["status"] == "not_attempted":
            row["reason"] = stop_reason or "Not reached."
    report.update(
        planned=len(cases),
        evaluated=sum(row["status"] != "not_attempted" for row in rows),
        solve_calls=solves,
        elapsed_seconds=perf_counter() - started,
        stop_reason=stop_reason or "Approved eight-case scope exhausted; no refinement.",
        production_sha256_after=verify_sources(),
    )
    (directory / "report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    return directory
