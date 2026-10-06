"""
Compare one fixed section-plane sampling candidate with all retained baselines.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT, verify_sources
from experiments.experiment_ribbon_diagnosis.preflight import EndPlan
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon
from experiments.experiment_secure_discrete_ribbon.reporting import matrix_fingerprint
from experiments.experiment_secure_discrete_ribbon.shape import RibbonShape

from .planning import ShortConnectionFixture, freeze_targets, inspect_candidate
from .regression_cases import comparison_cases
from .screen import _fingerprints, _fits
from .section_sampling import SectionSamplingRejected, sample_section_planes, section_metrics
from .solver import solve_candidate
from .stages import StageRecorder


def _write(path: Path, value: dict[str, object]) -> None:
    """
    Checkpoint generated evidence in this run's unique artifact directory.
    """
    path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")


def _section_failures(metrics: dict[str, float]) -> list[str]:
    """
    Check ordered, uncompressed section centers equally for both procedures.

    Nominal conductor spacing is retained; one-percent length remains a goal.
    Planarity is the improvement metric, not a new baseline acceptance claim.
    """
    failures = []
    if metrics["minimum_signed_neighbor_order_mm"] <= 0:
        failures.append("sampled_section_lane_order")
    if metrics["minimum_neighbor_pitch_ratio"] < 1 - 1e-7:
        failures.append("sampled_section_neighbor_compression")
    return failures


def comparison_findings(baseline: dict[str, object], candidate: dict[str, object]) -> list[str]:
    """
    Identify new hard findings or lost samples without hiding baseline failures.

    Length-goal and finite-chord changes remain reported metrics, not hard gates.
    Worsening minimum radius or spacing is a review stop even when the
    corresponding hard finding was already present. No native claim occurs.
    """
    findings = sorted(set(candidate.get("failures", [])) - set(baseline.get("failures", [])))
    if baseline["status"] != "rule_rejected" and candidate["status"] == "rule_rejected":
        findings.append("candidate_lost_baseline_section_samples")
    for name in ("sampled_whole_lane_minimum_radius_mm", "sampled_trunk_occupied_radius_mm"):
        old = baseline.get("preflight", {}).get("occupied_and_lane_checks", {}).get(name)
        new = candidate.get("preflight", {}).get("occupied_and_lane_checks", {}).get(name)
        if old is not None and new is not None:
            worsened = new < old - 1e-7 if "minimum_radius" in name else new > old + 1e-7
            if worsened:
                findings.append(f"worsened:{name}")
    for name in ("minimum_neighbor_pitch_ratio", "maximum_neighbor_pitch_ratio"):
        old = baseline.get("section_metrics", {}).get(name)
        new = candidate.get("section_metrics", {}).get(name)
        if old is not None and new is not None:
            worsened = new < old - 1e-7 if name.startswith("minimum") else new > old + 1e-7
            if worsened:
                findings.append(f"worsened:{name}")
    if baseline.get("source_shape") != candidate.get("source_shape"):
        findings.append("unchanged_source_solve_drift")
    return findings


def _measure(shape: RibbonShape, diameter_mm: float) -> dict[str, object]:
    """
    Record section and finite cap metrics, retaining their limited evidence scope.
    """
    if shape.start_fit is None or shape.end_fit is None:
        raise ValueError("The comparison requires both fixed cap fits.")
    recorder = StageRecorder((shape.start_fit, shape.end_fit))
    recorder("section_samples", shape.lanes)
    metrics = section_metrics(shape, diameter_mm)
    return {
        "section_metrics": metrics,
        "section_findings": _section_failures(metrics),
        "lane_and_cap_metrics": recorder.stages["section_samples"],
    }


def run() -> Path:
    """
    Freeze eleven inputs, baseline each once and schedule at most eleven candidates.

    Maximum 22 unchanged solves, zero refinements/native attempts, 60-second
    scheduling cap. All baselines precede candidate evaluation. Test the original
    spatial failure first, then the three collateral challenges, then controls.
    Stop on new regression, harness error, source drift, wall cap or the five-second
    estimate being exceeded. Do not retry or adjust inputs after any outcome.
    """
    started = perf_counter()
    cases = comparison_cases()
    sources = _fingerprints()
    production = verify_sources()
    inputs = {}
    for case in cases:
        fits = _fits(case)
        turns = freeze_targets(case, *fits, fixture=ShortConnectionFixture(case, turn_degrees=15))
        inputs[case.name] = (fits, turns)
    directory = PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/sections" / uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    candidate_order = (cases[5], *cases[8:], *cases[:5], *cases[6:8])
    plan = {
        "question": "Can local lane/section-plane intersections remove nonplanarity without collateral numerical regression?",
        "procedure": "Unchanged cap-transition solve versus the same solve followed by unique local polyline-plane intersections; fixed frame planes and exact cap points; no projection, rerouting or retuning.",
        "classification": "Development comparison; no untouched holdouts or native certificate.",
        "cases_and_targets": [
            {
                "case": asdict(case),
                "targets": {
                    name: asdict(route) for name, route in inputs[case.name][1].fixed_routes.items()
                },
            }
            for case in cases
        ],
        "matrix_sha256": matrix_fingerprint(cases),
        "candidate_order": [case.name for case in candidate_order],
        "sources": sources,
        "production": production,
        "limits": {
            "configurations": 11,
            "solves": 22,
            "refinements": 0,
            "native_attempts": 0,
            "schedule_seconds": 60,
        },
        "estimated_seconds": 5,
        "stops": "New hard finding, worsening sampled radius/occupied envelope/neighbor spacing, lost samples, unchanged-solve drift, harness error, fingerprint drift, 60-second cap or five-second estimate exceeded.",
        "scope": "Resampled polylines and fixed branch plans; analytic corrected-lane tangents, lobe closure/intersection, native loft and continuous clearance unmeasured. Cap point/fit preservation does not certify tangent preservation.",
        "memory_and_tokens": "Unmeasured; no Fusion calls or host memory ceiling claimed.",
        "native_prediction": "unknown",
    }
    _write(directory / "plan.json", plan)
    rows = {
        case.name: {
            "case_id": case.name,
            "expectation": case.expectation.value,
            "baseline": {"status": "not_attempted"},
            "candidate": {"status": "not_attempted"},
            "native": "not_attempted",
            "post_build_audit": "absent",
        }
        for case in cases
    }
    report = {
        "plan": plan,
        "cases": list(rows.values()),
        "planned": 11,
        "native_attempts": 0,
        "built": 0,
        "fully_audited": 0,
        "native_failure_rate": "unmeasured",
        "solve_calls": 0,
    }
    stop = None
    for procedure, scheduled in (("baseline", cases), ("candidate", candidate_order)):
        for case in scheduled:
            if perf_counter() - started >= 5:
                stop = "Five-second estimate or 60-second scheduling cap exceeded."
                break
            if _fingerprints() != sources or verify_sources() != production:
                stop = "Source/production drift."
                break
            row = rows[case.name]
            result: dict[str, object] = {"status": "started", "failures": []}
            row[procedure] = result
            fits, turns = inputs[case.name]
            solve_started = perf_counter()
            report["solve_calls"] += 1
            try:
                shape = solve_candidate(case, *fits)
                result.update(
                    solve_seconds=perf_counter() - solve_started, source_shape=asdict(shape)
                )
                if procedure == "candidate":
                    sampled_started = perf_counter()
                    sampling = sample_section_planes(shape, case.diameter_mm)
                    shape = sampling.shape
                    result.update(
                        section_sampling_seconds=perf_counter() - sampled_started,
                        source_parameters=sampling.source_parameters,
                        maximum_same_index_displacement_mm=sampling.maximum_same_index_displacement_mm,
                    )
                inspected = perf_counter()
                preflight = inspect_candidate(shape, EndPlan(case, turns))
                metrics = _measure(shape, case.diameter_mm)
                result.update(metrics)
                result.update(
                    preflight=preflight,
                    sampled_shape=asdict(shape),
                    inspection_seconds=perf_counter() - inspected,
                    failures=[*preflight["failures"], *metrics["section_findings"]],
                )
                result["status"] = "reject" if result["failures"] else "unresolved"
            except (UnsafeRibbon, SectionSamplingRejected) as error:
                result.update(
                    status="rule_rejected",
                    reason=str(error),
                    elapsed_seconds=perf_counter() - solve_started,
                )
            except (TypeError, ValueError, RuntimeError) as error:
                result.update(status="harness_error", reason=str(error))
                stop = f"{case.name}: {procedure} harness error; no retry."
            if procedure == "candidate" and stop is None:
                findings = comparison_findings(row["baseline"], result)
                row["new_regressions"] = findings
                if findings:
                    stop = f"{case.name}: new numerical regression; scope stopped without tuning."
            _write(directory / "report.json", report)
            if stop is not None:
                break
        if stop is not None:
            break
    for row in rows.values():
        for procedure in ("baseline", "candidate"):
            if row[procedure]["status"] == "not_attempted":
                row[procedure]["reason"] = stop or "Not reached."
    report.update(
        baseline_evaluated=sum(
            row["baseline"]["status"] != "not_attempted" for row in rows.values()
        ),
        candidate_evaluated=sum(
            row["candidate"]["status"] != "not_attempted" for row in rows.values()
        ),
        elapsed_seconds=perf_counter() - started,
        stop_reason=stop or "Eleven-case comparison scope exhausted; no further runs authorized.",
        source_sha256_after=_fingerprints(),
        production_sha256_after=verify_sources(),
    )
    _write(directory / "report.json", report)
    return directory


if __name__ == "__main__":
    print(run())
