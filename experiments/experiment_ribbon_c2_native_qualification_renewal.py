"""
Renew the fixed native C2 cohort with explicit90%-used system memory safeguards.

Requires live Fusion/adsk and the exact retained3202owner. No solver or fresh
sampling runs. Historical stopped scopes remain immutable; all temporary aliases
restore. The headroom guard supplements the4GiB process cap and shared deadlines.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from artifacts.verification.resume3114.memory import percentage
from artifacts.verification.resume3142.disposition import NativeDisposition, classify
from artifacts.verification.resume3142.partial import retain_partial
from artifacts.verification.resume3201.bindings import Binding, installed
from artifacts.verification.resume3202 import runtime as historical
from artifacts.verification.resume3221.schedule import ReviewSchedule
from artifacts.verification.resume3226 import integration
from artifacts.verification.resume3226 import manifest as prior_manifest
from artifacts.verification.resume3227 import manifest, memory
from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.gym.boundary import assess
from devtools.ribbon_analysis.gym.scene import Config
from experiments import experiment_ribbon_c2_native_qualification as prior
from experiments.experiment_ribbon_c2_native_qualification import compiled as prior_compiled
from experiments.experiment_ribbon_c2_native_qualification import write
from experiments.experiment_ribbon_c2_runtime_capture import idle_owner, required_state

FOLDER = manifest.FOLDER


def read_free() -> int:
    """
    Read the same actual host command at launch and during checkpointed work.
    """
    output = subprocess.check_output(["/usr/bin/memory_pressure", "-Q"], text=True)
    return percentage(output)


def compiled() -> dict[str, str]:
    """
    Reuse83original body checks and compare the new live headroom operations.
    """
    checks = prior_compiled()
    bodies: dict[str, Any] = {
        "Headroom.__post_init__": memory.Headroom.__post_init__,
        "Headroom.memory": memory.Headroom.memory,
        "checked_read": memory.checked_read,
        "launch_samples": memory.launch_samples,
    }
    for name, body in bodies.items():
        code = historical.compiled_body(Path(memory.__file__), name)
        assert historical.signature(body.__code__) == historical.signature(code)
        checks[name] = "exact_current_compiled_body"
    return checks


def preflight(started: float) -> None:
    """
    Reuse immutable readiness checks with an explicitly scoped current policy manifest.
    """
    from experiments.experiment_ribbon_locked_solver import native

    assert not hasattr(native, "_qualification_3227")
    with installed(
        (
            Binding(prior, "FOLDER", prior_manifest.FOLDER, FOLDER),
            Binding(prior, "manifest", prior_manifest, manifest),
            Binding(prior, "compiled", prior_compiled, compiled),
        )
    ):
        prior.preflight(started)


def restore_display(
    owner: Any, job: Path, observations: dict[str, Any], app: Any, camera: Any
) -> None:
    """
    Preserve certificates and restore the camera while hiding only this owned output.
    """
    write(job / "positional-certificates.json", observations)
    if owner.has_geometry():
        owner.displayed.component.bRepBodies.item(0).isLightBulbOn = False
    app.activeViewport.camera = camera
    app.activeViewport.refresh()


def build_once(
    owner: Any, job: Path, budget: NativeBudget, plan: dict[str, Any], app: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Enter complete certificate/audit bindings for exactly one original owner build.
    """
    from experiments.experiment_ribbon_locked_solver import lock, native

    def current_sources() -> dict[str, str]:
        """
        Verify both user policy revisions and unchanged selected geometry/solver sources.
        """
        return manifest.verify(plan)

    observations: dict[str, Any] = {}
    camera = app.activeViewport.camera
    try:
        with installed((Binding(native, "verify", lock.verify, current_sources),)):
            with integration.c2_scope(budget, observations, native.NativeScale.CONDITIONED):
                result = owner.build(job)
    finally:
        restore_display(owner, job, observations, app, camera)
    return result, observations


def construction_receipt(
    name: str,
    owner: Any,
    before: tuple[Any, ...],
    after: tuple[Any, ...],
    result: dict[str, Any],
    observations: dict[str, Any],
    budget: NativeBudget,
) -> dict[str, Any]:
    """
    Preserve native disposition, exact ownership and proof-separated timing without a physical claim.
    """
    partial = retain_partial(owner, before, after, result, FOLDER / name)
    ownership = historical.ownership(owner) if partial is None and owner.has_geometry() else None
    generation = result.get("generation_seconds")
    measured = None
    if isinstance(generation, (int, float)):
        measured = generation - float(observations["certificate_wall_seconds"])
    counters = {
        key: result[key] for key in ("status", "native_attempted", "built", "fidelity_audited")
    }
    return {
        "job": name,
        **counters,
        "ownership": ownership,
        "partial_ownership": partial,
        "case_seconds": budget.clock() - budget.started,
        "rss_kib": budget.memory(),
        "full_physical_audit": "unmeasured",
        "timing": {
            "generation_including_certificate_seconds": generation,
            "certificate_cpu_seconds": observations.get("certificate_cpu_seconds", 0.0),
            "certificate_wall_seconds": observations.get("certificate_wall_seconds", 0.0),
            "construction_excluding_certificate_seconds": measured,
        },
    }


