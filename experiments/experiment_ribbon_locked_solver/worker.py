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
from typing import Any, TextIO

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.gym.handoff import validate
from devtools.ribbon_analysis.inspection.archive import (
    SCHEMA,
    RuleObservation,
    snapshot_payload,
    write_document,
)
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_feature_insertion.contact_measurement import ContactPolicy

from .inspection import freeze
from .lock import verify
from .progress import append
from .rejected_display import retain
from .settings import Settings
from .solver import solve
from .solver_v2 import solve as solve_v2
from .versions import V2
from .versions import method as solver_method


def run(directory: Path) -> Path:
    """
    Preserve every flushed proposal under one owned journal; never launch native construction here.

    Open the append stream once, retaining per-event flush before solver progress.
    The original worker clocks include opening and using the stream. Context
    ownership closes it on normal, rejected, cancelled and exceptional exits.
    Clear raw material measurements within these clocks before each job, even
    when a host-only caller reuses this process. Record bounded hit/miss counts
    after solving; these are computational measurements, not acceptance proofs.
    """
    started, cpu_started = perf_counter(), process_time()
    material_error.cache_clear()
    with (directory / "trials.jsonl").open("a") as trials:
        return _run(directory, trials, started=started, cpu_started=cpu_started)


def _run(directory: Path, trials: TextIO, *, started: float, cpu_started: float) -> Path:
    """
    Execute the original source-pinned worker with a caller-owned, immediately flushed event stream.
    """
    append(directory, "numerical", "Worker started; validating frozen inputs and source lock.")
    plan = json.loads((directory / "plan.json").read_text())
    pins = verify()
    selected = solver_method(plan.get("version"))
    contact_policy = ContactPolicy(
        plan.get("contact_measurement_policy", ContactPolicy.STRICT.value)
    )
    if selected.identifier != V2 and contact_policy is not ContactPolicy.STRICT:
        raise ValueError("Temporary contact measurement override is v2 gym only")
    if plan.get("sources") != pins:
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
        f"Inputs validated; first-pass optimization {'on' if settings.first_pass_optimization else 'off'}, smoothing {settings.smoothing_percent:g}%, terminal hardware {'on' if settings.terminal_hardware else 'off'}.",
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
        trials.write(json.dumps(event, allow_nan=False) + "\n")
        trials.flush()
        stage = str(event.get("stage") or "smoothing")
        now = perf_counter()
        if stage != last_stage or now - last_report >= 0.5:
            append(directory, stage, str(event.get("status") or "Working"))
            last_stage, last_report = stage, now

    method: dict[str, Any] = {
        "id": plan["result_id"],
        "label": selected.label,
        "source": selected.source,
        "procedure": selected.identifier,
        "settings": {
            **asdict(settings),
            "solver_version": selected.identifier,
            "path_rules": "material-fold equal lengths + pinch + no lateral bending + thick contact"
            + (" + finite terminal hardware" if settings.terminal_hardware else ""),
            "contact_measurement_policy": contact_policy.value,
        },
        "status": "unresolved",
        "detail": "No accepted route within the selected finite families/budget.",
        "rules": [],
    }
    stopped = None
    try:
        checkpoint()
        if selected.identifier == V2:
            result = solve_v2(
                targets,
                settings,
                checkpoint,
                record,
                native_point_tolerance_mm=plan.get("native_point_tolerance_mm"),
                contact_policy=contact_policy,
            )
        else:
            result = solve(targets, settings, checkpoint, record)
        metric_cache = material_error.cache_info()
        result.detail["material_metric_cache"] = {
            "hits": metric_cache.hits,
            "misses": metric_cache.misses,
            "maxsize": metric_cache.maxsize,
            "currsize": metric_cache.currsize,
        }
        write_document(directory / "numerical-result.json", result.detail)
        if result.route is None and result.inspection_route is not None:
            checkpoint()
            record(
                {
                    "stage": "rejected_result",
                    "status": "not_accepted",
                    "reason": result.detail.get(
                        "rejection_reason", "Final solver candidate was not accepted"
                    ),
                    "route": snapshot(result.inspection_route),
                }
            )
        if settings.terminal_hardware:
            hardware = result.detail["terminal_hardware"]
            append(
                directory,
                "terminal_hardware",
                f"Terminal checks: {hardware['checks']}; outcomes {hardware['outcomes']}; "
                f"CPU {hardware['cpu_seconds']:.4f}s. "
                + (
                    "Final route clears both proxies."
                    if result.route is not None
                    else "No route accepted with terminal hardware clearance."
                ),
            )
        append(
            directory,
            "numerical",
            "Geometry plan ready; writing route and checking display data."
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
                contact_warning=result.detail.get("contact_warning") is True,
            )
            warning = method["contact_warning"]
            if warning:
                method["detail"] = (
                    "Geometry retained under the temporary gym override: material/cap checks pass, contact measurement stopped at its pair limit and remains unmeasured. Native fidelity is pending."
                )
                append(directory, "warning", method["detail"])
            method["rules"] = [
                asdict(
                    RuleObservation(
                        "Numerical material/caps" if warning else "Numerical material/cap/contact",
                        "measured",
                        "Exact material primitives and fixed caps; contact is separately labelled. Cubic display is an approximation.",
                        result.detail["cap_error_mm"],
                        1e-7,
                    )
                )
            ]
            if warning:
                measurement = result.detail["contact_measurement"]
                method["rules"].append(
                    asdict(
                        RuleObservation(
                            "Contact measurement",
                            "unmeasured",
                            f"Temporary diagnostic: {measurement['reason']} Unresolved pieces: {measurement['unresolved_pieces']}. Geometry was retained without clearance certification.",
                            measurement["pairs_checked"],
                            1024,
                        )
                    )
                )
    except (ArithmeticError, OSError, RuntimeError, TimeoutError, TypeError, ValueError) as error:
        stopped = f"{type(error).__name__}: {error}"
        append(directory, "failed", stopped)
        method.update(status="stopped", detail=stopped)
    if not (directory / "route.json").exists():
        try:
            count = retain(method, directory / "trials.jsonl", directory, targets, checkpoint)
            if count:
                append(
                    directory,
                    "diagnostic",
                    f"Retained {count} rejected paths for visual inspection; no accepted native build.",
                )
        except (
            ArithmeticError,
            KeyError,
            OSError,
            RuntimeError,
            TimeoutError,
            TypeError,
            ValueError,
        ) as error:
            # Optional display must preserve the original numerical failure and native stop.
            append(
                directory,
                "diagnostic",
                f"Rejected geometry unavailable: {type(error).__name__}: {error}",
            )
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
