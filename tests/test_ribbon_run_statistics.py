"""
Keep aggregate comparisons faithful to original outcomes and explicit measurement gaps.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_locked_solver.tester.sequence import Specification, defaults
from experiments.experiment_ribbon_regression.statistics import (
    comparison_metadata,
    summarize_journal,
)


def write_object(path: Path, value: Any) -> None:
    """
    Author synthetic evidence only, without loading a historical geometry fixture.
    """
    path.write_text(json.dumps(value))


@pytest.fixture
def journal(tmp_path: Path) -> Path:
    """
    Model three original attempts plus a separate repair across two source versions.
    """
    write_object(tmp_path / "plan.json", {"specification": {"maximum_cases": 1000}})
    write_object(
        tmp_path / "status.json",
        {"active": False, "phase": "stopped", "specification": {"maximum_cases": 3}},
    )
    entries: list[dict[str, Any]] = []
    for ordinal in range(1, 4):
        job = tmp_path / str(ordinal)
        job.mkdir()
        write_object(job / "plan.json", {"sources": {"solver.py": "a" if ordinal == 1 else "b"}})
        write_object(
            job / "numerical-result.json",
            {
                "status": "unresolved" if ordinal == 2 else "numerically_accepted",
                "cpu_seconds": 1.0 if ordinal == 1 else 0.1,
            },
        )
        if ordinal != 2:
            write_object(
                job / "native-result.json",
                {
                    "status": "built_and_named_fidelity_checks_pass",
                    "native_attempted": 1,
                    "built": 1,
                    "fidelity_audited": 1,
                    "generation_seconds": 0.5,
                    "audit_seconds": 0.2,
                    "audit": {"maximum_error_mm": 1e-9},
                },
            )
        entries.extend(
            [
                {"event": "case_started", "case": ordinal},
                {
                    "event": "case_finished",
                    "case": ordinal,
                    "job": str(job),
                    "status": "completed" if ordinal == 1 else "stopped",
                    "problem": None if ordinal == 1 else "failure",
                    "gym_boundary": {"status": "passed" if ordinal == 1 else "failed"},
                },
            ]
        )
    entries.extend([{"event": "case_repaired", "case": 2}, {"event": "source_epoch"}])
    (tmp_path / "cases.jsonl").write_text("\n".join(json.dumps(row) for row in entries))
    return tmp_path


def test_first_attempts_exclude_repair_credit_and_unattempted_native_work(journal: Path) -> None:
    """
    Preserve failures and separate measured denominators instead of pooling repaired results.
    """
    result = summarize_journal(journal)
    assert (result["planned"], result["attempted"], result["passed"], result["failed"]) == (
        3,
        3,
        1,
        2,
    )
    assert result["first_failure_ordinal"] == 2
    assert result["unattempted"] == result["uncollected"] == 0
    assert result["separate_repairs"] == result["source_epoch_events"] == 1
    assert result["source_versions"] == 2
    counts = result["counts"]
    assert counts["numerically_accepted"] == counts["native_attempted"] == counts["built"] == 2
    assert counts["fidelity_audited"] == counts["timing_goal_measured"] == 2
    assert counts["timing_goal_misses"] == counts["numerical_failures"] == 1
    assert counts["boundary_or_harness_failures"] == 1
    assert result["maximum_native_error_mm"] == 1e-9
    assert result["timings_seconds"]["solve_cpu"]["measured"] == 3
    assert result["timings_seconds"]["native"]["measured"] == 2
    assert result["full_physical_audit"] == "unmeasured"
    assert str(journal) not in json.dumps(result)


def test_active_or_duplicate_attempts_cannot_be_finalized(journal: Path) -> None:
    """
    Reject live summaries and duplicated first-attempt receipts instead of inflating coverage.
    """
    state = journal / "status.json"
    original = json.loads(state.read_text())
    write_object(state, {**original, "active": True})
    with pytest.raises(ValueError, match="stop the run"):
        summarize_journal(journal)
    write_object(state, original)
    log = journal / "cases.jsonl"
    log.write_text(log.read_text() + "\n" + log.read_text().splitlines()[1])
    with pytest.raises(ValueError, match="Duplicate"):
        summarize_journal(journal)


def test_native_error_maximum_includes_separate_seam_warning(journal: Path) -> None:
    """
    Preserve accepted warning counts while including measurements outside the main audit maximum.
    """
    path = journal / "1" / "native-result.json"
    native = json.loads(path.read_text())
    native.update(
        status="built_with_precision_warning",
        precision_warning={"maximum_error_mm": 2e-6, "categories": ["seam"]},
    )
    write_object(path, native)
    result = summarize_journal(journal)
    assert result["maximum_native_error_mm"] == 2e-6
    assert result["counts"]["accuracy_warnings"] == 1
    assert (result["passed"], result["failed"], result["first_failure_ordinal"]) == (1, 2, 2)


@pytest.mark.parametrize(
    "warning",
    (
        None,
        {},
        {"maximum_error_mm": -1},
        {"maximum_error_mm": float("nan")},
        {"maximum_error_mm": float("inf")},
        {"maximum_error_mm": True},
    ),
)
def test_native_warning_cannot_hide_missing_or_invalid_error(
    journal: Path, warning: dict[str, Any] | None
) -> None:
    """
    Reject incomplete warning evidence rather than publishing an understated aggregate maximum.
    """
    path = journal / "1" / "native-result.json"
    native = json.loads(path.read_text())
    write_object(
        path, {**native, "status": "built_with_precision_warning", "precision_warning": warning}
    )
    with pytest.raises(ValueError, match="warning requires its finite nonnegative"):
        summarize_journal(journal)


@pytest.mark.parametrize(
    "change,message",
    [
        ({"fidelity_audited": 2}, "0/1"),
        ({"audit": {"maximum_error_mm": float("nan")}}, "finite nonnegative"),
        ({"built": 0}, "pass requires"),
    ],
)
def test_missing_or_malformed_pass_measurements_are_rejected(
    journal: Path, change: dict[str, Any], message: str
) -> None:
    """
    Require actual native evidence before accepting an aggregate pass label.
    """
    path = journal / "1" / "native-result.json"
    write_object(path, {**json.loads(path.read_text()), **change})
    with pytest.raises(ValueError, match=message):
        summarize_journal(journal)


def test_comparisons_separate_sampling_contract_from_seed_count_and_solver_source() -> None:
    """
    Compare fresh populations across solver changes while exposing changed physical test contracts.
    """
    scene = Scene(Config(17, 3, 0.75, 300, 300), Goal(0, 0), Goal(25, 0))
    specification = Specification.parse({**defaults(scene), "maximum_cases": 100})
    original = comparison_metadata(specification, {"terminal_hardware": True}, {"solver": "a"})
    another = comparison_metadata(
        replace(specification, seed=22, maximum_cases=50),
        {"terminal_hardware": True},
        {"solver": "b"},
    )
    assert original["comparison_key"] == another["comparison_key"]
    assert original["solver_source_hash"] != another["solver_source_hash"]
    changed = comparison_metadata(specification, {"terminal_hardware": False}, {"solver": "a"})
    assert changed["comparison_key"] != original["comparison_key"]
