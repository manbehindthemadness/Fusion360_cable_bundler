"""
Run one source-pinned selected solver job in the configured host-only SDK subprocess.
"""

from __future__ import annotations

import json
import resource
import sys
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, process_time
from typing import Any

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.gym.handoff import validate
from devtools.ribbon_analysis.inspection.archive import (
    SCHEMA,
    RuleObservation,
    snapshot_payload,
    write_document,
)
from experiments.experiment_ribbon_contraction.runner import snapshot

from .inspection import freeze
from .lock import verify
from .progress import append
from .settings import VERSION, Settings
from .solver import solve


def run(directory: Path) -> Path:
    """
    Preserve unresolved/failed results and every proposal; never launch native construction here.
    """
    started, cpu_started = perf_counter(), process_time()
    append(directory, "numerical", "Worker started; validating frozen inputs and source lock.")
    plan = json.loads((directory / "plan.json").read_text())
    pins = verify()
    if plan.get("version") != VERSION or plan.get("sources") != pins:
        raise RuntimeError("Worker solver version/source mismatch")
    target = plan["targets"]
    targets = Targets.capture(
        Targets(**{k: Vector3(**v) if isinstance(v, dict) else v for k, v in target.items()})
    )
    gym = validate(plan.get("gym"), targets)
    if gym is None:
        raise ValueError("The selected gym procedure requires a frozen gym layout")
    settings = Settings.parse(plan["settings"])
    last_sources = perf_counter()
    last_stage, last_report = "", 0.0
    append(
        directory,
        "numerical",
        f"Inputs validated; first-pass optimization {'on' if settings.first_pass_optimization else 'off'}, smoothing {settings.smoothing_percent:g}%.",
    )

    def checkpoint() -> None:
        """
        Enforce cooperative cancellation,120seconds,4GiBRSS and fixed source policy.
        """
        nonlocal last_sources
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss = peak if sys.platform == "darwin" else peak * 1024
        if (directory / "cancel").exists() or perf_counter() - started > 120 or rss >= 4294967296:
            raise TimeoutError("Selected gym solver resource/cancellation limit")
        if perf_counter() - last_sources > 0.5:
            if verify() != pins:
                raise RuntimeError("Selected solver source drift")
            last_sources = perf_counter()

    def record(event: dict[str, Any]) -> None:
        """
        Append each algebraic, contact, radius and layout proposal before advancing.
        """
        nonlocal last_stage, last_report
        with (directory / "trials.jsonl").open("a") as stream:
            stream.write(json.dumps(event, allow_nan=False) + "\n")
        stage = str(event.get("stage") or "smoothing")
        now = perf_counter()
        if stage != last_stage or now - last_report >= 0.5:
            append(directory, stage, str(event.get("status") or "Working"))
            last_stage, last_report = stage, now

    method: dict[str, Any] = {
        "id": plan["result_id"],
        "label": "Selected material solver v1",
        "source": "experiments/experiment_ribbon_locked_solver/solver.py",
        "procedure": VERSION,
        "settings": {
            **asdict(settings),
            "solver_version": VERSION,
            "path_rules": "material-fold equal lengths + pinch + no lateral bending + thick contact",
        },
        "status": "unresolved",
        "detail": "No accepted route within the selected finite families/budget.",
        "rules": [],
    }
    stopped = None
    try:
        checkpoint()
        result = solve(targets, settings, checkpoint, record)
        write_document(directory / "numerical-result.json", result.detail)
        append(
            directory,
            "numerical",
            "Route accepted; writing geometry plan and checking display data."
            if result.route is not None
            else "No route accepted within the solver's rules and finite budget; no native build.",
        )
        if result.route is not None:
            if result.first_pass is None:
                raise ArithmeticError("Accepted route lacks its first-pass provenance")
            write_document(directory / "route.json", snapshot(result.route))
            write_document(directory / "first-pass.json", snapshot(result.first_pass))
            if result.material_uv is not None:
                write_document(directory / "material-uv.json", result.material_uv)
            method.update(
                status="recorded",
                detail="Numerical material/cap/contact checks pass; native construction/fidelity remain unattempted.",
                snapshot=snapshot_payload(freeze(result.route, plan["result_id"])),
            )
            method["rules"] = [
                asdict(
                    RuleObservation(
                        "Numerical material/cap/contact",
                        "measured",
                        "Exact material primitives with independent cap/contact gates; cubic display is an approximation.",
                        result.detail["cap_error_mm"],
                        1e-7,
                    )
                )
            ]
    except (ArithmeticError, OSError, RuntimeError, TimeoutError, TypeError, ValueError) as error:
        stopped = f"{type(error).__name__}: {error}"
        append(directory, "failed", stopped)
        method.update(status="stopped", detail=stopped)
    method["rules"].extend(
        [
            asdict(
                RuleObservation(
                    "Native material fidelity",
                    "unmeasured",
                    "Native construction and fidelity occur separately in Fusion.",
                )
            ),
            asdict(
                RuleObservation(
                    "Full physical audit",
                    "unmeasured",
                    "Numerical and native fidelity checks do not establish complete physical acceptance.",
                )
            ),
        ]
    )
    manifest = {
        "schema": SCHEMA,
        "targets": target,
        "gym": gym,
        "solvers": [method],
        "sources": pins,
        "seconds": perf_counter() - started,
        "cpu_seconds": process_time() - cpu_started,
    }
    if stopped:
        manifest["stopped"] = stopped
    destination = directory / "manifest.json"
    write_document(destination, manifest)
    if not stopped and (directory / "route.json").exists():
        append(directory, "numerical", "Numerical stage complete; waiting for native construction.")
    return destination


if __name__ == "__main__":
    run(Path(sys.argv[1]).resolve())
