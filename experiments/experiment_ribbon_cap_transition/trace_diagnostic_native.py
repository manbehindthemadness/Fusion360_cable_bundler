"""
Display one unchanged failing trace with cap headings and a curvature marker.

One numerical diagnostic and one curve-only display attempt; no solids, retries,
shape search, report files or edits to retained candidate bodies.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, process_time
from typing import Any
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3, lerp
from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT
from experiments.experiment_ribbon_diagnosis.storage import archive

from . import sweep_reference_native
from .lateral_native import _bodies, _design
from .native_budget import NativeBudget, resident_kib
from .trace_diagnostic import INTERVALS_PER_SEGMENT, diagnose_trace
from .trace_sweep_native import _point

NAME = "Trace01 diagnostic - banked crossover"
_state: dict[str, Any] | None = None


def prepare() -> dict[str, Any]:
    """
    Verify frozen provenance and evaluate the failed case once, without geometry.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Trace diagnostic already prepared; no retry.")
    previous = sweep_reference_native._state
    if previous is None or not previous["finished"] or not previous["stop_reason"]:
        raise RuntimeError("Expected the preserved stopped sweep batch.")
    if sweep_reference_native._fingerprints() != previous["plan"]["sources"]:
        raise RuntimeError("Frozen sweep inputs/procedure changed; do not diagnose a replacement.")
    case = previous["cases"][0]
    _document, design = _design()
    if any(c.name == NAME for c in design.allComponents) or resident_kib() >= 2097152:
        raise RuntimeError("Diagnostic already exists or memory ceiling reached.")
    started = perf_counter()
    plan = {
        "question": "Does trace1 itself violate4.5mm radius, or is conservative certification unresolved? Compare analytic shared lane and unchanged interpolated cubics.",
        "input": asdict(case),
        "samples_per_cubic": INTERVALS_PER_SEGMENT + 1,
        "numerical_seconds_limit": 10,
        "display_seconds_limit": 30,
        "overall_seconds_limit": 60,
        "rss_kib": 2097152,
        "solves": 1,
        "display_attempts": 1,
        "native_solid_attempts": 0,
        "search": 0,
        "retries": 0,
        "parent_sources": previous["plan"]["sources"],
        "diagnostic_sources": {
            str(p.relative_to(PROJECT_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__), Path(__file__).with_name("trace_diagnostic.py"))
        },
    }
    path, result = diagnose_trace(case, 1)
    _state = {
        "plan": plan,
        "case": case,
        "path": path,
        "result": result,
        "baseline": _bodies(design),
        "started": started,
        "display_attempted": False,
        "finished": False,
    }
    return result


def display() -> dict[str, Any]:
    """
    Author the exact NURBS once, draw two headings and mark the smallest observation.

    Preserve failed diagnostic inputs on API errors. Native operations are checked
    only at scheduling boundaries; no assumption that cancellation stops a kernel.
    """
    state = _state
    if state is None or state["display_attempted"]:
        raise RuntimeError("No undisplayed diagnostic; no retry.")
    state["display_attempted"] = True
    budget = NativeBudget(maximum_seconds=30)
    wall_started, cpu_started = perf_counter(), process_time()
    try:
        if perf_counter() - state["started"] >= 60:
            raise RuntimeError("Diagnostic overall scheduling limit reached.")
        _document, design = _design()
        path, case = state["path"], state["case"]
        budget.check("diagnostic_component")
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = adsk.core.Vector3D.create(48, 0, 0)
        component = design.rootComponent.occurrences.addNewComponent(matrix).component
        component.name = NAME
        sketch = component.sketches.add(component.xYConstructionPlane)
        sketch.name = "Unchanged trace01 - cubic sweep interpolation"
        controls = [sketch.modelToSketchSpace(_point(p)) for p in path.controls]
        curve = adsk.core.NurbsCurve3D.createNonRational(controls, 3, list(path.knots), False)
        if curve is None or sketch.sketchCurves.sketchFixedSplines.addByNurbsCurve(curve) is None:
            raise RuntimeError("Native diagnostic curve authoring failed.")
        budget.check("endpoint_tangents")
        tangents = component.sketches.add(component.xYConstructionPlane)
        tangents.name = "Prescribed start and end headings - 10mm"
        for endpoint, heading in (
            (path.controls[0], case.start_tangent),
            (path.controls[-1], case.end_tangent),
        ):
            line = tangents.sketchCurves.sketchLines.addByTwoPoints(
                tangents.modelToSketchSpace(_point(endpoint)),
                tangents.modelToSketchSpace(_point(endpoint.translated(heading, 10))),
            )
            if line is None:
                raise RuntimeError("Endpoint tangent display failed.")
            line.isConstruction = True
        worst = state["result"]["interpolated_smallest_observed"]
        position = Vector3(*worst["position_mm"])
        marker = component.sketches.add(component.xYConstructionPlane)
        marker.name = (
            f"Smallest observed radius {worst['radius_mm']:.6f}mm - segment{worst['segment']}"
        )
        for axis in (Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)):
            if (
                marker.sketchCurves.sketchLines.addByTwoPoints(
                    marker.modelToSketchSpace(_point(position.translated(axis, -1))),
                    marker.modelToSketchSpace(_point(position.translated(axis, 1))),
                )
                is None
            ):
                raise RuntimeError("Curvature-location marker failed.")
        for item in (sketch, tangents, marker):
            item.isLightBulbOn = True
        state["result"]["curve_display_seconds"] = perf_counter() - wall_started
        state["result"]["curve_display_cpu_seconds"] = process_time() - cpu_started
        budget.check("camera")
        app = adsk.core.Application.get()
        target = _point(lerp(path.controls[0], path.controls[-1], 0.5))
        target.x += 48
        camera = app.activeViewport.camera
        camera.isPerspective = False
        camera.target = target
        camera.eye = adsk.core.Point3D.create(target.x + 10, target.y - 12, target.z + 10)
        camera.upVector = adsk.core.Vector3D.create(0, 0, 1)
        if not camera.setExtents(12, 10):
            raise RuntimeError("Diagnostic camera extent failed.")
        app.activeViewport.camera = camera
        app.activeViewport.refresh()
        directory = (
            PROJECT_ROOT
            / "artifacts/verification/ribbon_cap_transition/trace_diagnostic"
            / uuid4().hex
        )
        directory.mkdir(parents=True, exist_ok=False)
        budget.check("archive")
        export_started = perf_counter()
        archive(design, directory / "candidates.f3d")
        app.activeViewport.saveAsImageFile(str(directory / "trace.png"), 1800, 1100)
        state["result"]["archive_and_image_seconds"] = perf_counter() - export_started
        state["result"]["directory"] = str(directory)
        current = {b["name"]: b["volume_cm3"] for b in _bodies(design)}
        state["result"]["retained_names_volumes_unchanged"] = all(
            current.get(b["name"]) == b["volume_cm3"] for b in state["baseline"]
        )
        state["result"]["solid_count"] = len(current)
        state["finished"] = True
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        state["result"]["display_error"] = str(error)
    finally:
        state["result"]["overall_seconds"] = perf_counter() - state["started"]
        state["result"]["memory_samples"] = budget.samples
        state["result"]["final_rss_kib"] = resident_kib()
    return state["result"]
