"""
Establish three fixed collateral baselines with no solver adjustment or native work.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from cable_bundler.routing.geometry import difference, dot
from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT, verify_sources
from experiments.experiment_ribbon_diagnosis.preflight import EndPlan
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon
from experiments.experiment_secure_discrete_ribbon.reporting import matrix_fingerprint

from .planning import ShortConnectionFixture, freeze_targets, inspect_candidate
from .regression_cases import PURPOSES, collateral_cases, comparison_cases
from .screen import _fingerprints, _fits
from .solver import solve_candidate


def run() -> Path:
    """
    Solve each new collateral case at most once and preserve all baseline findings.

    Freeze complete inputs before evaluating. Stop scheduling at source drift,
    harness error or 60 seconds. Failures remain evidence, never triggers for
    fixture edits, retries or an automatic fix. Existing controls are registered
    for comparison, not re-evaluated or counted as new coverage in this run.
    """
    started = perf_counter()
    cases = collateral_cases()
    sources = _fingerprints()
    inputs = []
    for case in cases:
        fits = _fits(case)
        turns = freeze_targets(case, *fits, fixture=ShortConnectionFixture(case, turn_degrees=15))
        inputs.append((case, fits, turns))
    directory = (
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/collateral" / uuid4().hex
    )
    directory.mkdir(parents=True, exist_ok=False)
    plan = {
        "question": "Establish pre-fix baselines for three structurally different collateral-mechanics challenges.",
        "procedure": "Unchanged cap-transition solver, initialization, banking, fold budget and fixed connection fixture; fixed centerlines; no rerouting or adjustment.",
        "purposes": PURPOSES,
        "cases_and_fixed_targets": [
            {
                "case": asdict(case),
                "targets": {name: asdict(route) for name, route in turns.fixed_routes.items()},
            }
            for case, _, turns in inputs
        ],
        "matrix_sha256": matrix_fingerprint(cases),
        "future_comparison_matrix_sha256": matrix_fingerprint(comparison_cases()),
        "future_comparison_ids": [case.name for case in comparison_cases()],
        "source_and_rule_sha256": sources,
        "production_sha256": verify_sources(),
        "limits": {
            "configurations": 3,
            "solves_per_case": 1,
            "refinements": 0,
            "native_attempts": 0,
            "schedule_wall_seconds": 60,
        },
        "classification": "Development collateral baselines; no algorithm improvement or native success claim.",
        "native_prediction": "unknown; sampled lane-center planarity is not a native profile/loft certificate",
        "estimated_seconds": 5,
        "resource_basis": "Cheap host-only baseline; estimate under 5 seconds from prior screen. Host memory/token cost unmeasured; Fusion untouched.",
        "stops": "60-second scheduling cap, five-second estimate exceeded, source drift or harness error; no retuning after known rule findings.",
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
    report: dict[str, object] = {
        "plan": plan,
        "cases": rows,
        "planned": 3,
        "native_attempts": 0,
        "built": 0,
        "fully_audited": 0,
    }
    stop = None
    for (case, fits, turns), row in zip(inputs, rows):
        if perf_counter() - started > 5 or _fingerprints() != sources:
            stop = "Scheduling cap or source drift."
            break
        solve_started = perf_counter()
        try:
            shape = solve_candidate(case, *fits)
            row["solve_seconds"] = perf_counter() - solve_started
            inspected = perf_counter()
            preflight = inspect_candidate(shape, EndPlan(case, turns))
            row.update(
                status=preflight["verdict"],
                preflight=preflight,
                inspection_seconds=perf_counter() - inspected,
                maximum_sampled_lane_center_off_frame_plane_mm=max(
                    abs(dot(difference(lane[i], frame.origin), frame.tangent))
                    for i, frame in enumerate(shape.frames)
                    for lane in shape.lanes
                ),
                baseline_role="Known failing diagnostic"
                if preflight["failures"]
                else "No detected numerical violation; native baseline absent",
            )
        except UnsafeRibbon as error:
            row.update(
                status="rule_rejected", reason=str(error), baseline_role="Known failing diagnostic"
            )
        except (TypeError, ValueError) as error:
            row.update(status="harness_error", reason=str(error))
            stop = "Harness error; no retry."
            break
        (directory / "report.json").write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8"
        )
    for row in rows:
        if row["status"] == "not_attempted":
            row["reason"] = stop or "Not reached."
    report.update(
        evaluated=sum(row["status"] != "not_attempted" for row in rows),
        elapsed_seconds=perf_counter() - started,
        stop_reason=stop or "Three-case baseline scope exhausted; no fix or refinement.",
        native_failure_rate="unmeasured",
        production_sha256_after=verify_sources(),
    )
    (directory / "report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    return directory
