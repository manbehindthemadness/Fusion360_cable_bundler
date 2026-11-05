"""
Verify sequential scheduling, first-problem latching and persistent inspection evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.inspection.run_contract import ProcedureRunner
from experiments.experiment_ribbon_locked_solver.tester.engine import Tester as RangeTester
from experiments.experiment_ribbon_locked_solver.versions import V2
from tests.test_ribbon_range_sequence import specification


class Runner(ProcedureRunner):
    """
    Model one ordinary runner at a time with no subprocess, Fusion or geometry operations.
    """

    def __init__(self, directory: Path, outcomes: list[str]) -> None:
        """
        Retain an ordered terminal sequence so additional launches are observable failures.
        """
        self.directory, self.outcomes = directory, outcomes
        self.jobs: list[Path] = []
        self.status: dict[str, Any] = {"status": "idle"}
        self.cancelled = False

    def start(
        self, request: dict[str, Any], targets: Targets, *, gym: dict[str, Any] | None = None
    ) -> None:
        """
        Require exact frozen inputs and create only one current numerical result record.
        """
        assert request["procedures"][0]["id"] == V2 and gym is not None
        assert gym["targets"]["lines"] == targets.lines
        assert self.status["status"] not in ("running", "cancelling")
        job = self.directory / f"job-{len(self.jobs) + 1}"
        job.mkdir(parents=True)
        (job / "numerical-result.json").write_text(json.dumps({"contact": "separated"}))
        self.jobs.append(job)
        self.status = {"status": "running", "job": str(job)}

    def poll(self) -> Path:
        """
        Finish the current operation once, with cancellation never starting native work.
        """
        outcome = "cancelled" if self.cancelled else self.outcomes[len(self.jobs) - 1]
        self.status.update(status=outcome, detail=outcome)
        if outcome in ("completed", "completed_with_warning"):
            self.status["native"] = {
                "status": "built_with_precision_warning"
                if outcome.endswith("warning")
                else "built_and_named_fidelity_checks_pass"
            }
        manifest = self.jobs[-1] / "manifest.json"
        manifest.write_text("{}")
        return manifest

    def cancel(self) -> None:
        """
        Retain a stop request for collection at the next operation boundary.
        """
        self.cancelled = True
        self.status["status"] = "cancelling"

    def state(self) -> dict[str, Any]:
        """
        Return a detached status without collecting work implicitly.
        """
        return dict(self.status)

    def open_example(self, identifier: str) -> Path:
        """
        Reject accidental manual navigation from the scheduling boundary.
        """
        raise AssertionError(f"Unexpected example {identifier} in {self.directory}")

    def register_layout(self, manifest: Path, label: str) -> str:
        """
        Leave inspection registration to the separately mocked presenter.
        """
        raise AssertionError(f"Unexpected registration {label}: {manifest} in {self.directory}")

    def inspect_layout(self, manifest: Path, label: str) -> Path:
        """
        Reject direct inspection instead of silently bypassing the presentation callback.
        """
        raise AssertionError(f"Unexpected inspection {label}: {manifest} in {self.directory}")


def make_tester(tmp_path: Path, outcomes: list[str]) -> tuple[RangeTester, Runner, Mock]:
    """
    Bind real scheduling/journaling to mocked display and source/resource boundaries.
    """
    runner = Runner(tmp_path / "jobs", outcomes)
    present = Mock()
    tester = RangeTester(
        tmp_path / "tests",
        runner,
        lambda: {"source": "pinned"},
        Mock(),
        Mock(),
        Mock(),
        present,
        Mock(),
    )
    return tester, runner, present


def start(
    tester: RangeTester,
    *,
    warnings: bool = True,
    limit: int = 0,
    screenshots: dict[str, Any] | None = None,
) -> None:
    """
    Start an explicitly frozen selection without launching the first case yet.
    """
    payload = specification()
    payload.update(stop_on_warnings=warnings, maximum_cases=limit)
    if screenshots is not None:
        payload["screenshots"] = screenshots
    tester.start(
        payload,
        {
            "id": V2,
            "settings": {
                "smoothing_percent": 0,
                "material_uv": False,
                "first_pass_optimization": True,
            },
        },
    )


def test_first_problem_stops_without_retry_and_preserves_exact_case(tmp_path: Path) -> None:
    """
    Complete one pass, stop at the unresolved second case, and refuse any third launch.
    """
    tester, runner, present = make_tester(tmp_path, ["completed", "unresolved", "completed"])
    start(tester)
    assert not runner.jobs
    tester.poll()
    first = tester.scene
    tester.poll()
    assert tester.active and tester.passed == 1 and len(runner.jobs) == 1
    tester.poll()
    failed = tester.scene
    assert failed is not None
    assert first != failed
    tester.poll()
    assert not tester.active and tester.phase == "problem" and len(runner.jobs) == 2
    for _ in range(3):
        tester.poll()
    assert len(runner.jobs) == 2 and tester.scene is failed
    present.assert_called_once_with(failed, runner.jobs[-1] / "manifest.json")
    assert tester.journal is not None
    inputs = json.loads((tester.journal.directory / "case-000002.json").read_text())
    assert inputs["gym"]["config"] == failed.payload()["config"]
    ledger = [
        json.loads(line)
        for line in (tester.journal.directory / "cases.jsonl").read_text().splitlines()
    ]
    assert len([e for e in ledger if e["event"] == "case_finished"]) == 2
    assert ledger[-1]["event"] == "tester_stopped"


@pytest.mark.parametrize("stop_on_warning", (True, False))
def test_warning_policy_is_explicit_and_never_changes_solver_rules(
    tmp_path: Path, stop_on_warning: bool
) -> None:
    """
    Either stop at the native warning or finish the configured one-case test with it recorded.
    """
    tester, runner, _ = make_tester(tmp_path, ["completed_with_warning"])
    start(tester, warnings=stop_on_warning, limit=1)
    tester.poll()
    tester.poll()
    assert not tester.active and len(runner.jobs) == 1
    assert tester.phase == ("problem" if stop_on_warning else "completed")


def test_stop_during_work_collects_without_next_case(tmp_path: Path) -> None:
    """
    Keep Stop effective while a worker is awaiting collection.
    """
    tester, runner, _ = make_tester(tmp_path, ["completed", "completed"])
    start(tester)
    tester.poll()
    tester.stop()
    assert tester.active and tester.phase == "stopping"
    tester.poll()
    assert not tester.active and tester.phase == "stopped" and len(runner.jobs) == 1


def test_stop_between_cases_never_launches_the_next_input(tmp_path: Path) -> None:
    """
    Leave a distinct event boundary for a queued Stop after synchronous native construction.
    """
    tester, runner, _ = make_tester(tmp_path, ["completed", "completed"])
    start(tester)
    tester.poll()
    tester.poll()
    tester.stop()
    tester.poll()
    assert not tester.active and len(runner.jobs) == 1 and tester.passed == 1


def test_source_drift_stops_before_another_case(tmp_path: Path) -> None:
    """
    Refuse a new test input when its frozen executable policy has changed.
    """
    tester, runner, _ = make_tester(tmp_path, ["completed"])
    start(tester)
    tester.verify = lambda: {"source": "changed"}
    tester.poll()
    assert not tester.active and not runner.jobs and "sources changed" in tester.reason


def test_unmeasured_contact_always_stops_even_when_native_warnings_are_allowed(
    tmp_path: Path,
) -> None:
    """
    Do not continue through the temporary geometry-only contact override.
    """
    tester, runner, _ = make_tester(tmp_path, ["completed_with_warning"])
    start(tester, warnings=False)
    tester.poll()
    (runner.jobs[0] / "numerical-result.json").write_text(json.dumps({"contact": "unresolved"}))
    tester.poll()
    assert not tester.active and "Contact" in tester.reason


def test_source_change_during_work_cancels_before_more_native_work(tmp_path: Path) -> None:
    """
    Collect a source-triggered stop through the cancellation path, then remain latched.
    """
    tester, runner, _ = make_tester(tmp_path, ["completed", "completed"])
    start(tester)
    tester.poll()
    tester.verify = lambda: {"source": "changed"}
    tester.poll()
    assert tester.active and tester.phase == "stopping" and runner.cancelled
    tester.poll()
    assert not tester.active and tester.phase == "problem" and len(runner.jobs) == 1


def test_persistence_failure_stops_scheduling_even_if_status_cannot_be_saved(
    tmp_path: Path,
) -> None:
    """
    Cancel the owned worker when the log filesystem fails instead of continuing silently.
    """
    tester, runner, _ = make_tester(tmp_path, ["completed", "completed"])
    start(tester)
    tester.poll()
    assert tester.journal is not None
    tester.journal.status = Mock(side_effect=OSError("disk full"))
    poll = runner.poll
    runner.poll = Mock(return_value=None)
    tester.poll()
    assert runner.cancelled and tester.phase == "stopping"
    runner.poll = poll
    tester.poll()
    assert not tester.active and len(runner.jobs) == 1 and "persisted" in tester.reason


def test_setup_stop_is_not_a_geometry_attempt_and_new_start_does_not_rewrite_it(
    tmp_path: Path,
) -> None:
    """
    Label a preview interruption before launch, preserve its journal, and allow a new explicit run.
    """
    tester, runner, _ = make_tester(tmp_path, ["completed"])
    tester.prepare = Mock(
        side_effect=RuntimeError("Scheduling limit reached before gym end profiles")
    )
    start(tester)
    tester.poll()
    assert not tester.active and tester.attempted == tester.passed == 0
    assert tester.reason.startswith("Tester setup stopped before solver launch:")
    assert not runner.jobs and tester.journal is not None
    previous = tester.journal.directory
    logs = {p.name: p.read_bytes() for p in previous.iterdir()}
    tester.prepare = Mock()
    start(tester, limit=1)
    tester.poll()
    tester.poll()
    assert tester.phase == "completed" and tester.attempted == tester.passed == 1
    assert {p.name: p.read_bytes() for p in previous.iterdir()} == logs
