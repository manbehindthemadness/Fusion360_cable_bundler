"""
Expose one bounded selected solver while keeping historical seed-discovery procedures retired.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.gym.handoff import validate
from devtools.ribbon_analysis.inspection.archive import targets_payload, write_document
from experiments.experiment_ribbon_diagnostic_viewer.controller import ProcedureController

from . import lock
from .lock import ROOT
from .settings import VERSION, Settings


class Controller(ProcedureController):
    """
    Reuse the existing owned-worker cancellation/replay boundary for one new procedure.

    Native building is supplied by the owning Fusion workspace and runs only
    after completed numerical acceptance. No historical solver is enabled.
    """

    def __init__(
        self,
        python: Path,
        directory: Path,
        document_id: str,
        build: Callable[[Path], dict[str, Any]],
    ) -> None:
        """
        Bind the configured SDK, explicit design identity and owned native-build callback.
        """
        super().__init__(python, directory)
        self.document_id = document_id
        self.build = build
        self._status["detail"] = (
            "Selected material solver ready; historical seed-discovery methods remain retired."
        )

    def open_example(self, identifier: str) -> Path:
        """
        Reuse frozen-layout selection without advertising the retired replacement placeholder.
        """
        manifest = super().open_example(identifier)
        self._status["detail"] = (
            "Frozen inputs selected. Run the selected solver from a gym layout."
        )
        return manifest

    def start(
        self, request: dict[str, Any], targets: Targets, *, gym: dict[str, Any] | None = None
    ) -> None:
        """
        Validate one locked procedure before freezing sources/targets and launching a worker.
        """
        if self._process is not None:
            raise ValueError("A numerical job is already awaiting completion")
        choices = request.get("procedures")
        if (
            set(request) != {"procedures"}
            or not isinstance(choices, list)
            or len(choices) != 1
            or not isinstance(choices[0], dict)
            or choices[0].get("id") != VERSION
        ):
            super().start(request, targets, gym=gym)
            return
        if set(choices[0]) != {"id", "settings"}:
            raise ValueError("Selected solver requests require id and settings only")
        settings = Settings.parse(choices[0]["settings"])
        targets = Targets.capture(targets)
        context = validate(gym, targets)
        if context is None:
            raise ValueError("Run the selected solver from a frozen gym layout")
        pins = lock.verify()
        self.directory.mkdir(parents=True, exist_ok=True)
        job = self.directory / ("selected-" + uuid4().hex)
        job.mkdir()
        result_id = "run-" + job.name + ":" + VERSION
        write_document(
            job / "plan.json",
            {
                "version": VERSION,
                "result_id": result_id,
                "targets": targets_payload(targets),
                "gym": context,
                "settings": asdict(settings),
                "sources": pins,
                "document_id": self.document_id,
                "limits": {
                    "numerical_seconds": 120,
                    "native_seconds": 120,
                    "rss_bytes": 4294967296,
                    "launch_rss_kib": 3984588,
                },
                "native_prediction": "Unknown; numerical acceptance is separate from native fidelity",
                "stop": "First source/resource/API/numerical/native-fidelity error; retain all evidence, no retry or tolerance changes",
            },
        )
        self._job, self._started, self._seconds, self._cancelled = job, perf_counter(), 120, None
        self._log = (job / "worker.log").open("x")
        environment = dict(os.environ)
        environment.pop("PYTHONHOME", None)
        environment.pop("PYTHONPATH", None)
        try:
            self._process = subprocess.Popen(
                [
                    str(self.python),
                    "-m",
                    "experiments.experiment_ribbon_locked_solver.worker",
                    str(job),
                ],
                cwd=ROOT,
                stdout=self._log,
                stderr=subprocess.STDOUT,
                text=True,
                env=environment,
            )
        except OSError:
            self._log.close()
            self._log = None
            raise
        self._status = {
            "status": "running",
            "detail": "Selected material solver running; fixed endpoints and source lock retained.",
            "procedure": VERSION,
            "completed": 0,
            "total": 1,
            "job": str(job),
        }

    def poll(self) -> Path | None:
        """
        Build accepted material geometry once and append native disposition in a new manifest.
        """
        manifest = super().poll()
        if manifest is None:
            return None
        document = json.loads(manifest.read_text())
        job = manifest.parent
        if not (job / "route.json").exists() or document.get("stopped"):
            return manifest
        self._status.update(
            status="running",
            detail="Building native geometry and checking development fidelity.",
            phase="native",
        )
        native = self.build(job)
        success = native.get("status") == "built_and_named_fidelity_checks_pass"
        method = document["solvers"][0]
        errors = str(native.get("error") or "Unknown native failure").strip().splitlines()
        failure = errors[-1] if errors else "Unknown native failure"
        method["detail"] = (
            "Numerical material/cap/contact and named native material fidelity pass; full physical audit remains unmeasured."
            if success
            else "Numerical route retained for diagnosis; native build/fidelity failed: " + failure
        )
        method["status"] = "recorded" if success else "stopped"
        method["rules"] = [
            rule for rule in method["rules"] if rule.get("name") != "Native material fidelity"
        ]
        method["rules"].append(
            {
                "name": "Native material fidelity",
                "status": "measured" if success else "failed",
                "detail": "Surface, ordered guide, seam and cap gates; full physical audit unmeasured.",
                "value": None,
                "limit": None,
            }
        )
        document["native_result"] = str(job / "native-result.json")
        if not success:
            document["stopped"] = method["detail"]
        final = job / "native-manifest.json"
        write_document(final, document)
        summary = {k: v for k, v in native.items() if k not in {"audit", "rss_samples"}}
        self._status.update(
            status="completed" if success else "stopped",
            detail=method["detail"],
            native=summary,
            phase="finished",
            elapsed_seconds=perf_counter() - self._started,
        )
        return final

    def state(self) -> dict[str, Any]:
        """
        Advertise the selected method separately from unavailable historical discovery.
        """
        return {
            **super().state(),
            "active_solver": {
                "id": VERSION,
                "label": "Selected material solver v1",
                "settings": asdict(Settings()),
                "scope": "Joint construction, optional aesthetic smoothing and optional material UV metadata; full physical compliance unverified",
            },
        }
