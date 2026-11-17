"""
Freeze and execute one diagnostic complete gym layout with explicit finite work limits.
"""

from __future__ import annotations

import json
import pickle
import subprocess
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, process_time
from typing import Any
from uuid import UUID

from artifacts.verification.resume3114.memory import percentage
from artifacts.verification.resume3227 import manifest, memory
from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.gym.handoff import identity
from devtools.ribbon_analysis.gym.scene import Scene
from experiments.experiment_ribbon_complete.ending_material import audit as audit_endings
from experiments.experiment_ribbon_complete.evaluation import witness_finding
from experiments.experiment_ribbon_complete.execution import RibbonPlan, TrunkConstructor, prepare
from experiments.experiment_ribbon_complete.material_witnesses import WitnessWork
from experiments.experiment_ribbon_complete.material_witnesses import audit as audit_witnesses
from experiments.experiment_ribbon_complete.profile_transition import TransitionTiming
from experiments.experiment_ribbon_complete.trunk_material import TrunkMetricWork
from experiments.experiment_ribbon_locked_solver.settings import Settings

from . import lock
from .fixture import author
from .material_report import measure as measure_material

SETTINGS = Settings(1, False, True, True)
LIMITS = {
    "seconds": 10,
    "witness_calls": 1024,
    "intervals_per_span": 16,
    "metric_spans": 16384,
    "rss_kib": 4194304,
}


