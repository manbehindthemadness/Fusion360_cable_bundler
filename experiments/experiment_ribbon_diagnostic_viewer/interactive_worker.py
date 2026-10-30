"""
Run one frozen optional-procedure plan in a fresh project SDK process, without Fusion.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from devtools.ribbon_analysis import budget
from devtools.ribbon_analysis.contracts import RibbonPath
from devtools.ribbon_analysis.gym.handoff import identity
from devtools.ribbon_analysis.inspection.archive import (
    SCHEMA,
    RuleObservation,
    canonical,
    snapshot_payload,
    write_document,
)
from devtools.ribbon_analysis.inspection.capture import CaptureLimits, SearchRecorder, search_stage
from devtools.ribbon_analysis.inspection.geometry import freeze_path
from devtools.ribbon_analysis.inspection.measurements import observations
from devtools.ribbon_analysis.inspection.session import Session
from experiments.experiment_ribbon_cap_transition.constraint_policy import configured, scope
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from . import ablation, adapters, procedures


class SchedulingStop(RuntimeError):
    """
    Latch resource, cancellation and source stops before scheduling another procedure.
    """


class ExcerptComplete(RuntimeError):
    """
    End a declared search prefix normally; this never signifies a completed solve.
    """


def _search(
    identifier: str,
    case: EndpointCase,
    settings: dict[str, Any],
    recorder: SearchRecorder,
    checkpoint: Callable[[], None],
) -> tuple[RibbonPath | None, dict[str, Any]]:
    """
    Observe a fixed search prefix while keeping resource failures exceptional.
    """

    def observe() -> None:
        """
        Check hard limits first, then recognize declared excerpt completion.
        """
        checkpoint()
        if settings["excerpt"] and recorder.count >= settings["excerpt"]:
            raise ExcerptComplete

    recorder.checkpoint = observe
    try:
        with recorder.recording(), search_stage(identifier):
            path, metrics = adapters.execute(identifier, case, settings, observe)
    except ExcerptComplete:
        return None, {"procedure_completed": False, "excerpt_paths": recorder.count}
    return path, dict(metrics, procedure_completed=True)


def _progress(directory: Path, payload: dict[str, Any]) -> None:
    """
    Replace a transient progress indicator; immutable plans/results stay separate.
    """
    temporary = directory / "progress.tmp"
    temporary.write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")
    os.replace(temporary, directory / "progress.json")


def run(directory: Path) -> Path:
    """
    Retain all outcomes and complete transported paths, including interrupted work.

    Unexpected failures deliberately fail soft only to archive an error and skip
    remaining procedures; they never continue as an accepted geometry result.
    """
    plan = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
    session = Session(directory / "input.json")
    if plan.get("gym_id") != (identity(session.gym) if session.gym is not None else None):
        raise ValueError("Worker inputs disagree with the planned gym identity.")
    requested = procedures.selections(plan["procedures"])
    work = ablation.workloads(requested, plan.get("comparison"))
    targets = session.targets
    case = EndpointCase(
        targets.name,
        targets.start,
        targets.end,
        targets.start_tangent,
        targets.end_tangent,
        targets.start_width,
        targets.end_width,
        targets.lines,
        targets.diameter_mm,
    )
    labels = {entry.identifier: entry for entry in procedures.CATALOG}
    methods: list[dict[str, Any]] = []
    started = perf_counter()
    stopped: str | None = None
    maximum_rss = 0
    for index, selection in enumerate(work):
        identifier, settings = selection["id"], selection["settings"]
        role = selection["role"]
        suffix = "" if role == "normal" else ":" + role
        name = f"{plan['run_id']}:{identifier}{suffix}"
        disabled = selection["disabled_rules"]
        item: dict[str, Any] = {
            "id": name,
            "label": f"{labels[identifier].label}{' / ' + role if suffix else ''} · {plan['run_id'][-8:]}",
            "procedure": identifier,
            "disabled_rules": disabled,
            "comparison": {
                "role": role,
                "baseline": f"{plan['run_id']}:{identifier}:baseline",
                "origin": plan["comparison"]["origin"],
            }
            if suffix
            else None,
            "source": str(directory / "plan.json") + " / " + identifier,
            "status": "not_run",
            "detail": "Not scheduled after a latched stop.",
            "rules": [
                asdict(
                    RuleObservation(
                        "Physical acceptance",
                        "unmeasured",
                        "Numerical procedure only; no native solid construction or complete physical audit.",
                    )
                )
            ],
        }
        methods.append(item)
        if stopped is not None:
            item["detail"] = "Not run after: " + stopped
            continue
        method_started = perf_counter()
        last_memory = -1.0
        last_progress = -1.0
        recorder: SearchRecorder | None = None

        def checkpoint(
            seconds: float = float(settings["seconds"]),
            began: float = method_started,
            procedure: str = identifier,
            ordinal: int = index,
        ) -> None:
            """
            Bound numerical work while servicing cancellation and source checks.
            """
            nonlocal last_memory, last_progress, maximum_rss
            now = perf_counter()
            if (directory / "cancel").exists():
                raise SchedulingStop("Cancelled at a numerical checkpoint.")
            if now - began >= seconds or now - started >= 120:
                raise SchedulingStop(f"Time scheduling cap in {procedure}.")
            if now - last_memory >= 0.25:
                last_memory = now
                rss = budget.resident_kib()
                maximum_rss = max(maximum_rss, rss)
                if rss >= 4 * 1024 * 1024:
                    raise SchedulingStop("4GiB worker RSS ceiling.")
            if now - last_progress >= 0.8:
                last_progress = now
                if procedures.source_pins() != plan["sources"]:
                    raise SchedulingStop("Source fingerprints changed after the plan.")
                if (
                    sum(history_file.stat().st_size for history_file in directory.glob("*.jsonl"))
                    >= 256 * 1024 * 1024
                ):
                    raise SchedulingStop("256MiB aggregate search recording cap.")
                _progress(
                    directory,
                    {
                        "status": "running",
                        "procedure": procedure,
                        "completed": ordinal,
                        "total": len(work),
                        "elapsed_seconds": now - started,
                    },
                )

        try:
            checkpoint()
            if budget.resident_kib() >= int(3.8 * 1024 * 1024):
                raise SchedulingStop("3.8GiB worker launch headroom.")
            history = directory / f"{identifier}{'-' + role if suffix else ''}.jsonl"
            active_recorder = SearchRecorder(
                history,
                identifier,
                checkpoint,
                CaptureLimits(
                    paths=settings["paths"], control_points=2_000_000, bytes=64 * 1024 * 1024
                ),
            )
            recorder = active_recorder
            item["history"] = history.name
            with scope(configured(disabled, settings)):
                path, metrics = _search(identifier, case, settings, active_recorder, checkpoint)
            canonical(metrics)
            if procedures.source_pins() != plan["sources"]:
                raise SchedulingStop("Source fingerprints changed during the procedure.")
            checkpoint()
            item.update(
                status="unresolved" if metrics["procedure_completed"] else "recorded",
                detail="Numerical procedure completed. Physical acceptance remains unresolved."
                if metrics["procedure_completed"]
                else f"Search excerpt: first {active_recorder.count} complete transports. Procedure unfinished; last path may be a seed, probe or rejected trial.",
                metrics=metrics,
            )
            if disabled:
                item["detail"] += (
                    " Disabled in search: "
                    + ", ".join(disabled)
                    + ". Measurements still use the full reference rules."
                )
            if path is not None:
                snapshot = freeze_path(name, path, intervals=512, sections=33)
                item["snapshot"] = snapshot_payload(snapshot)
                item["rules"] = [
                    asdict(rule)
                    for rule in observations(
                        snapshot,
                        targets,
                        plan["minimum_radius_mm"],
                        pinch_percent=settings["pinch_percent"]
                        if settings.get("bend_model") == "pinch percent"
                        else None,
                    )
                ]
            elif active_recorder.last is not None:
                item["snapshot"] = snapshot_payload(active_recorder.last)
                item["rules"] = [
                    asdict(rule)
                    for rule in observations(
                        active_recorder.last,
                        targets,
                        plan["minimum_radius_mm"],
                        pinch_percent=settings["pinch_percent"]
                        if settings.get("bend_model") == "pinch percent"
                        else None,
                    )
                ]
            checkpoint()
        except Exception as error:
            # Preserve unexpected implementation errors as stopped evidence, never a pass.
            stopped = f"{type(error).__name__}: {error}"
            item.update(status="stopped", detail=stopped, error_traceback=traceback.format_exc())
            if recorder is not None and recorder.last is not None:
                item["snapshot"] = snapshot_payload(recorder.last)
                item["rules"] = [
                    asdict(
                        RuleObservation(
                            "Interrupted numerical search",
                            "unmeasured",
                            "Last completed transport may be a probe or rejected trial, not a fitted result.",
                        )
                    )
                ]
        finally:
            item["seconds"] = perf_counter() - method_started
            item["settings"] = settings
            item["recording"] = {
                "paths": recorder.count if recorder else 0,
                "capture_seconds_subset": recorder.seconds if recorder else 0,
            }
    result = {
        "schema": SCHEMA,
        "targets": asdict(targets),
        "solvers": methods,
        "sources": plan["sources"],
        "plan": "plan.json",
        "seconds": perf_counter() - started,
        "maximum_rss_kib": maximum_rss,
        "stopped": stopped,
        "native_solid_attempts": 0,
        "independent_configurations": 1,
    }
    if session.gym is not None:
        result["gym"] = session.gym
    destination = directory / "manifest.json"
    write_document(destination, result)
    _progress(
        directory,
        {
            "status": "stopped" if stopped else "completed",
            "detail": stopped or "Results recorded; physical acceptance unresolved.",
            "total": len(work),
            "elapsed_seconds": perf_counter() - started,
        },
    )
    return destination


if __name__ == "__main__":
    run(Path(sys.argv[1]))
