"""
Advance one ordinary gym run at a time and latch the first problem without retrying it.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

from devtools.ribbon_analysis.gym.boundary import (
    BOUNDARY_POLICY,
    EXTRA_ALLOWANCE_MM,
    BoundaryReport,
)
from devtools.ribbon_analysis.gym.scene import Scene
from devtools.ribbon_analysis.inspection.archive import write_document
from devtools.ribbon_analysis.inspection.run_contract import ProcedureRunner

from ..settings import Settings
from ..versions import method
from .image_replay import capture_record
from .journal import Journal, problem
from .screenshots import Screenshots
from .sequence import Specification


class Tester:
    """
    Keep an outcome-independent input schedule and bounded current-case memory.

    Polling only schedules the next case after a separate completed-case boundary.
    All geometry/native work remains in the ordinary controller and host callbacks.
    """

    def __init__(
        self,
        directory: Path,
        runner: ProcedureRunner,
        verify: Callable[[], dict[str, str]],
        guard: Callable[[], None],
        prepare: Callable[[Scene], None],
        cleanup: Callable[[], None],
        present: Callable[[Scene, Path | None], None],
        setup: Callable[[], None],
        capture: Callable[[Path], None] | None = None,
        measure_boundary: Callable[[Scene], BoundaryReport] | None = None,
    ) -> None:
        """
        Receive explicit ownership/resource boundaries rather than importing Fusion into scheduling.
        """
        self.directory, self.runner, self.verify, self.guard = directory, runner, verify, guard
        self.prepare, self.cleanup, self.present, self.setup = prepare, cleanup, present, setup
        self.capture = capture
        self.measure_boundary = measure_boundary
        self.boundary: BoundaryReport | None = None
        self.screenshots: Screenshots | None = None
        self.last_screenshot: dict[str, Any] | None = None
        self._capture_attempted = False
        self.active = False
        self.phase = "idle"
        self.reason = "Not started."
        self.journal: Journal | None = None
        self.specification: Specification | None = None
        self.scene: Scene | None = None
        self.manifest: Path | None = None
        self.job: str | None = None
        self.selection: dict[str, Any] = {}
        self.sources: dict[str, str] = {}
        self.attempted = self.passed = self.warnings = 0
        self._started = 0.0
        self._elapsed = 0.0
        self._stop_reason: str | None = None
        self._input: Path | None = None
        self._journal_error: str | None = None
        self._setup_done = False

    def start(self, specification: Any, selection: Any) -> None:
        """
        Validate and freeze the user's plan, then wait for a poll before the first case.
        """
        if self.active or self.runner.state().get("status") in ("running", "cancelling"):
            raise ValueError("Stop and collect the current work before starting a tester.")
        spec = Specification.parse(specification)
        if not isinstance(selection, dict) or set(selection) != {"id", "settings"}:
            raise ValueError("Choose one solver and its complete settings.")
        method(selection["id"])
        Settings.parse(selection["settings"])
        self.guard()
        sources = self.verify()
        chosen = json.loads(json.dumps(selection, allow_nan=False))
        if spec.screenshots.enabled and self.capture is None:
            raise ValueError("This tester has no viewport screenshot exporter.")
        journal = Journal(
            self.directory / ("range-" + uuid4().hex),
            {
                "schema": "ribbon-gym-tester-v1",
                "specification": spec.payload(),
                "selection": chosen,
                "sources": sources,
                "combinations_per_pass": spec.combinations,
                "limits": {
                    "numerical_seconds_per_case": 120,
                    "native_seconds_per_case": 120,
                    "rss_kib": 4194304,
                    "launch_rss_kib": 3984588,
                    "maximum_cases": spec.maximum_cases,
                },
                "scope": "User-started sequential gym testing. Zero case limit means continue until a problem or Stop. Each input is frozen before one normal solve/build/audit; no retry, outcome filtering or tolerance changes. Successful test geometry is cleared before the next case; logs persist. Existing user output is retained. Full physical audit remains unmeasured.",
                "gym_boundary": {
                    "policy": BOUNDARY_POLICY,
                    "enforced": self.measure_boundary is not None,
                    "measurement": "native_precise_body_bounds_in_component_coordinates",
                    "extra_layers": 1,
                    "extra_allowance_mm": EXTRA_ALLOWANCE_MM,
                    "graphics": False,
                    "solver_feedback": False,
                },
            },
        )
        screenshots = (
            Screenshots(spec.screenshots, journal.directory.name, self.capture)
            if spec.screenshots.enabled and self.capture is not None
            else None
        )
        self.specification, self.selection, self.sources, self.journal = (
            spec,
            chosen,
            sources,
            journal,
        )
        self.scene, self.manifest, self.job, self._input = None, None, None, None
        self.boundary = None
        self.attempted = self.passed = self.warnings = 0
        self._stop_reason = None
        self._journal_error = None
        self._setup_done = False
        self.screenshots, self.last_screenshot = screenshots, None
        self._capture_attempted = False
        self._started = perf_counter()
        self._elapsed = 0.0
        self.active, self.phase, self.reason = True, "next", "Ready to start the first case."
        self._save()

    def stop(self, reason: str = "Stopped by user.") -> None:
        """
        Stop scheduling immediately; collect numerical cancellation without starting native work.

        A supplied host-error reason remains a problem rather than a user cancellation.
        """
        if not self.active:
            return
        self._stop_reason = reason
        if self.phase == "running":
            self.runner.cancel()
            self.phase = "stopping"
            self.reason = "Stopping at the next safe operation boundary."
        else:
            self._finish(reason, "stopped" if reason == "Stopped by user." else "problem")
        self._save()

    def poll(self) -> None:
        """
        Launch or collect one case per call, stopping on the first failed boundary.
        """
        if not self.active:
            return
        try:
            if self.phase in ("running", "stopping"):
                if self.phase != "stopping":
                    self.guard()
                    if self.verify() != self.sources:
                        raise RuntimeError(
                            "Tester sources changed; no further cases are permitted."
                        )
                manifest = self.runner.poll()
                if manifest is not None:
                    self.manifest = manifest
                state = self.runner.state()
                if state.get("status") in ("running", "cancelling"):
                    self._save()
                    return
                self._complete(state)
            else:
                self._launch()
        except (ArithmeticError, OSError, RuntimeError, TypeError, ValueError) as error:
            context = (
                "Tester setup stopped before solver launch"
                if self.job is None and self._input is not None
                else "Tester stopped"
            )
            reason = f"{context}: {type(error).__name__}: {error}"
            if self.runner.state().get("status") in ("running", "cancelling"):
                self._stop_reason = reason
                self.runner.cancel()
                self.phase, self.reason = "stopping", reason
            else:
                self._finish(reason, "problem")
        self._save()

    def _launch(self) -> None:
        """
        Clear only the previous successful test body, freeze the next input and launch once.
        """
        assert self.specification is not None and self.journal is not None
        self.guard()
        if self.verify() != self.sources:
            raise RuntimeError("Tester sources changed; no case launched.")
        if not self._setup_done:
            self.setup()
            self._setup_done = True
        self.cleanup()
        scene = self.specification.scene(self.attempted)
        self.scene = scene
        self.boundary = None
        self.manifest, self.job, self._input = None, None, None
        self.last_screenshot = None
        self._capture_attempted = False
        input_path = self.journal.begin(self.attempted, scene)
        self._input = input_path
        self.prepare(scene)
        previous = self.runner.state().get("job")
        try:
            self.runner.start({"procedures": [self.selection]}, scene.targets, gym=scene.payload())
        finally:
            current = self.runner.state().get("job")
            if current != previous:
                self.job = current
        self.attempted += 1
        self.phase, self.reason = "running", f"Running case {self.attempted}."
        self.journal.append(
            {
                "event": "case_started",
                "case": self.attempted,
                "input": str(input_path),
                "job": self.job,
            }
        )

    def _complete(self, state: dict[str, Any]) -> None:
        """
        Persist the terminal disposition before deciding whether another input is allowed.
        """
        assert self.specification is not None and self.journal is not None
        reason = self._stop_reason or problem(state, self.specification.stop_on_warnings)
        if reason is None and self.measure_boundary is not None:
            assert self.scene is not None and self.job is not None
            boundary = self.measure_boundary(self.scene)
            self.boundary = boundary
            write_document(Path(self.job) / "gym-boundary.json", boundary.payload())
            reason = boundary.problem
        self.journal.append(
            {
                "event": "case_finished",
                "case": self.attempted,
                "job": self.job,
                "input": str(self._input) if self._input else None,
                "manifest": str(self.manifest) if self.manifest else None,
                "status": state.get("status"),
                "detail": state.get("detail"),
                "problem": reason,
                "native": state.get("native"),
                "gym_boundary": self.boundary.payload() if self.boundary else None,
            }
        )
        if reason:
            self._finish(reason, "stopped" if reason == "Stopped by user." else "problem")
            return
        self.passed += 1
        self.warnings += int(state.get("status") == "completed_with_warning")
        self._capture()
        if self.specification.maximum_cases and self.attempted >= self.specification.maximum_cases:
            self._finish("Configured case limit reached.", "completed")
            return
        self.phase, self.reason = "next", "Case passed; next case waits for the next poll."

    def _finish(self, reason: str, phase: str) -> None:
        """
        Latch the stop before inspection so a display error cannot schedule more cases.
        """
        self.active, self.phase, self.reason = False, phase, reason
        if self.scene is not None:
            try:
                self.present(self.scene, self.manifest)
            except (ArithmeticError, OSError, RuntimeError, TypeError, ValueError) as error:
                self.reason += f" Inspection could not open: {type(error).__name__}: {error}"
                # Do not label a stale viewport as the failed case when presentation failed.
                self._capture_attempted = True
            try:
                self._capture()
            except (OSError, RuntimeError, ValueError) as error:
                self.reason += f" Screenshot failed: {type(error).__name__}: {error}"
        if self.journal is not None:
            try:
                self.journal.append(
                    {
                        "event": "tester_stopped",
                        "phase": self.phase,
                        "reason": self.reason,
                        "job": self.job,
                    }
                )
            except OSError as error:
                # Failure logging is fail-soft only after the scheduling latch is closed.
                failure = f"Stop record could not be persisted: {error}"
                self._journal_error = failure
                self.reason += " " + failure
        self._elapsed = perf_counter() - self._started

    def _capture(self) -> None:
        """
        Record one screenshot after terminal work, before another case can clear its geometry.
        """
        if self.screenshots is None or self._capture_attempted or self._input is None:
            return
        self._capture_attempted = True
        assert self.journal is not None
        try:
            replay = capture_record(self._input, self.journal.directory / "plan.json", self.job)
            saved = self.screenshots.save(self._input.stem, replay)
        except (OSError, RuntimeError, ValueError) as error:
            self.journal.append(
                {"event": "screenshot_failed", "input": str(self._input), "error": str(error)}
            )
            raise
        self.last_screenshot = saved
        self.journal.append({"event": "screenshot_saved", "input": str(self._input), **saved})

    def inspect(self) -> None:
        """
        Reopen the retained last case after an external command or display error is cleared.
        """
        if self.active or self.scene is None:
            raise ValueError("Stop the tester before inspecting its last case.")
        self.present(self.scene, self.manifest)

    def state(self) -> dict[str, Any]:
        """
        Expose bounded reconnect data; full per-case logs stay on disk.
        """
        return {
            "active": self.active,
            "phase": self.phase,
            "reason": self.reason,
            "attempted": self.attempted,
            "passed": self.passed,
            "warnings": self.warnings,
            "directory": str(self.journal.directory) if self.journal else None,
            "job": self.job,
            "input": str(self._input) if self._input else None,
            "current": {
                "config": asdict(self.scene.config),
                "a": self.scene.a.payload(),
                "b": self.scene.b.payload(),
            }
            if self.scene
            else None,
            "elapsed_seconds": perf_counter() - self._started if self.active else self._elapsed,
            "specification": self.specification.payload() if self.specification else None,
            "screenshot": self.last_screenshot,
            "gym_boundary": self.boundary.payload() if self.boundary else None,
        }

    def _save(self) -> None:
        """
        Preserve the latest latch/counter state for inspection after interruption.
        """
        if self.journal is not None and self._journal_error is None:
            try:
                self.journal.status(self.state())
            except OSError as error:
                # Stop scheduling even when the filesystem cannot retain the final status.
                self._journal_error = f"Tester status could not be persisted: {error}"
                self.reason = self._journal_error
                if self.runner.state().get("status") in ("running", "cancelling"):
                    self.runner.cancel()
                    self._stop_reason, self.phase = self._journal_error, "stopping"
                else:
                    self.active, self.phase = False, "problem"
                    self._elapsed = perf_counter() - self._started
