"""
Own one opt-in project-SDK worker while keeping Fusion responsive for replay.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from time import perf_counter
from typing import Any, TextIO
from uuid import uuid4

from devtools.ribbon_analysis import budget
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.inspection.archive import (
    SCHEMA,
    targets_payload,
    write_document,
)
from devtools.ribbon_analysis.inspection.values import integer_value, json_object

from . import ablation, examples, procedures
from .procedures import ROOT


class ProcedureController:
    """
    Freeze settings before launch; isolate numerical modules from the live Fusion host.

    Cancellation and watchdog signals affect this controller's own SDK subprocess
    only. Workers perform no Fusion calls or native construction. Histories, plans
    and failed jobs are retained in unique directories, never used as implicit retries.
    """

    def __init__(
        self, python: Path, directory: Path, references: dict[str, Path] | None = None
    ) -> None:
        """
        Require the inspected project-local SDK and an explicit owned output directory.
        """
        if (
            not python.is_absolute()
            or not python.is_file()
            or python.parent.resolve() != (ROOT / ".venv/bin").resolve()
        ):
            raise ValueError("Configure the project-local .venv Python executable.")
        self.python, self.directory = python, directory.resolve()
        self._process: subprocess.Popen[str] | None = None
        self._log: TextIO | None = None
        self._job: Path | None = None
        self._started = 0.0
        self._seconds = 0.0
        self._cancelled: float | None = None
        self._examples = dict(references or {})
        self._example = next(iter(self._examples), "")
        self._status: dict[str, Any] = {
            "status": "idle",
            "detail": "Choose procedures and settings, then Run selected. No solver runs automatically.",
        }

    def start(self, request: dict[str, Any], targets: Targets) -> None:
        """
        Validate every option and archive a fixed one-case plan before starting work.
        """
        if self._process is not None:
            raise ValueError("A numerical job is already awaiting completion.")
        if set(request) not in ({"procedures"}, {"procedures", "comparison"}):
            raise ValueError("Run requests require selections and an optional explicit comparison.")
        selected = procedures.selections(request["procedures"])
        comparison = json_object(request["comparison"]) if "comparison" in request else None
        work = ablation.workloads(selected, comparison)
        if sum(item["settings"]["seconds"] for item in work) > 120:
            raise ValueError("Baseline plus ablation exceed the 120-second run budget.")
        targets = Targets.capture(targets)
        if targets.lines not in (1, 3):
            raise ValueError("Interactive examples support one or three conductors.")
        if budget.resident_kib() >= int(3.8 * 1024 * 1024):
            raise RuntimeError("Fusion lacks 3.8GiB launch headroom for a numerical job.")
        run_id = "run-" + uuid4().hex
        self.directory.mkdir(parents=True, exist_ok=True)
        job = self.directory / run_id
        job.mkdir()
        input_document = {
            "schema": SCHEMA,
            "targets": targets_payload(targets),
            "solvers": [
                {
                    "id": "input",
                    "label": "Frozen endpoint inputs",
                    "source": "Active diagnostic session",
                    "status": "not_run",
                    "detail": "Boundary inputs only; no solution supplied.",
                    "rules": [],
                }
            ],
        }
        write_document(job / "input.json", input_document)
        plan = {
            "schema": "ribbon-procedure-run-v1",
            "run_id": run_id,
            "targets": targets_payload(targets),
            "procedures": selected,
            "comparison": comparison,
            "sources": procedures.source_pins(),
            "minimum_radius_mm": 3 * targets.diameter_mm,
            "limits": {
                "aggregate_seconds": 120,
                "rss_kib": 4 * 1024 * 1024,
                "capture_bytes_per_method": 64 * 1024 * 1024,
                "aggregate_capture_bytes": 256 * 1024 * 1024,
                "native_solid_attempts": 0,
                "retries": 0,
            },
            "scope": "One existing development configuration, optional numerical comparisons from fixed endpoint inputs. Local legacy checks do not certify full-thickness collision or physical acceptance.",
        }
        write_document(job / "plan.json", plan)
        environment = dict(os.environ)
        for key in ("PYTHONHOME", "PYTHONPATH"):
            environment.pop(key, None)
        log = (job / "worker.log").open("x", encoding="utf-8")
        self._log = log
        try:
            self._process = subprocess.Popen(
                [
                    str(self.python),
                    "-m",
                    "experiments.experiment_ribbon_diagnostic_viewer.interactive_worker",
                    str(job),
                ],
                cwd=ROOT,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError:
            log.close()
            self._log = None
            self._status = {
                "status": "stopped",
                "detail": "Worker launch failed; frozen plan retained.",
                "directory": str(job),
            }
            raise
        self._job, self._started = job, perf_counter()
        self._seconds = sum(item["settings"]["seconds"] for item in work)
        self._cancelled = None
        self._status = {
            "status": "running",
            "detail": "Numerical worker started; search recording is included in the time limits.",
            "directory": str(job),
            "total": len(work),
        }

    def cancel(self) -> None:
        """
        Ask the active worker to stop before its next numerical checkpoint.
        """
        if self._process is not None and self._job is not None and self._cancelled is None:
            (self._job / "cancel").touch(exist_ok=True)
            self._cancelled = perf_counter()
            self._status.update(
                status="cancelling", detail="Stopping at the next numerical checkpoint."
            )

    def poll(self) -> Path | None:
        """
        Collect an immutable result once, enforcing a worker-only watchdog if needed.
        """
        process, job = self._process, self._job
        if process is None or job is None:
            return None
        now = perf_counter()
        if now - self._started > self._seconds + 5 or budget.resident_kib() >= 4 * 1024 * 1024:
            self.cancel()
        if self._cancelled is not None and now - self._cancelled > 2 and process.poll() is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass  # The owned worker finished between the poll and termination request.
            self._status.update(
                detail="Numerical worker did not stop at a checkpoint; termination requested. Recorded files retained."
            )
        if process.poll() is None:
            progress = job / "progress.json"
            if progress.is_file():
                self._status.update(json_object(json.loads(progress.read_text(encoding="utf-8"))))
                # A final progress write precedes process exit; keep polling until collected.
                self._status["status"] = "cancelling" if self._cancelled is not None else "running"
            return None
        self._process = None
        if self._log is not None:
            self._log.close()
            self._log = None
        manifest = job / "manifest.json"
        if not manifest.is_file():
            self._status.update(
                status="stopped",
                detail=f"Worker exited ({process.returncode}) without a complete result manifest; partial histories and log retained.",
            )
            return None
        document = json_object(json.loads(manifest.read_text(encoding="utf-8")))
        methods = document.get("solvers")
        if not isinstance(methods, list):
            raise ValueError("Worker result has no procedure dispositions.")
        identifiers = [
            item["id"]
            for item in methods
            if isinstance(item, dict) and item.get("snapshot") is not None
        ]
        self._status.update(
            status="stopped" if document.get("stopped") else "completed",
            detail=document.get("stopped")
            or "Results added to the selector; physical acceptance remains unresolved.",
            result_ids=identifiers,
            completed=sum(
                isinstance(item, dict) and item.get("status") != "not_run" for item in methods
            ),
            elapsed_seconds=document.get("seconds"),
        )
        return manifest

    def state(self) -> dict[str, Any]:
        """
        Describe implemented settings and current progress without executing a solver.
        """
        return {
            "catalog": procedures.catalog(),
            "examples": examples.EXAMPLES,
            "example": self._example,
            "demonstration": procedures.demonstration(),
            "ablation_controls": {
                entry.identifier: ablation.controls(entry.identifier)
                for entry in procedures.CATALOG
            },
            **self._status,
        }

    def open_example(self, identifier: str) -> Path:
        """
        Retain authored examples separately; refuse to change targets during a job.
        """
        if self._process is not None:
            raise ValueError("Stop and collect the active job before changing examples.")
        if identifier not in self._examples:
            display_budget = budget.NativeBudget(
                maximum_seconds=10, maximum_rss_kib=4 * 1024 * 1024, memory=budget.resident_kib
            )
            display_budget.check("example launch")
            if integer_value(display_budget.samples[-1]["rss_kib"]) >= int(3.8 * 1024 * 1024):
                raise RuntimeError("Example authoring lacks launch headroom.")
            directory = self.directory / ("example-" + identifier + "-" + uuid4().hex)
            last_checked = 0.0

            def checkpoint() -> None:
                """
                Sample authoring resources without spawning ps for every transport step.
                """
                nonlocal last_checked
                now = perf_counter()
                if now - last_checked >= 0.25:
                    display_budget.check("author reference")
                    last_checked = now

            self._examples[identifier] = examples.create(directory, identifier, checkpoint)
        self._example = identifier
        self._status = {
            "status": "idle",
            "detail": "Example selected; choose a solver or load the nine-procedure demonstration.",
        }
        return self._examples[identifier]