def boundary_receipt(owner: Any, job: Path) -> dict[str, Any]:
    """
    Record the separate whole-body stress-box measurement under0.01mm dimensional policy.
    """
    box = owner.displayed.component.bRepBodies.item(0).preciseBoundingBox
    if box is None:
        raise RuntimeError("Native precise bounds unavailable")
    points = tuple(Vector3(p.x * 10, p.y * 10, p.z * 10) for p in (box.minPoint, box.maxPoint))
    config = Config(**manifest.read(job / "plan.json")["gym"]["config"])
    measurement = assess(config, *points)
    return {
        "raw": measurement.payload(),
        "accuracy_mm": 0.01,
        "accepted": measurement.excess_mm <= 0.01,
    }


def retire_owned(owner: Any, expected: dict[str, Any], job: Path) -> None:
    """
    Archive and retire only the exact currently verified diagnostic output.
    """
    historical.check_ownership(owner, expected)
    write(job / "retiring-owned.json", expected)
    owner.clear()


def new_owner(document_id: str) -> Any:
    """
    Create this renewal's independent owner without changing the prior stopped scope.
    """
    from experiments.experiment_ribbon_locked_solver import native

    owner = native.NativeOwner(document_id, construction_scale=native.NativeScale.CONDITIONED)
    native._qualification_3227 = owner
    return owner


def execute(started: float) -> None:
    """
    Run the frozen three complete inputs once with launch and ongoing system headroom checks.

    A blocking kernel call cannot be interrupted by a Python checkpoint; bounded
    inputs, process cap, reserve and earliest deadline govern every subsequent
    operation. No OS setting is changed and no unrelated process is terminated.
    """
    # noinspection PyUnresolvedReferences
    import adsk.core

    # noinspection PyUnresolvedReferences
    import adsk.fusion

    from experiments.experiment_ribbon_locked_solver import lock, native

    plan = manifest.read(FOLDER / "native-plan.json")
    schedule = ReviewSchedule(started, plan["review_seconds"])
    guard = memory.Headroom(plan["minimum_system_free_percent"], read_free)
    cohort = schedule.cohort_budget(memory=guard.memory)
    manifest.verify(plan)
    expected = idle_owner(plan)
    assert compiled() == manifest.read(FOLDER / "preflight.json")["compiled"]
    assert not hasattr(native, "_qualification_3227")
    write(
        FOLDER / "started.json",
        {
            "epoch_seconds": time.time(),
            "memory_policy": "90%used/10%free",
            "review_seconds": plan["review_seconds"],
        },
    )
    completed: list[dict[str, Any]] = []
    attempted: list[str] = []
    stop = None
    active_job = None
    app = adsk.core.Application.get()
    root = adsk.fusion.Design.cast(app.activeProduct).rootComponent
    owner = required_state(native, "_qualification_3202")
    try:
        for name in plan["jobs"]:
            active_job = name
            job = FOLDER / name
            budget = schedule.case_budget(memory=guard.memory)
            manifest.verify(plan)
            historical.check_ownership(owner, expected)
            assert app.activeDocument.creationId == plan["document_id"]
            assert (
                app.userInterface.activeCommand == "SelectCommand" and native.verify is lock.verify
            )
            readings = memory.launch_samples(guard.minimum_free_percent, read_free, time.sleep)
            write(
                job / "memory-gate.json",
                {"actual_free_percent": readings, "minimum": guard.minimum_free_percent},
            )
            budget.check("native system headroom launch")
            if readings[-1] < guard.minimum_free_percent:
                raise RuntimeError("Insufficient authorized native memory reserve")
            retire_owned(owner, expected, job)
            if not completed:
                owner = new_owner(plan["document_id"])
            assert not owner.has_geometry()
            before = tuple(root.occurrences)
            write(job / "native-started.json", {"epoch_seconds": time.time()})
            attempted.append(name)
            result, observations = build_once(owner, job, budget, plan, app)
            receipt = construction_receipt(
                name, owner, before, tuple(root.occurrences), result, observations, budget
            )
            write(job / "construction-receipt.json", receipt)
            completed.append(receipt)
            budget.check("native build and named audit terminal")
            if classify(result) is NativeDisposition.STOPPED:
                raise RuntimeError(result["error"])
            expected = receipt["ownership"]
            assert expected is not None
            boundary = boundary_receipt(owner, job)
            write(job / "boundary-receipt.json", boundary)
            historical.check_ownership(owner, expected)
            budget.check("native case terminal")
            if not boundary["accepted"]:
                raise RuntimeError("Separate native boundary stress failure")
        manifest.verify(plan)
        cohort.check("native cohort terminal")
    except (AssertionError, ArithmeticError, ValueError, TypeError, OSError, RuntimeError) as error:
        stop = {"job": active_job, "error": repr(error)}
        write(FOLDER / "STOP.json", stop)
    report = {
        "jobs": completed,
        "attempted_jobs": attempted,
        "unattempted": [name for name in plan["jobs"] if name not in attempted],
        "stop": stop,
        "wall_seconds": time.perf_counter() - started,
        "rss_kib": cohort.memory(),
        "system_memory_samples": guard.samples,
        "minimum_system_free_percent_observed": guard.minimum_observed_percent,
        "new_solves": 0,
        "fresh_credit": 0,
        "full_physical_audits": 0,
    }
    write(FOLDER / "result.json", report)
    print({"completed": len(completed), "stop": stop, "wall_seconds": report["wall_seconds"]})
