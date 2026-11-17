"""
Exercise complete manual-gym lifecycle and rejection reporting with analytical constructors.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from artifacts.verification.resume3338.author import author as original_author
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_complete.execution import RibbonPlan
from experiments.experiment_ribbon_complete.material_witnesses import (
    CompleteWitnessAudit,
    WitnessWork,
)
from experiments.experiment_ribbon_complete_gym import job
from experiments.experiment_ribbon_complete_gym.fixture import author
from experiments.experiment_ribbon_locked_solver.solver import Result
from tests.test_ribbon_complete_execution import trunk


def scene(lines: int = 2) -> Scene:
    """
    Declare reproducible endpoint input only, with no claim of trunk feasibility.
    """
    return Scene(Config(1, lines, 0.75, 300, 100), Goal(0, 1), Goal(25, 7))


@pytest.mark.parametrize("lines", (2, 3, 10))
def test_maintained_fixture_preserves_original_targets_and_identity_before_any_solve(
    lines: int,
) -> None:
    """
    Moving the author out of an artifact must not tune ending length or ordered sources.
    """
    source = scene(lines)
    namespace = UUID(int=3350)
    assert author(source, namespace) == original_author(source, namespace)


@pytest.fixture
def frozen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Mock external source/memory readings while retaining actual complete geometry arithmetic.
    """
    monkeypatch.setattr(job.lock, "capture", lambda: {})
    monkeypatch.setattr(job.lock, "verify", lambda pins: None)
    monkeypatch.setattr(
        job.subprocess,
        "check_output",
        lambda *args, **kwargs: "System-wide memory free percentage: 55%",
    )
    directory = tmp_path / "case"
    job.freeze(scene(), UUID(int=3350), directory, 1e-5)
    return directory


def test_manual_complete_case_certifies_corrected_endings_without_native_or_full_pass(
    frozen: Path,
) -> None:
    """
    A trunk stand-in exercises the pipeline; this is not endpoint or geometry qualification.
    """
    result = json.loads(job.run(frozen, trunk).read_text())
    assert result["status"] == "unqualified"
    assert result["ending_material"]["within_allowance"]
    assert result["prepared_branches"] == 4 and result["unattempted_route_ids"] == []
    assert result["witness_calls"] == 0 and result["native_calls"] == 0
    assert result["fully_qualified_complete_ribbons"] == 0 and not result["generalization_credit"]
    measured = result["planned_material"]
    assert measured["status"] == "within_planned_increment_bound"
    assert len(measured["findings"]) == 4 and measured["allowance_mm"] == "1/100"
    assert result["metric_spans"] == measured["metric_spans"] == 5
    assert "junction_material_correspondence" in measured["outstanding"]
    assert "native_material_correspondence" in measured["outstanding"]
    events = [json.loads(line) for line in (frozen / "events.jsonl").read_text().splitlines()]
    assert events[-1]["stage"] == "planned_material_increment_bound"
    witness = next(row for row in events if row["stage"] == "complete_material_witness")
    assert witness["status"] == "not_attempted"
    assert witness["reason"] == "certified_combined_upper_bound" and witness["findings"] == []
    with pytest.raises(FileExistsError):
        job.run(frozen, trunk)


