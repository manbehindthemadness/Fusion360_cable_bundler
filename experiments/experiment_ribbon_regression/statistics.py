"""
Compare aggregate first-attempt outcomes without using historical geometry as a reference fixture.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

from experiments.experiment_ribbon_locked_solver.tester.sequence import Specification


def comparison_metadata(
    specification: Specification, settings: dict[str, Any], sources: dict[str, str]
) -> dict[str, Any]:
    """
    Separate test-contract comparability from solver-source changes and run seed identity.

    Case count and seed do not change the sampling population. Native geometry,
    physical checks, resource limits and first-failure stopping remain explicit.
    Historical mixed-source or replay cohorts must retain their own population label.
    """
    contract = {
        "ranges": {key: value.payload() for key, value in specification.ranges.items()},
        "mode": specification.mode,
        "avoid_adjacent_zones": specification.avoid_adjacent_zones,
        "settings": settings,
        "stop_on_warnings": specification.stop_on_warnings,
        "contact": "require_separation",
        "boundary": "one-extra-cubicle-layer-plus-10mm-v2",
        "native_accuracy": "original-goals-warning-below-0.01mm-v2",
        "numerical_native_seconds": 120,
        "rss_kib": 4194304,
        "recovery": "4updates24Newton/.35CPU/2wall/original2048pairs",
        "stopping": "first_problem_or_configured_case_limit",
    }

    def digest(value: dict[str, Any]) -> str:
        """
        Fingerprint finite contract metadata without tying comparison to a particular input seed.
        """
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(encoded.encode()).hexdigest()

    return {
        "population": "fresh_unique_first_attempts",
        "contract": contract,
        "comparison_key": digest(contract),
        "solver_source_hash": digest(sources),
        "solver_source_count": len(sources),
    }


def _object(path: Path) -> dict[str, Any]:
    """
    Read one bounded generated JSON object while rejecting missing or malformed evidence.
    """
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError(f"Statistics input exceeds16MiB: {path.name}")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Statistics input must be an object: {path.name}")
    return value


def _distribution(values: list[float]) -> dict[str, int | float | None]:
    """
    Report descriptive timing values and their measured denominator, without confidence claims.
    """
    ordered = sorted(values)
    return {
        "measured": len(values),
        "minimum": min(values) if values else None,
        "median": median(values) if values else None,
        "p95": ordered[math.ceil(0.95 * len(values)) - 1] if values else None,
        "maximum": max(values) if values else None,
    }


def summarize_journal(directory: Path) -> dict[str, Any]:
    """
    Roll completed first attempts into counts and timing distributions, excluding repairs from pass credit.

    Missing native results mean unattempted, not a kernel failure. Source changes
    within one run are counted explicitly. Active/incompletely collected runs are
    not finalized; their original journal remains the authority until collection.
    Returned statistics contain no target coordinates, routes or case/job paths.
    The maximum native error includes separately retained dimensional warnings,
    such as seam findings absent from the main fidelity audit's maximum.
    """
    plan, state = _object(directory / "plan.json"), _object(directory / "status.json")
    if state.get("active") is not False:
        raise ValueError("Collect and stop the run before finalizing statistics")
    entries = [json.loads(line) for line in (directory / "cases.jsonl").read_text().splitlines()]
    if any(not isinstance(entry, dict) for entry in entries):
        raise ValueError("Statistics require structured journal entries")
    rows = [entry for entry in entries if entry.get("event") == "case_finished"]
    started = [entry for entry in entries if entry.get("event") == "case_started"]
    if any(type(row.get("case")) is not int or row["case"] < 1 for row in rows + started):
        raise ValueError("Statistics require positive integer attempt ordinals")
    if len({row.get("case") for row in rows}) != len(rows):
        raise ValueError("Duplicate first-attempt ordinals cannot be rolled up")
    if len({row["case"] for row in started}) != len(started) or not {
        row["case"] for row in rows
    } <= {row["case"] for row in started}:
        raise ValueError("Finished attempts require unique original start records")
    counts: Counter[str] = Counter()
    timings: dict[str, list[float]] = {name: [] for name in ("solve_cpu", "native", "audit")}
    first_failure = None
    maximum_error: float = 0.0
    source_hashes = set()
    for row in rows:
        raw_job = row.get("job")
        if not isinstance(raw_job, str) or not raw_job:
            raise ValueError("A finished first attempt requires its original job evidence")
        job = Path(raw_job)
        numerical, execution = _object(job / "numerical-result.json"), _object(job / "plan.json")
        sources = execution.get("sources")
        if not isinstance(sources, dict) or not sources:
            raise ValueError("Statistics require the original executable source fingerprints")
        source_hashes.add(json.dumps(sources, sort_keys=True))
        native_path = job / "native-result.json"
        native = _object(native_path) if native_path.exists() else {}
        okay = row.get("problem") is None and row.get("status") in (
            "completed",
            "completed_with_warning",
        )
        counts["passed"] += int(okay)
        counts["numerically_accepted"] += int(numerical.get("status") == "numerically_accepted")
        for key in ("native_attempted", "built", "fidelity_audited"):
            value = native.get(key, 0)
            if type(value) is not int or not 0 <= value <= 1:
                raise ValueError("Native statistics require per-configuration0/1 counts")
            counts[key] += value
        counts["accuracy_warnings"] += int(native.get("status") == "built_with_precision_warning")
        boundary = row.get("gym_boundary")
        if okay and (
            numerical.get("status") != "numerically_accepted"
            or native.get("native_attempted") != 1
            or native.get("built") != 1
            or native.get("fidelity_audited") != 1
            or native.get("status")
            not in ("built_and_named_fidelity_checks_pass", "built_with_precision_warning")
            or not isinstance(boundary, dict)
            or boundary.get("status") != "passed"
        ):
            raise ValueError("A pass requires numerical, native/fidelity and boundary evidence")
        audit = native.get("audit")
        error = audit.get("maximum_error_mm") if isinstance(audit, dict) else None
        if native.get("fidelity_audited") and (
            type(error) not in (int, float) or not math.isfinite(error) or error < 0
        ):
            raise ValueError(
                "Audited native geometry requires its finite nonnegative measured error"
            )
        if type(error) in (int, float) and math.isfinite(error):
            maximum_error = max(maximum_error, error)
        warning = native.get("precision_warning")
        if native.get("status") == "built_with_precision_warning" or warning is not None:
            warning_error = warning.get("maximum_error_mm") if isinstance(warning, dict) else None
            if isinstance(warning_error, bool) or not isinstance(warning_error, (int, float)):
                raise ValueError("Native warning requires its finite nonnegative measured error")
            if not math.isfinite(warning_error) or warning_error < 0:
                raise ValueError("Native warning requires its finite nonnegative measured error")
            maximum_error = max(maximum_error, warning_error)
        if not okay:
            first_failure = (
                row["case"] if first_failure is None else min(first_failure, row["case"])
            )
            category = (
                "numerical"
                if numerical.get("status") != "numerically_accepted"
                else "native_or_fidelity"
                if native.get("status")
                not in (
                    "built_and_named_fidelity_checks_pass",
                    "built_with_precision_warning",
                )
                else "accuracy"
                if native.get("status") == "built_with_precision_warning"
                else "boundary_or_harness"
            )
            counts[category + "_failures"] += 1
        measured = {
            "solve_cpu": numerical.get("cpu_seconds"),
            "native": native.get("generation_seconds"),
            "audit": native.get("audit_seconds"),
        }
        for name, value in measured.items():
            if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                timings[name].append(float(value))
        cpu, generation = measured["solve_cpu"], measured["native"]
        if (
            type(cpu) in (int, float)
            and type(generation) in (int, float)
            and math.isfinite(cpu)
            and math.isfinite(generation)
            and cpu >= 0
            and generation >= 0
        ):
            counts["timing_goal_measured"] += 1
            counts["timing_goal_misses"] += int(cpu > generation)
    specification = state.get("specification", plan.get("specification"))
    if not isinstance(specification, dict):
        raise ValueError("Statistics require the declared run specification")
    planned = specification.get("maximum_cases")
    if type(planned) is not int or planned < len(started):
        raise ValueError("Statistics require a finite case limit covering every attempt")
    return {
        "planned": planned,
        "unattempted": planned - len(started),
        "attempted": len(started),
        "finished": len(rows),
        "passed": counts["passed"],
        "failed": len(rows) - counts["passed"],
        "uncollected": len(started) - len(rows),
        "first_failure_ordinal": first_failure,
        "counts": dict(counts),
        "timings_seconds": {name: _distribution(values) for name, values in timings.items()},
        "maximum_native_error_mm": maximum_error if counts["fidelity_audited"] else None,
        "source_versions": len(source_hashes),
        "source_epoch_events": sum(entry.get("event") == "source_epoch" for entry in entries),
        "separate_repairs": sum(entry.get("event") == "case_repaired" for entry in entries),
        "full_physical_audited": 0,
        "full_physical_audit": "unmeasured",
        "stop_phase": state.get("phase"),
    }
