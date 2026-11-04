"""
Expose one bounded selected solver while keeping historical seed-discovery procedures retired.
"""

from __future__ import annotations

import json
import math
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
from experiments.experiment_ribbon_feature_insertion.contact_measurement import ContactPolicy

from . import lock, progress
from .lock import ROOT
from .settings import Settings
from .versions import DEFAULT_VERSION, METHODS, V2
from .versions import method as solver_method


class Controller(ProcedureController):
    """
    Reuse the existing owned-worker cancellation/replay boundary for one new procedure.

    Accepted construction and rejected inspection have separate callbacks and
    dispositions. Optional rejected bodies never count as solver acceptance.
    """

    def __init__(
        self,
        python: Path,
        directory: Path,
        document_id: str,
        build: Callable[[Path], dict[str, Any]],
        *,
        native_point_tolerance_mm: float = 1e-5,
        contact_policy: ContactPolicy = ContactPolicy.STRICT,
        inspect_rejected: Callable[[Path], dict[str, Any]] | None = None,
    ) -> None:
        """
        Bind the configured SDK, explicit design identity and owned native-build callback.
        """
        super().__init__(python, directory)
        if (
            type(native_point_tolerance_mm) not in (int, float)
            or not math.isfinite(native_point_tolerance_mm)
            or native_point_tolerance_mm <= 0
        ):
            raise ValueError("Native point tolerance must be finite and positive")
        self.document_id = document_id
        self.build = build
        self.inspect_rejected = inspect_rejected
        self.native_point_tolerance_mm = native_point_tolerance_mm
        self.contact_policy = ContactPolicy(contact_policy)
        self._active_version = DEFAULT_VERSION
        self._active_settings = solver_method(DEFAULT_VERSION).defaults
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
            or choices[0].get("id") not in tuple(entry.identifier for entry in METHODS)
        ):
            super().start(request, targets, gym=gym)
            return
        if set(choices[0]) != {"id", "settings"}:
            raise ValueError("Selected solver requests require id and settings only")
        settings = Settings.parse(choices[0]["settings"])
        selected = solver_method(choices[0]["id"])
        targets = Targets.capture(targets)
        context = validate(gym, targets)
        if context is None:
            raise ValueError("Run the selected solver from a frozen gym layout")
        pins = lock.verify()
        self.directory.mkdir(parents=True, exist_ok=True)
        job = self.directory / ("selected-" + uuid4().hex)
        job.mkdir()
        result_id = "run-" + job.name + ":" + selected.identifier
        write_document(
            job / "plan.json",
            {
                "version": selected.identifier,
                "result_id": result_id,
                "targets": targets_payload(targets),
                "gym": context,
                "settings": asdict(settings),
                "sources": pins,
                "document_id": self.document_id,
                "native_point_tolerance_mm": self.native_point_tolerance_mm,
                "contact_measurement_policy": self.contact_policy.value
                if selected.identifier == V2
                else ContactPolicy.STRICT.value,
                "limits": {
                    "numerical_seconds": 120,
                    "native_seconds": 120,
                    "rss_bytes": 4294967296,
                    "launch_rss_kib": 3984588,
                },
                "native_prediction": "Unknown; numerical acceptance is separate from native fidelity",
                "failed_inspection": "One native attempt for a closed rejected route, then scaffold fallback; never acceptance",
                "stop": "First failure stops routing/testing; rejected native inspection is separate and attempted once. Source/resource/cancellation stops inspection; no retry or tolerance changes.",
            },
        )
        self._job, self._started, self._seconds, self._cancelled = job, perf_counter(), 120, None
        self._log = (job / "worker.log").open("x")
        progress.append(job, "control", "Request validated; launching numerical worker.")
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
        except OSError as error:
            if self._log is not None:
                self._log.close()
            self._log = None
            progress.append(job, "control", f"Worker launch failed: {error}")
            self._status.update(status="stopped", detail=f"Worker launch failed: {error}")
            raise
        self._active_settings = settings
        self._active_version = selected.identifier
        self._status = {
            "status": "running",
            "phase": "numerical",
            "detail": "Selected material solver running; fixed endpoints and source lock retained.",
            "procedure": selected.identifier,
            "completed": 0,
            "total": 1,
            "job": str(job),
        }

    def poll(self) -> Path | None:
        """
        Build accepted material geometry once and append native disposition in a new manifest.
        """
        previous_process = self._process
        manifest = super().poll()
        if manifest is None:
            if previous_process is not None and self._process is None and self._job is not None:
                output = progress.tail(self._job / "worker.log", 4000).strip()
                progress.append(
                    self._job, "control", self._status["detail"] + ("\n" + output if output else "")
                )
            return None
        document = json.loads(manifest.read_text())
        job = manifest.parent
        if self._cancelled is not None:
            message = (
                "Numerical work collected after cancellation; native construction not attempted."
            )
            progress.append(job, "control", message)
            self._status.update(status="cancelled", phase="finished", detail=message)
            return manifest
        if not (job / "route.json").exists() or document.get("stopped"):
            progress.append(
                job,
                "numerical",
                str(
                    document.get("stopped")
                    or "No accepted route was produced; native construction was not attempted."
                ),
            )
            if not document.get("stopped"):
                self._status.update(
                    status="unresolved",
                    phase="finished",
                    detail="No accepted route was produced; native construction was not attempted.",
                )
            if (
                not document.get("stopped")
                and self.inspect_rejected is not None
                and (job / "rejected-geometry.json").exists()
            ):
                return self._inspect_rejected(manifest, document)
            return manifest
        self._status.update(
            status="running",
            detail="Building native geometry and checking development fidelity.",
            phase="native",
        )
        progress.append(job, "control", "Numerical result collected; starting native construction.")
        try:
            native = self.build(job)
        except (ArithmeticError, OSError, RuntimeError, TypeError, ValueError) as error:
            message = f"Native stage could not complete: {type(error).__name__}: {error}"
            progress.append(job, "native", message)
            self._status.update(status="stopped", phase="finished", detail=message)
            raise
        success = native.get("status") in (
            "built_and_named_fidelity_checks_pass",
            "built_with_precision_warning",
        )
        precision_warning = native.get("status") == "built_with_precision_warning"
        method = document["solvers"][0]
        contact_warning = method.get("contact_warning") is True
        errors = str(native.get("error") or "Unknown native failure").strip().splitlines()
        failure = errors[-1] if errors else "Unknown native failure"
        method["detail"] = (
            "Numerical material/cap/contact and named native material fidelity pass; full physical audit remains unmeasured."
            if success
            else "Numerical route retained for diagnosis; native build/fidelity failed: " + failure
        )
        if success and contact_warning:
            method["detail"] = (
                "Native material fidelity passes; contact measurement aborted at its pair limit and remains unmeasured (temporary gym override). Full physical audit remains unmeasured."
            )
        if precision_warning:
            method["detail"] = (
                "Native solid displayed with dimensional accuracy warnings below 0.01 mm; "
                "strict accuracy findings retained. Topology and angular checks pass. "
                "Full physical audit remains unmeasured."
            )
            if contact_warning:
                method["detail"] += " Contact measurement remains unmeasured (temporary override)."
            method["native_precision_warning"] = native.get("precision_warning")
        method["status"] = "recorded" if success else "stopped"
        method["rules"] = [
            rule for rule in method["rules"] if rule.get("name") != "Native material fidelity"
        ]
        method["rules"].append(
            {
                "name": "Native material fidelity",
                "status": "warning" if precision_warning else "measured" if success else "failed",
                "detail": "Original dimensional accuracy goals missed; sub-0.01 mm warnings retained."
                if precision_warning
                else "Surface, ordered guide, seam and cap gates; full physical audit unmeasured.",
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
            status=(
                "completed_with_warning" if contact_warning or precision_warning else "completed"
            )
            if success
            else "stopped",
            detail=method["detail"],
            native=summary,
            phase="finished",
            elapsed_seconds=perf_counter() - self._started,
        )
        progress.append(job, "complete" if success else "failed", method["detail"])
        return final

    def _inspect_rejected(self, manifest: Path, document: dict[str, Any]) -> Path:
        """
        Append optional native inspection evidence while preserving the unresolved stop.
        """
        assert self.inspect_rejected is not None
        job = manifest.parent
        try:
            result = self.inspect_rejected(job)
        except (ArithmeticError, OSError, RuntimeError, TypeError, ValueError) as error:
            result = {"built": 0, "error": f"{type(error).__name__}: {error}"}
        message = (
            "Rejected route displayed as a native inspection body; NOT ACCEPTED."
            if result.get("built") == 1
            else "Rejected route retained as diagnostic scaffold; native inspection unavailable."
        )
        progress.append(job, "inspection", message)
        document["rejected_native_result"] = result
        document["solvers"][0]["detail"] += " " + message
        self._status.update(
            status="unresolved",
            phase="finished",
            detail=self._status["detail"] + " " + message,
            inspection={key: value for key, value in result.items() if key != "rss_samples"},
        )
        final = job / "inspection-manifest.json"
        write_document(final, document)
        return final

    def state(self) -> dict[str, Any]:
        """
        Advertise progress and the last launched controls, retaining settings across palette reconnects.
        """
        return {
            **super().state(),
            "job": str(self._job) if self._job is not None else None,
            "build_log": progress.read(self._job),
            "active_solver": {
                **self._method_payload(self._active_version),
                "settings": asdict(self._active_settings),
            },
            "available_solvers": [self._method_payload(entry.identifier) for entry in METHODS],
        }

    def _method_payload(self, identifier: str) -> dict[str, Any]:
        """
        Expose the session-only diagnostic override without changing either method's normal default.
        """
        policy = self.contact_policy if identifier == V2 else ContactPolicy.STRICT
        return {**solver_method(identifier).payload(), "contact_measurement_policy": policy.value}
