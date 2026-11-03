"""
Manage authored inputs and archived results after retirement of path discovery.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from time import perf_counter
from typing import Any, TextIO
from uuid import uuid4

from devtools.ribbon_analysis import budget
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.gym.handoff import identity
from devtools.ribbon_analysis.inspection.session import Session
from devtools.ribbon_analysis.inspection.values import integer_value, json_object

from . import examples, procedures
from .procedures import ROOT


class ProcedureController:
    """
    Retain replay and input authoring while refusing new path-search launches.

    Cancellation and collection remain for an owned worker started before retirement
    in a live Fusion session. New launches reject. Retained plans and histories are
    never used as implicit retries.
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
        self._layout_labels: dict[str, str] = {}
        self._example = next(iter(self._examples), "")
        self._status: dict[str, Any] = {
            "status": "idle",
            "detail": procedures.DISCOVERY_REMOVED,
        }

    def start(
        self, request: dict[str, Any], targets: Targets, *, gym: dict[str, Any] | None = None
    ) -> None:
        """
        Reject retired procedures before creating a plan, directory or subprocess.
        """
        del targets, gym
        if self._process is not None:
            raise ValueError("A numerical job is already awaiting completion.")
        if set(request) not in ({"procedures"}, {"procedures", "comparison"}):
            raise ValueError("Run requests require selections and an optional explicit comparison.")
        procedures.selections(request["procedures"])

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
        Describe unavailable discovery and retained input/replay capabilities.
        """
        return {
            "catalog": procedures.catalog(),
            "examples": [
                *examples.EXAMPLES,
                *({"id": key, "label": label} for key, label in self._layout_labels.items()),
            ],
            "example": self._example,
            "discovery_available": False,
            "ablation_controls": {},
            **self._status,
        }

    def register_layout(self, manifest: Path, label: str) -> str:
        """
        Add an immutable endpoint-only case without authoring or running a route.
        """
        if self._process is not None:
            raise ValueError("Stop and collect the active job before sending a gym layout.")
        session = Session(manifest)
        if session.gym is None or any(method["has_result"] for method in session.methods):
            raise ValueError("Send a frozen gym input layout without a solver result.")
        identifier = identity(session.gym)
        self._examples[identifier] = manifest.resolve()
        self._layout_labels[identifier] = label
        return identifier

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
            "detail": "Example selected. " + procedures.DISCOVERY_REMOVED,
        }
        return self._examples[identifier]

    def inspect_layout(self, manifest: Path, label: str) -> Path:
        """
        Select finished-run inputs while preserving the current job's status and build log.
        """
        self._example = self.register_layout(manifest, label)
        return manifest.resolve()
