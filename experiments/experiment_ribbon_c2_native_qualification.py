"""
Run one frozen known-input native C2 cohort in the owned idle Fusion diagnostic design.

Requires live Fusion/adsk and the retained3202owner. This development-only entry
is outside normal test collection. No solve, fresh sampling or production change
occurs. One attempt per precommitted job, first problem stops, no automatic retry.
"""

from __future__ import annotations

import inspect
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from artifacts.verification.resume3114.memory import percentage, sample
from artifacts.verification.resume3142.disposition import NativeDisposition, classify
from artifacts.verification.resume3142.partial import retain_partial
from artifacts.verification.resume3201.bindings import Binding, installed
from artifacts.verification.resume3202 import runtime as historical
from artifacts.verification.resume3221.schedule import ReviewSchedule
from artifacts.verification.resume3226 import certified, integration, manifest
from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.gym.boundary import assess
from devtools.ribbon_analysis.gym.scene import Config
from experiments.experiment_ribbon_c2_runtime_capture import (
    compiled_arithmetic,
    idle_owner,
    required_state,
)

FOLDER = manifest.FOLDER


def write(path: Path, value: Any) -> None:
    """
    Preserve each receipt once without nonfinite JSON or overwriting prior outcomes.
    """
    with path.open("x") as stream:
        json.dump(value, stream, allow_nan=False, indent=2)


def compiled() -> dict[str, str]:
    """
    Verify effective native arithmetic and new bound/policy bodies without executing compiled files.
    """
    from artifacts.verification.resume3225 import flat, terminal
    from experiments.experiment_ribbon_locked_solver import accuracy

    checks = compiled_arithmetic()
    for module, names in (
        (certified, ("certified",)),
        (integration, ("c2_scope",)),
        (flat, ("Reference.prepare", "enclose")),
        (terminal, ("norm_lower", "Plane.point", "plane", "tail_error", "tail")),
        (
            accuracy,
            (
                "DimensionalAccuracy.__post_init__",
                "DimensionalAccuracy.accepts",
                "DimensionalAccuracy.observe",
            ),
        ),
    ):
        filename = module.__file__
        assert isinstance(filename, str)
        for name in names:
            function: Any = module
            for part in name.split("."):
                function = getattr(function, part)
            function = inspect.unwrap(function)
            assert historical.signature(function.__code__) == historical.signature(
                historical.compiled_body(Path(filename), name)
            ), name
            checks[module.__name__ + "." + name] = "exact_current_compiled_body"
    return checks


def preflight(started: float) -> None:
    """
    Verify current source, retained ownership, idle tools and reversible bindings without CAD changes.
    """
    from experiments.experiment_ribbon_locked_solver import native

    plan = manifest.read(FOLDER / "native-plan.json")
    budget = ReviewSchedule(started, 15).cohort_budget()
    manifest.verify(plan)
    ownership = idle_owner(plan)
    assert not hasattr(native, "_qualification_3226")
    checks = compiled()
    observations: dict[str, Any] = {}
    with integration.c2_scope(budget, observations, native.NativeScale.CONDITIONED):
        assert native.DISPLAY_ACCURACY.goal_mm == 0.01
        assert observations["translation_calls"] == 0
    assert checks == compiled()
    budget.check("native C2 readiness terminal")
    manifest.verify(plan)
    write(
        FOLDER / "preflight.json",
        {
            "ownership": ownership,
            "compiled": checks,
            "rss_kib": budget.memory(),
            "wall_seconds": time.perf_counter() - started,
            "native_attempts": 0,
        },
    )
    print({"ready": True, "compiled_checks": len(checks), "faces": ownership["faces"]})


