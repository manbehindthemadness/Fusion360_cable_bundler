"""
Expose one banking-invalid quarter-turn candidate as visible planar sketches only.

Requires idle live Fusion; retains existing documents and creates no solids or
loft features. This is a representation diagnostic, not geometry validation.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import dot, magnitude
from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT

from .master_frames import master_scaffold
from .native_budget import NativeBudget
from .reflected_twist import ReflectedTwistDiagnostic
from .straight_twist import section_arcs
from .turn_pair import turn_fixtures

NAME = "Ribbon diagnostic - 90 turn - reflected roll - sketches only"


def run(_context: object) -> None:
    """
    Draw one fixed specimen once, bounded to 60 seconds and 2 GiB observed RSS.

    Capture host errors intentionally to preserve partial sketches without retry.
    Limits gate subsequent operations; an in-flight native call cannot be cancelled.
    No solid construction, cap fitting or post-build compliance audit is attempted.
    """
    app = adsk.core.Application.get()
    if app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("An active Fusion command prevents sketch authoring.")
    existing = next(
        (
            app.documents.item(i)
            for i in range(app.documents.count)
            if app.documents.item(i).name == NAME
        ),
        None,
    )
    if existing is not None:
        if app.activeDocument != existing:
            raise RuntimeError("Existing diagnostic is not the active document.")
        existing_design = adsk.fusion.Design.cast(app.activeProduct)
        root = existing_design.rootComponent
        if root.sketches.count or root.bRepBodies.count or root.constructionPlanes.count:
            raise RuntimeError("Existing geometry must not be overwritten or retried.")
    budget = NativeBudget(maximum_seconds=60)
    budget.check("math")
    started = perf_counter()
    case = turn_fixtures()[0].case
    scaffold = master_scaffold(
        case.route,
        case.start_width,
        case.end_width,
        28.5,
        twist=ReflectedTwistDiagnostic(360),
    )
    ratios = tuple(
        abs(dot(curvature, frame.width)) / magnitude(curvature)
        if magnitude(curvature) > 1e-12
        else 0.0
        for frame, curvature in zip(scaffold.frames, scaffold.curvature_vectors)
    )
    directory = (
        PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/reflected_sketch" / uuid4().hex
    )
    directory.mkdir(parents=True)
    paths = (
        Path(__file__),
        Path(__file__).with_name("master_frames.py"),
        Path(__file__).with_name("reflected_twist.py"),
        Path(__file__).with_name("turn_pair.py"),
        Path(__file__).with_name("straight_twist.py"),
        PROJECT_ROOT / "experiment_testing_rules.txt",
        PROJECT_ROOT / "rollback_end_loft_notes.txt",
    )
    plan = {
        "case": asdict(case),
        "scaffold": asdict(scaffold),
        "width_axis_curvature_ratios": ratios,
        "section_arcs_mm": section_arcs(),
        "sources": {
            str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
        },
        "scope": "one quarter-turn trunk, undeformed sections, reflected 0/180/0 roll",
        "limits": {"seconds": 60, "rss_kib": budget.maximum_rss_kib},
    }
    (directory / "plan.json").write_text(json.dumps(plan, indent=2, default=str), encoding="utf-8")
    report: dict[str, object] = {
        "document": NAME,
        "status": "not_started",
        "sections": 0,
        "math_seconds": perf_counter() - started,
        "numerical": "no-wide-axis-bend rule violated",
        "violating_samples": sum(value > 1e-8 for value in ratios),
        "maximum_width_axis_curvature_ratio": max(ratios),
        "native_loft_attempts": 0,
        "complete_ribbons_built": 0,
        "post_build_compliance": "unattempted; sketch-only diagnostic",
    }
    started = perf_counter()
    try:
        budget.check("new document")
        if existing is None:
            document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
            document.name = NAME
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.DirectDesignType
        component = design.rootComponent
        for index, frame in enumerate(scaffold.frames):
            budget.check(f"section {index + 1}")
            origin = adsk.core.Point3D.create(
                frame.origin.x / 10,
                frame.origin.y / 10,
                frame.origin.z / 10,
            )
            normal = adsk.core.Vector3D.create(
                frame.tangent.x,
                frame.tangent.y,
                frame.tangent.z,
            )
            plane_input = component.constructionPlanes.createInput()
            if not plane_input.setByPlane(adsk.core.Plane.create(origin, normal)):
                raise RuntimeError("Section plane setup failed.")
            plane = component.constructionPlanes.add(plane_input)
            plane.isLightBulbOn = False
            sketch = component.sketches.add(plane)
            roll = math.degrees(scaffold.bank_angles_radians[index])
            sketch.name = (
                f"Section {index + 1:02d} - roll {roll:.2f}deg - "
                f"wide-bend ratio {ratios[index]:.4f}"
            )
            sketch.isComputeDeferred = True
            for arc in section_arcs():
                points = []
                for x, y in arc:
                    point = adsk.core.Point3D.create(
                        (frame.origin.x + frame.width.x * x + frame.thickness.x * y) / 10,
                        (frame.origin.y + frame.width.y * x + frame.thickness.y * y) / 10,
                        (frame.origin.z + frame.width.z * x + frame.thickness.z * y) / 10,
                    )
                    points.append(sketch.modelToSketchSpace(point))
                sketch.sketchCurves.sketchArcs.addByThreePoints(*points)
            sketch.isComputeDeferred = False
            if sketch.profiles.count != 1 or sketch.sketchCurves.sketchArcs.count != 40:
                raise RuntimeError("Original section topology guard failed.")
            sketch.areProfilesShown = False
            sketch.arePointsShown = False
            sketch.isLightBulbOn = True
            report["sections"] = index + 1
        report["body_count"] = component.bRepBodies.count
        if component.bRepBodies.count != 0:
            raise RuntimeError("Sketch-only diagnostic unexpectedly contains a body.")
        report["status"] = "32 section sketches created; no loft attempted"
        budget.check("display")
        app.activeViewport.fit()
        app.activeViewport.refresh()
        budget.check("screenshot")
        report["screenshot_saved"] = app.activeViewport.saveAsImageFile(
            str(directory / "sketches.png"),
            1800,
            1100,
        )
    except Exception as error:
        report["status"] = "stopped; partial sketches retained, no retry"
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        report["sketch_and_display_seconds"] = perf_counter() - started
        report["resource_samples"] = budget.samples
        report["stop_reason"] = budget.stopped
        (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        app.log(f"Reflected sketch diagnostic: {directory}; {report['status']}")
