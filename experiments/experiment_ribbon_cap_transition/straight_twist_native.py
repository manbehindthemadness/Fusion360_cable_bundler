"""
Run the approved three-variant planar twist pilot in one new owned Fusion document.

Requires an idle Fusion command. Retains all existing documents, stops at the first
failure, and checkpoints partial evidence without retry or geometry repair. Native
calls cannot be cancelled by these between-operation scheduling limits.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from time import perf_counter
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT

from .native import _write
from .native_budget import NativeBudget
from .straight_twist import TWISTS_DEGREES, rate_metrics, section_arcs, twist_frames

NAME = "Straight ribbon - planar twist rate pilot"


def _hashes() -> dict[str, str]:
    """
    Fingerprint authoring, scheduling and governing rules before any document write.
    """
    paths = (
        Path(__file__),
        Path(__file__).with_name("straight_twist.py"),
        Path(__file__).with_name("native_budget.py"),
        PROJECT_ROOT / "experiment_testing_rules.txt",
        PROJECT_ROOT / "rollback_end_loft_notes.txt",
    )
    return {
        str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def _sections(
    component: adsk.fusion.Component, degrees: float, budget: NativeBudget
) -> list[adsk.fusion.Profile]:
    """
    Create exactly 32 original planar contours without rails, endings or flexing.
    """
    profiles = []
    for number, frame in enumerate(twist_frames(degrees), 1):
        budget.check(f"section {number}")
        plane_input = component.constructionPlanes.createInput()
        if not plane_input.setByOffset(
            component.xYConstructionPlane,
            adsk.core.ValueInput.createByReal(frame.origin.z / 10),
        ):
            raise RuntimeError("Section plane setup failed.")
        plane = component.constructionPlanes.add(plane_input)
        plane.isLightBulbOn = False
        sketch = component.sketches.add(plane)
        sketch.name = f"Original planar section {number:02d}"
        for arc in section_arcs():
            points = []
            for x, y in arc:
                model = adsk.core.Point3D.create(
                    (frame.width.x * x + frame.thickness.x * y) / 10,
                    (frame.width.y * x + frame.thickness.y * y) / 10,
                    frame.origin.z / 10,
                )
                points.append(sketch.modelToSketchSpace(model))
            sketch.sketchCurves.sketchArcs.addByThreePoints(*points)
        if sketch.profiles.count != 1 or sketch.sketchCurves.sketchArcs.count != 40:
            raise RuntimeError("Original section topology guard failed.")
        profiles.append(sketch.profiles.item(0))
        sketch.isLightBulbOn = False
    return profiles


def run(_context: object) -> None:
    """
    Attempt 0/180/360 degrees once each, with 60s/case, 300s/batch and 2GiB RSS.

    Exceptions are captured intentionally to preserve partial native geometry in
    the MCP transaction. Harness errors are distinct from kernel failures; later
    cases remain explicitly unattempted. Positive construction is not compliance.
    """
    app = adsk.core.Application.get()
    if app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("An active Fusion command prevents this diagnostic.")
    if any(app.documents.item(i).name == NAME for i in range(app.documents.count)):
        raise RuntimeError("An existing pilot document must not be overwritten.")
    run_dir = (
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/straight_twist" / uuid4().hex
    )
    run_dir.mkdir(parents=True)
    fingerprints = _hashes()
    cases: list[dict[str, object]] = [
        {
            "id": f"straight_quintic_{degrees:g}",
            "parent": "straight_57mm_planar",
            "twist_degrees": degrees,
            "metrics": rate_metrics(degrees),
            "native_prediction": "unknown",
            "numerical": "fixed authoring evaluated; centerline curvature zero; twist policy excepted diagnostically",
            "status": "not attempted",
            "audit": "not attempted",
        }
        for degrees in TWISTS_DEGREES
    ]
    plan: dict[str, object] = {
        "question": "Does twist alone fail near the observed original rate?",
        "procedure": "straight-planar-original-40arc-quintic-v1",
        "centerline": "fixed straight Z, 57mm; no search or rerouting",
        "dimensions": "19 conductors at 1.5mm pitch; 32 sections; actual width28.8mm",
        "coverage": "one development route family, three twist variants; not complete ribbons",
        "exclusions": "no endings, sphere, flex, rails, strain/pitch/length/native skin audits",
        "budgets": {
            "attempts": 3,
            "seconds_per_case": 60,
            "seconds_batch": 300,
            "rss_kib": 2097152,
        },
        "stop": "first failure or scheduling limit; no retries or tuning",
        "fingerprints": fingerprints,
        "cases": cases,
    }
    _write(run_dir / "plan.json", plan)
    batch = NativeBudget(maximum_seconds=300)
    batch.check("new diagnostic document")
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    document.name = NAME
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("Diagnostic design is unavailable.")
    stopped: str | None = None
    for index, (degrees, case) in enumerate(zip(TWISTS_DEGREES, cases)):
        if stopped is not None:
            case["not_attempted_reason"] = stopped
            continue
        case_budget = NativeBudget(maximum_seconds=60)
        stage = "preparation"
        started = perf_counter()
        try:
            if _hashes() != fingerprints:
                raise RuntimeError("Frozen source/rule fingerprints changed.")
            batch.check(f"case {degrees:g}")
            case_budget.check("component")
            placement = adsk.core.Matrix3D.create()
            placement.translation = adsk.core.Vector3D.create(index * 4.5, 0, 0)
            occurrence = design.rootComponent.occurrences.addNewComponent(placement)
            component = occurrence.component
            component.name = f"Planar {degrees:g} deg - preparing"
            profiles = _sections(component, degrees, case_budget)
            case["preparation_seconds"] = perf_counter() - started
            batch.check("native trunk")
            case_budget.check("native trunk")
            loft = component.features.loftFeatures.createInput(
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )
            loft.isSolid = True
            for profile in profiles:
                loft.loftSections.add(profile)
            stage = "native"
            case["native_attempted"] = True
            native_started = perf_counter()
            try:
                feature = component.features.loftFeatures.add(loft)
            finally:
                case["native_seconds"] = perf_counter() - native_started
            bodies = [feature.bodies.item(i) for i in range(feature.bodies.count)]
            case["bodies"] = [{"solid": body.isSolid, "volume_cm3": body.volume} for body in bodies]
            if len(bodies) != 1 or not bodies[0].isSolid or bodies[0].volume <= 0:
                raise RuntimeError("Loft did not return one positive-volume solid.")
            bodies[0].name = f"Original planar {degrees:g} degree trunk"
            component.name = f"Planar {degrees:g} deg - BUILT (unaudited)"
            case["status"] = "built"
            stage = "post-build scheduling"
            case_budget.check("after trunk")
            batch.check("after case")
        except Exception as error:
            if case["status"] != "built":
                case["status"] = (
                    "kernel/output failure" if stage == "native" else "harness or scheduling stop"
                )
            case["error"] = str(error)
            stopped = f"Stopped at {case['id']}: {error}"
        finally:
            case["case_seconds"] = perf_counter() - started
            case["memory_samples"] = case_budget.samples
            _write(
                run_dir / "report.json",
                {**plan, "stop_reason": stopped, "batch_seconds": perf_counter() - batch.started},
            )
    _write(
        run_dir / "report.json",
        {
            **plan,
            "stop_reason": stopped,
            "batch_seconds": perf_counter() - batch.started,
            "artifact_directory": str(run_dir),
            "document": document.name,
            "batch_memory_samples": batch.samples,
        },
    )
    app.log(f"Straight twist pilot evidence: {run_dir}")