def execute(started: float) -> None:
    """
    Build fixed complete inputs once, retaining stopped geometry and every unattempted tail.

    Imports, source checks, launch memory sampling, preparation, construction and
    audits share the caller's aggregate start and earlier estimated review.
    Only exactly archived owned output is retired. Successful builds receive
    named fidelity and separate boundary evidence, never a full physical pass.
    """
    # noinspection PyUnresolvedReferences
    import adsk.core

    # noinspection PyUnresolvedReferences
    import adsk.fusion

    from experiments.experiment_ribbon_locked_solver import lock, native

    plan = manifest.read(FOLDER / "native-plan.json")
    schedule = ReviewSchedule(started, plan["review_seconds"])
    cohort = schedule.cohort_budget()
    manifest.verify(plan)
    expected = idle_owner(plan)
    assert compiled() == manifest.read(FOLDER / "preflight.json")["compiled"]
    assert not hasattr(native, "_qualification_3226")
    write(
        FOLDER / "started.json",
        {"epoch_seconds": time.time(), "review_seconds": plan["review_seconds"]},
    )
    app = adsk.core.Application.get()
    root = adsk.fusion.Design.cast(app.activeProduct).rootComponent
    owner = required_state(native, "_qualification_3202")
    completed: list[dict[str, Any]] = []
    attempted_jobs: list[str] = []
    stop = None
    active_job = None
    try:
        for name in plan["jobs"]:
            active_job = name
            budget = schedule.case_budget()
            manifest.verify(plan)
            assert app.activeDocument.creationId == plan["document_id"]
            assert app.userInterface.activeCommand == "SelectCommand"
            historical.check_ownership(owner, expected)
            readings = sample(
                lambda: percentage(subprocess.check_output(["memory_pressure", "-Q"], text=True)),
                time.sleep,
            )
            job = FOLDER / name
            write(job / "memory-gate.json", {"actual_free_percent": readings, "minimum": 50})
            budget.check("actual native memory launch gate")
            if readings[-1] < 50:
                raise RuntimeError("Native launch stopped below50%actual system memory free")
            write(job / "retiring-owned.json", expected)
            owner.clear()
            if not completed:
                owner = native.NativeOwner(
                    plan["document_id"], construction_scale=native.NativeScale.CONDITIONED
                )
                native._qualification_3226 = owner
            assert not owner.has_geometry()
            before = tuple(root.occurrences)
            camera = app.activeViewport.camera
            observations: dict[str, Any] = {}

            def verify_sources() -> dict[str, str]:
                """
                Use the frozen new policy manifest, preserving the original selected solver sources.
                """
                return manifest.verify(plan)

            try:
                write(job / "native-started.json", {"epoch_seconds": time.time()})
                attempted_jobs.append(name)
                with installed((Binding(native, "verify", lock.verify, verify_sources),)):
                    with integration.c2_scope(budget, observations, native.NativeScale.CONDITIONED):
                        result = owner.build(job)
            finally:
                write(job / "positional-certificates.json", observations)
                if owner.has_geometry():
                    owner.displayed.component.bRepBodies.item(0).isLightBulbOn = False
                app.activeViewport.camera = camera
                app.activeViewport.refresh()
            partial = retain_partial(owner, before, tuple(root.occurrences), result, job)
            disposition = classify(result)
            ownership = (
                historical.ownership(owner) if partial is None and owner.has_geometry() else None
            )
            receipt = {
                "job": name,
                "status": result["status"],
                "native_attempted": result["native_attempted"],
                "built": result["built"],
                "fidelity_audited": result["fidelity_audited"],
                "ownership": ownership,
                "partial_ownership": partial,
                "case_seconds": budget.clock() - budget.started,
                "rss_kib": budget.memory(),
                "full_physical_audit": "unmeasured",
            }
            generation = result.get("generation_seconds")
            construction_seconds: float | None = None
            if isinstance(generation, (int, float)):
                construction_seconds = generation - float(observations["certificate_wall_seconds"])
            receipt["timing"] = {
                "generation_including_certificate_seconds": generation,
                "certificate_cpu_seconds": observations.get("certificate_cpu_seconds", 0.0),
                "certificate_wall_seconds": observations.get("certificate_wall_seconds", 0.0),
                "construction_excluding_certificate_seconds": construction_seconds,
                "scope": "Proof/audit excluded from matched construction benchmark",
            }
            write(job / "construction-receipt.json", receipt)
            completed.append(receipt)
            budget.check("native construction and named audit terminal")
            if disposition is NativeDisposition.STOPPED:
                raise RuntimeError(result["error"])
            assert ownership is not None
            expected = ownership
            body = owner.displayed.component.bRepBodies.item(0)
            box = body.preciseBoundingBox
            assert box is not None
            measured = assess(
                Config(**manifest.read(job / "plan.json")["gym"]["config"]),
                Vector3(box.minPoint.x * 10, box.minPoint.y * 10, box.minPoint.z * 10),
                Vector3(box.maxPoint.x * 10, box.maxPoint.y * 10, box.maxPoint.z * 10),
            )
            boundary = {
                "raw": measured.payload(),
                "accuracy_mm": 0.01,
                "accepted": measured.excess_mm <= 0.01,
            }
            write(job / "boundary-receipt.json", boundary)
            historical.check_ownership(owner, expected)
            manifest.verify(plan)
            budget.check("native case boundary terminal")
            if not boundary["accepted"]:
                raise RuntimeError("Separate native boundary stress gate failed")
        cohort.check("native C2 cohort terminal")
    except (AssertionError, ArithmeticError, ValueError, TypeError, OSError, RuntimeError) as error:
        stop = {"job": active_job, "error": repr(error)}
        write(FOLDER / "STOP.json", stop)
    write(
        FOLDER / "result.json",
        {
            "jobs": completed,
            "attempted_jobs": attempted_jobs,
            "unattempted": [name for name in plan["jobs"] if name not in attempted_jobs],
            "stop": stop,
            "wall_seconds": time.perf_counter() - started,
            "rss_kib": cohort.memory(),
            "new_solves": 0,
            "fresh_credit": 0,
            "full_physical_audits": 0,
        },
    )
    print(
        {"completed": len(completed), "stop": stop, "wall_seconds": time.perf_counter() - started}
    )