def inspect_material(
    plan: RibbonPlan,
    witnesses: WitnessWork,
    metrics: TrunkMetricWork,
    record: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    """
    Measure the rigorous combined bound first, retaining rejection witnesses when inconclusive.

    A complete source-owned upper bound already excludes the violations targeted
    by chord witnesses on those same paths. Skip that redundant rejection test
    only for a certified bound. Missing geometry, unresolved bounds and exceptions
    cannot acquire this exemption. Every stage shares the caller's existing work
    allocations, watchdog and memory checkpoint; no physical pass is returned.
    """
    wall, cpu = perf_counter(), process_time()
    endings = audit_endings(plan, metrics.checkpoint)
    planned = measure_material(plan, metrics)
    status = "trunk_unresolved" if plan.trunk.route is None else "unqualified"
    witness: dict[str, Any] = {
        "stage": "complete_material_witness",
        "status": "not_attempted",
        "reason": "trunk_unresolved"
        if plan.trunk.route is None
        else "certified_combined_upper_bound",
        "findings": [],
    }
    if plan.trunk.route is not None and planned["status"] != "within_planned_increment_bound":
        measured = audit_witnesses(plan, LIMITS["intervals_per_span"], witnesses)
        if measured.status == "violated":
            status = "planned_material_violation"
        witness.update(
            status=measured.status,
            reason="combined_upper_bound_inconclusive",
            findings=[witness_finding(row) for row in measured.findings],
        )
    record({**witness, "witness_calls": witnesses.calls})
    record({"stage": "planned_material_increment_bound", **planned})
    metrics.checkpoint()
    outstanding = (
        tuple(
            dict.fromkeys(
                (
                    "trunk_material_metrics",
                    "junction_material_correspondence",
                    "native_material_correspondence",
                )
                + tuple(gate for branch in plan.branches for gate in branch.outstanding)
            )
        )
        if plan.trunk.route is not None
        else ("complete_geometry",)
    )
    return {
        "status": status,
        "ending_material": endings,
        "planned_material": planned,
        "outstanding": outstanding,
        "audit_wall_seconds": perf_counter() - wall,
        "audit_cpu_seconds": process_time() - cpu,
    }


def freeze(scene: Scene, namespace: UUID, directory: Path, tolerance_mm: float) -> Path:
    """
    Write all complete targets and their hash before one explicitly requested diagnostic run.

    One-diameter extensions and no descendants are an input fixture, not a solver
    repair. All manual runs are diagnostic, with no novelty or qualification credit.
    This development-only trusted pickle is loaded only after its hash and runtime
    sources match. Repeated layouts get separate histories; no old outcome is erased.
    """
    if type(tolerance_mm) not in (int, float) or not 0 < tolerance_mm < 0.01:
        raise ValueError("Supply the current positive Fusion point tolerance below0.01mm")
    pins = lock.capture()
    source = author(scene, namespace)
    directory.mkdir(parents=True, exist_ok=False)
    targets = directory / "targets.pkl"
    with targets.open("xb") as stream:
        pickle.dump(source, stream, protocol=4)
    plan = {
        "scope": "manual complete gym diagnostic; no fresh coverage or native qualification",
        "gym": scene.payload(),
        "layout_id": identity(scene.payload()),
        "namespace": str(namespace),
        "targets_sha256": manifest.digest(targets),
        "sources": pins,
        "limits": LIMITS,
        "settings": asdict(SETTINGS),
        "native_point_tolerance_mm": tolerance_mm,
        "fixture": "both ends; one diameter extension; all lanes; no descendants",
        "candidate": "unchanged3338/3346 frozen3185 context bundle",
        "new_native_calls": 0,
        "generalization_credit": False,
    }
    with (directory / "plan.json").open("x") as stream:
        json.dump(plan, stream, indent=2, allow_nan=False)
    return directory / "plan.json"


def run(directory: Path, constructor: TrunkConstructor | None = None) -> Path:
    """
    Execute once and retain flushed prefix evidence on a known resource or geometry stop.

    An injected constructor supports analytical boundary tests; normal execution
    uses the unchanged candidate adapter. This function never starts native work,
    retries, renews limits or returns a physical pass. Launch/source/input failures
    propagate before a numerical operation; in-flight failures retain their report.
    """
    plan = manifest.read(directory / "plan.json")
    if plan["limits"] != LIMITS or plan["settings"] != asdict(SETTINGS):
        raise ValueError("Complete gym execution policy differs from the frozen policy")
    lock.verify(plan["sources"])
    targets_path = directory / "targets.pkl"
    if manifest.digest(targets_path) != plan["targets_sha256"]:
        raise RuntimeError("Complete gym frozen input drift")
    source = pickle.loads(targets_path.read_bytes())
    with (directory / "started.json").open("x") as stream:
        json.dump({"status": "one diagnostic attempt started"}, stream)

    def free() -> int:
        """
        Read actual system reserve without changing host settings.
        """
        return percentage(subprocess.check_output(["/usr/bin/memory_pressure", "-Q"], text=True))

    guard = memory.Headroom(10, free)
    budget = NativeBudget(
        memory=guard.memory,
        maximum_seconds=LIMITS["seconds"],
        maximum_rss_kib=LIMITS["rss_kib"],
    )
    cpu = process_time()
    last_sources = budget.started

    def check() -> None:
        """
        Enforce one aggregate clock, memory reserve, cancellation and source identity.
        """
        nonlocal last_sources
        if (directory / "cancel").exists():
            raise RuntimeError("Complete gym numerical work cancelled")
        budget.check("complete gym numerical diagnostic")
        if perf_counter() - last_sources >= 0.5:
            lock.verify(plan["sources"])
            last_sources = perf_counter()

    work = WitnessWork(LIMITS["witness_calls"], check)
    metrics = TrunkMetricWork(LIMITS["metric_spans"], check)
    report: dict[str, Any] = {
        "layout_id": plan["layout_id"],
        "status": "stopped",
        "fully_qualified_complete_ribbons": 0,
        "native_calls": 0,
        "generalization_credit": False,
        "planned_material": {"status": "unattempted"},
    }
    with (directory / "events.jsonl").open("x") as events:

        def record(event: dict[str, Any]) -> None:
            """
            Flush completed stages before advancing so a stop cannot discard the prefix.
            """
            events.write(json.dumps(event, allow_nan=False) + "\n")
            events.flush()

        try:
            check()
            if budget.memory() >= 3984588:
                raise RuntimeError("Complete gym lacks3.8GiB launch headroom")
            if constructor is None:
                from functools import partial

                from .candidate import construct

                constructor = partial(
                    construct,
                    settings=SETTINGS,
                    native_point_tolerance_mm=plan["native_point_tolerance_mm"],
                )
            prepared = prepare(
                source,
                constructor,
                check,
                record,
                timing=TransitionTiming.LOW_ENERGY,
            )
            check()
            lock.verify(plan["sources"])
            with (directory / "complete-plan.pkl").open("xb") as stream:
                pickle.dump(prepared, stream, protocol=4)
            report.update(
                prepared_branches=len(prepared.branches),
                unattempted_route_ids=[str(value) for value in prepared.unattempted_route_ids],
                preparation_cpu_seconds=prepared.cpu_seconds,
                preparation_wall_seconds=prepared.wall_seconds,
            )
            report["planned_material"] = {"status": "started"}
            inspection = inspect_material(prepared, work, metrics, record)
            check()
            report.update(inspection)
        except (ArithmeticError, OSError, RuntimeError, TypeError, ValueError) as error:
            # Fail-closed diagnostic receipt: preserve the stop, never retry or classify as pass.
            report["error"] = f"{type(error).__name__}: {error}"
            if report["planned_material"]["status"] == "started":
                report["planned_material"] = {"status": "stopped", "error": report["error"]}
        report.update(
            wall_seconds=perf_counter() - budget.started,
            cpu_seconds=process_time() - cpu,
            witness_calls=work.calls,
            metric_spans=metrics.spans,
            minimum_system_free_percent=guard.minimum_observed_percent,
            resource_stop=budget.stopped,
        )
    destination = directory / "result.json"
    with destination.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    return destination
