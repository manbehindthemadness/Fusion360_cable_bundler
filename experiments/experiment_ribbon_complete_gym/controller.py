"""
Own one manually requested complete gym worker and collect its honest diagnostic disposition.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from time import perf_counter
from typing import Any, TextIO
from uuid import uuid4

from devtools.ribbon_analysis.gym.scene import Scene

from . import job, lock


class Controller:
    """
    Keep current gym edits separate from a frozen single-case numerical history.

    No operation installs or invokes a native builder. Every launch requires an
    explicit start; polling and cancellation cannot launch another case or retry.
    """

    def __init__(self, python: Path, directory: Path) -> None:
        """
        Require the project SDK and an ignored repository-owned diagnostic directory.
        """
        if (
            not python.is_file()
            or python.resolve() != (lock.ROOT / ".venv/bin/python").resolve()
            or (lock.ROOT / "artifacts/verification").resolve() not in directory.resolve().parents
        ):
            raise ValueError("Complete gym requires project SDK and owned verification output")
        self.python, self.directory = python, directory
        self.process: subprocess.Popen[str] | None = None
        self.log: TextIO | None = None
        self.job: Path | None = None
        self.started = 0.0
        self.cancelled: float | None = None
        self.report: dict[str, Any] = {"status": "idle"}

    def start(self, scene: Scene, tolerance_mm: float) -> None:
        """
        Freeze every complete target before launching exactly one owned worker.
        """
        if self.process is not None:
            raise ValueError("Collect or cancel the active complete gym job first")
        namespace = uuid4()
        directory = self.directory / ("manual-" + namespace.hex)
        job.freeze(scene, namespace, directory, tolerance_mm)
        environment = dict(os.environ)
        environment.pop("PYTHONHOME", None)
        environment.pop("PYTHONPATH", None)
        self.job, self.started, self.cancelled = directory, perf_counter(), None
        log = (directory / "worker.log").open("x")
        self.log = log
        self.report = {"status": "running", "job": str(directory)}
        try:
            self.process = subprocess.Popen(
                [
                    str(self.python),
                    "-m",
                    "experiments.experiment_ribbon_complete_gym.worker",
                    str(directory),
                ],
                cwd=lock.ROOT,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError as error:
            log.close()
            self.log = None
            self.report.update(status="stopped", error=f"Worker launch failed: {error}")
            raise

    def cancel(self) -> None:
        """
        Request cooperative cancellation of this worker without scheduling replacement work.
        """
        if self.process is not None and self.job is not None and self.cancelled is None:
            (self.job / "cancel").touch(exist_ok=False)
            self.cancelled = perf_counter()
            self.report["status"] = "cancelling"

    def poll(self) -> dict[str, Any]:
        """
        Collect once, preserving incomplete prefixes and terminating only the owned subprocess.
        """
        if self.process is None or self.job is None:
            return dict(self.report)
        if perf_counter() - self.started > job.LIMITS["seconds"] + 5:
            self.cancel()
        if self.cancelled is not None and perf_counter() - self.cancelled > 2:
            if self.process.poll() is None:
                self.process.terminate()
        if self.process.poll() is None:
            return dict(self.report)
        code = self.process.returncode
        self.process = None
        if self.log is not None:
            self.log.close()
            self.log = None
        result = self.job / "result.json"
        if result.is_file():
            self.report = json.loads(result.read_text())
            if not isinstance(self.report, dict) or self.report.get("status") not in (
                "stopped",
                "trunk_unresolved",
                "planned_material_violation",
                "unqualified",
            ):
                raise ValueError("Complete gym worker returned an unknown disposition")
            if code != 0:
                self.report["collection_error"] = f"Worker exited with code{code}"
                self.report["status"] = "stopped"
            if self.cancelled is not None:
                self.report["collection_note"] = (
                    "Cancellation requested; retained original worker outcome"
                )
        else:
            self.report = {
                "status": "stopped",
                "error": f"Worker exited({code}) without a complete receipt; partial files retained",
            }
        self.report["job"] = str(self.job)
        events = self.job / "events.jsonl"
        if events.is_file():
            content = events.read_text()
            lines = content.splitlines()
            rows = []
            for index, line in enumerate(lines):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    if index == len(lines) - 1 and not content.endswith("\n"):
                        break
                    raise
                if not isinstance(row, dict):
                    raise ValueError("Complete gym event must be an object")
                rows.append(row)
            self.report["material"] = next(
                (row for row in reversed(rows) if row.get("stage") == "complete_material_witness"),
                None,
            )
        return dict(self.report)