def test_metric_stop_preserves_prepared_plan_without_false_completion(
    frozen: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A new measurement failure retains the prepared prefix and does not renew its budget.
    """
    calls = []

    def stopped(plan: Any, work: Any) -> dict[str, Any]:
        """
        Observe one existing allocation and stop before returning metric evidence.
        """
        calls.append((plan, work.maximum_spans))
        raise RuntimeError("analytical metric stop")

    monkeypatch.setattr(job, "measure_material", stopped)
    result = json.loads(job.run(frozen, trunk).read_text())
    assert result["status"] == "stopped" and "analytical metric stop" in result["error"]
    assert len(calls) == 1 and calls[0][1] == 16384
    assert (frozen / "complete-plan.pkl").exists() and result["prepared_branches"] == 4
    assert result["planned_material"]["status"] == "stopped"
    assert result["fully_qualified_complete_ribbons"] == 0
    assert result["witness_calls"] == 0


@pytest.mark.parametrize("violation", (False, True))
def test_inconclusive_upper_bound_keeps_rejection_witnesses(
    frozen: Path, monkeypatch: pytest.MonkeyPatch, violation: bool
) -> None:
    """
    A missing bound cannot skip the original rejection test or create an acceptance.
    """
    original = job.measure_material

    def unresolved(plan: Any, work: Any) -> dict[str, Any]:
        """
        Retain the actual measurement but withhold its upper-bound qualification.
        """
        report = original(plan, work)
        report["status"] = "unresolved_bound"
        return report

    monkeypatch.setattr(job, "measure_material", unresolved)
    audit = job.audit_witnesses

    def witnessed(plan: RibbonPlan, intervals: int, work: WitnessWork) -> CompleteWitnessAudit:
        """
        Exercise worker classification with source-labelled completed or violating receipts.
        """
        receipt = audit(plan, intervals, work)
        if violation:
            receipt = replace(
                receipt,
                findings=(
                    replace(receipt.findings[0], lower_mm=Fraction(1, 50)),
                    *receipt.findings[1:],
                ),
            )
        return receipt

    monkeypatch.setattr(job, "audit_witnesses", witnessed)
    result = json.loads(job.run(frozen, trunk).read_text())
    assert result["status"] == ("planned_material_violation" if violation else "unqualified")
    assert result["witness_calls"] == 128
    assert result["planned_material"]["status"] == "unresolved_bound"
    events = [json.loads(line) for line in (frozen / "events.jsonl").read_text().splitlines()]
    witness = next(row for row in events if row["stage"] == "complete_material_witness")
    assert witness["status"] == ("violated" if violation else "not_witnessed")
    assert witness["findings"] and all(row["first_route_ids"] for row in witness["findings"])
    assert result["fully_qualified_complete_ribbons"] == 0


def test_unresolved_trunk_leaves_metric_work_unattempted(frozen: Path) -> None:
    """
    A solver stop cannot acquire ending measurements or an inferred zero trunk bound.
    """

    def unresolved(
        _targets: Targets, check: Callable[[], None], _record: Callable[[dict[str, Any]], None]
    ) -> Result:
        """
        Return one recorded unresolved constructor outcome without replacement geometry.
        """
        check()
        return Result(None, None, {"status": "analytical_unresolved"}, None)

    result = json.loads(job.run(frozen, unresolved).read_text())
    assert result["status"] == "trunk_unresolved"
    assert result["planned_material"] == {
        "status": "unattempted",
        "reason": "trunk_unresolved",
        "metric_spans": 0,
    }
    assert result["metric_spans"] == 0 and result["prepared_branches"] == 0
    assert result["fully_qualified_complete_ribbons"] == 0


def test_post_measurement_cancellation_cannot_publish_a_completed_result(
    frozen: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The final shared checkpoint must pass before committing the completed audit status.
    """
    inspect = job.inspect_material

    def cancelled(
        plan: RibbonPlan,
        witnesses: WitnessWork,
        metrics: Any,
        record: Callable[[dict[str, Any]], None],
    ) -> dict[str, Any]:
        """
        Cancel after all arithmetic returns but before its worker receipt is committed.
        """
        report = inspect(plan, witnesses, metrics, record)
        (frozen / "cancel").touch()
        return report

    monkeypatch.setattr(job, "inspect_material", cancelled)
    result = json.loads(job.run(frozen, trunk).read_text())
    assert result["status"] == "stopped" and "cancelled" in result["error"]
    assert result["planned_material"]["status"] == "stopped"


@pytest.mark.parametrize("cancelled", (False, True))
def test_stopped_worker_preserves_reason_and_never_retries_constructor(
    frozen: Path, cancelled: bool
) -> None:
    """
    Cancellation before work and a constructor stop have separate honest call counts.
    """
    calls = []

    def stopped(
        targets: Targets, _check: Callable[[], None], record: Callable[[dict[str, Any]], None]
    ) -> Result:
        """
        Flush a prefix and stop once, without returning replacement geometry.
        """
        calls.append(targets)
        record({"stage": "analytical_stop"})
        raise TimeoutError("analytical constructor stop")

    if cancelled:
        (frozen / "cancel").touch()
    result = json.loads(job.run(frozen, stopped).read_text())
    assert result["status"] == "stopped" and len(calls) == int(not cancelled)
    assert result["witness_calls"] == 0 and not (frozen / "complete-plan.pkl").exists()
    assert ("cancelled" if cancelled else "constructor stop") in result["error"]


def test_input_drift_stops_before_unpickling_or_constructing(
    frozen: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A trusted-local input receipt is mandatory even for a diagnostic run.
    """
    (frozen / "targets.pkl").write_bytes(b"changed")

    def forbidden(_payload: bytes) -> Any:
        """
        Fail if a changed pickle reaches deserialization.
        """
        raise AssertionError("Unpickle must not run")

    monkeypatch.setattr("pickle.loads", forbidden)
    with pytest.raises(RuntimeError, match="input drift"):
        job.run(frozen, trunk)
    assert not (frozen / "started.json").exists()
