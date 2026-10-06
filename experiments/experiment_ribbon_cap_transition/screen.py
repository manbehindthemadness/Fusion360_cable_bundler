"""
Run one bounded development comparison on eight five-width sphere configurations.

No Fusion calls or native attempts occur. Five-width scope is explicitly requested
by the user; it is not evidence for the retained historical three-width boundary.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT, verify_sources
from experiments.experiment_ribbon_diagnosis.inputs import analytic_guide_frame
from experiments.experiment_ribbon_diagnosis.preflight import EndPlan
from experiments.experiment_secure_discrete_ribbon.bank import bank_ribbon_frames
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.contract import (
    UnsafeRibbon,
    certify_curvature,
    discrete_profile_reach,
)
from experiments.experiment_secure_discrete_ribbon.frames import ribbon_frames
from experiments.experiment_secure_discrete_ribbon.reporting import matrix_fingerprint
from experiments.experiment_secure_discrete_ribbon.shape import RibbonEndFit, solve_ribbon_shape

from .fixtures import development_cases
from .planning import ShortConnectionFixture, freeze_targets, inspect_candidate, prepare_candidate


def screen_cases() -> tuple[RibbonStressCase, ...]:
    """
    Freeze all direction cases, a gentle control, two spatial twists and a negative.
    """
    return development_cases()


def _fits(case: RibbonStressCase) -> tuple[RibbonEndFit, RibbonEndFit]:
    """
    Author physical straight guides independently of either solver result.
    """
    fits = []
    for at_start in (True, False):
        frame = analytic_guide_frame(case, at_start)
        fits.append(
            RibbonEndFit(
                tuple(
                    frame.origin.translated(
                        frame.width, (i - (case.lines - 1) / 2) * case.diameter_mm
                    )
                    for i in range(case.lines)
                ),
                (frame.thickness,) * case.lines,
                approach_normal=frame.tangent,
            )
        )
    return fits[0], fits[1]


def _fingerprints() -> dict[str, str]:
    """
    Fingerprint candidate code, shared experimental contracts, and retained rules.
    """
    paths = [
        *Path(__file__).parent.glob("*.py"),
        PROJECT_ROOT / "experiment_testing_rules.txt",
        PROJECT_ROOT / "rollback_end_loft_notes.txt",
    ]
    paths.extend(
        PROJECT_ROOT / "experiments/experiment_secure_discrete_ribbon" / name
        for name in ("frames.py", "shape.py", "bank.py", "contract.py")
    )
    paths.extend(
        PROJECT_ROOT / "experiments/experiment_ribbon_diagnosis" / name
        for name in ("preflight.py", "spatial.py", "end_sections.py", "compact.py")
    )
    return {
        str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }


def run() -> Path:
    """
    Evaluate at most eight cases once per procedure, stopping on a new violation.

    The native prediction remains unresolved. All scheduled or skipped cases
    remain in the report. A two-minute cap prevents scheduling the next case;
    it does not interrupt an in-flight calculation. No automatic retries occur.
    """
    cases = screen_cases()
    directory = PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition" / uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    fingerprints = _fingerprints()
    rows = [
        {
            "case_id": case.name,
            "expectation": case.expectation.value,
            "baseline": {"status": "not_attempted"},
            "candidate": {"status": "not_attempted"},
            "native": "not_attempted",
            "post_build_audit": "absent",
        }
        for case in cases
    ]
    plan = {
        "hypothesis": "Exact cap frames and lane-specific C2 correction fields remove authored cap mismatch without relocating connections.",
        "procedure": "Historical blend vs cap-transition-v2; fixed centerlines and pre-authored 15-degree, four-conductor-radius targets; original fold search budgets.",
        "case_ids": [case.name for case in cases],
        "classification": "Development only; no holdouts consumed.",
        "sphere_diameter_widths": 5,
        "lineage": "Four direction controls (mixed pair reflection-related), one gentle control, two pre-existing five-width spatial twists, one invalid tight control. All development; none are holdouts.",
        "limits": {
            "complete_configurations": 8,
            "shape_solves_per_case": 2,
            "refinement_rounds": 0,
            "native_attempts": 0,
            "schedule_wall_cap_seconds": 120,
        },
        "stops": [
            "new candidate preflight violation relative to baseline",
            "source drift",
            "wall cap",
            "harness error",
        ],
        "source_and_rule_sha256": fingerprints,
        "production_sha256": verify_sources(),
        "matrix_sha256": matrix_fingerprint(cases),
        "native_prediction": "unresolved",
        "memory_and_cost": "unmeasured; no Fusion operations",
    }
    (directory / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    started = perf_counter()
    stop_reason = None
    for case, row in zip(cases, rows):
        if perf_counter() - started >= 120 or _fingerprints() != fingerprints:
            stop_reason = "Wall cap or source drift; remaining configurations not attempted."
            break
        start_fit, end_fit = _fits(case)
        fixture = ShortConnectionFixture(case, turn_degrees=15)
        turns = freeze_targets(case, start_fit, end_fit, fixture=fixture)
        try:
            certify_curvature(case.route, discrete_profile_reach(case.lines, case.diameter_mm))
        except UnsafeRibbon as error:
            row["baseline"] = row["candidate"] = {"status": "rule_rejected", "reason": str(error)}
            continue
        for procedure in ("baseline", "candidate"):
            solve_started = perf_counter()
            try:
                if procedure == "baseline":
                    frames = bank_ribbon_frames(
                        ribbon_frames(case.route, case.start_width, case.end_width),
                        case.lines,
                        case.diameter_mm,
                    )
                    shape = solve_ribbon_shape(
                        frames, case.lines, case.diameter_mm, start_fit=start_fit, end_fit=end_fit
                    )
                    end_plan = EndPlan(case, turns)
                    preflight = inspect_candidate(shape, end_plan)
                else:
                    shape, end_plan, preflight = prepare_candidate(
                        case, start_fit, end_fit, fixture=fixture
                    )
                row[procedure] = {
                    "status": preflight["verdict"],
                    "preflight": preflight,
                    "trunk_lane_spread": shape.spread,
                    "end_lead_mm": shape.end_lead_mm,
                    "elapsed_seconds": perf_counter() - solve_started,
                }
            except (UnsafeRibbon, ValueError) as error:
                row[procedure] = {"status": "harness_error", "reason": str(error)}
                stop_reason = f"{case.name}: {procedure} harness error."
                break
        if stop_reason:
            break
        baseline = row["baseline"]
        candidate = row["candidate"]
        if isinstance(baseline, dict) and isinstance(candidate, dict):
            baseline_checks, candidate_checks = (
                baseline.get("preflight", {}),
                candidate.get("preflight", {}),
            )
            if isinstance(baseline_checks, dict) and isinstance(candidate_checks, dict):
                introduced = sorted(
                    set(candidate_checks.get("failures", []))
                    - set(baseline_checks.get("failures", []))
                )
                if introduced:
                    row["new_violations"] = introduced
                    stop_reason = f"{case.name}: candidate introduced a new measured violation."
                    break
    for row in rows:
        for procedure in ("baseline", "candidate"):
            outcome = row[procedure]
            if isinstance(outcome, dict) and outcome.get("status") == "not_attempted":
                outcome["reason"] = stop_reason or "Not reached."
    report = {
        "plan": plan,
        "cases": rows,
        "elapsed_seconds": perf_counter() - started,
        "stop_reason": stop_reason,
        "native_attempts": 0,
        "native_failure_rate": "unmeasured",
        "geometry_success_claim": False,
    }
    report_path = directory / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


if __name__ == "__main__":
    print(run())
