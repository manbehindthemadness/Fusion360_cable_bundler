"""
Draw four exact-radius trajectory candidates, retaining every ribbon-frame finding.

Four solves/four curve displays,10s math/30s display/60s overall/2GiB. Zero solid
builds/search/retries/report files. Rejected ribbon candidates are explicitly
permitted curve-only diagnostics; source/resource/API failures stop scheduling.
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

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT
from experiments.experiment_ribbon_diagnosis.storage import archive

from .biarc_route import audit, biarc, rational_spline
from .clamped_comparison import _sources
from .endpoint_first import endpoint_cases
from .endpoint_lateral import lateral_cases
from .endpoint_reference import reference_cases
from .lateral_native import _bodies, _design
from .native_budget import NativeBudget, resident_kib
from .trace_sweep_native import _point

NAME = "Radius-limited trajectories - biarc diagnostic"
_state: dict[str, Any] | None = None


def run() -> dict[str, Any]:
    """
    Evaluate once and append exact rational splines to the owned candidate document.

    Radius checks do not waive the fixed width-axis bending or smooth-join rules.
    All original solids/sketches remain; only one new owned component is authored.
    ArchiveF3D/PNG only, leave the candidate document open and the new array in view.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Biarc display already started; no retry.")
    _document, design = _design()
    if any(component.name == NAME for component in design.allComponents):
        raise RuntimeError("Biarc trajectory array already exists; no duplicate.")
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    baseline = _bodies(design)
    cases = (reference_cases()[1], endpoint_cases()[0], lateral_cases()[-1], reference_cases()[0])
    sources = _sources()
    for name in ("biarc_native.py", "biarc_route.py", "lateral_native.py", "trace_sweep_native.py"):
        sources[name] = hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
    for name in ("experiment_testing_rules.txt", "rollback_end_loft_notes.txt"):
        sources[name] = hashlib.sha256((PROJECT_ROOT / name).read_bytes()).hexdigest()
    _state = {
        "plan": {
            "inputs": [asdict(case) for case in cases],
            "sources": sources,
            "algorithm": "equal-distance-two-circle-route-v1",
            "math_seconds": 10,
            "display_seconds": 30,
            "overall_seconds": 60,
            "rss_kib": 2097152,
            "solves": 4,
            "curve_attempts": 4,
            "native_solid_attempts": 0,
            "search": 0,
            "retries": 0,
            "diagnostic_permission": "Draw even when fixed-width or curvature-join ribbon rules fail; retain findings.",
        },
        "rows": [
            {"case": case.name, "evaluated": False, "display_attempted": False, "displayed": False}
            for case in cases
        ],
        "stop_reason": None,
    }
    routes = []
    math_started = perf_counter()
    cpu_started = process_time()
    try:
        for case, row in zip(cases, _state["rows"]):
            if perf_counter() - math_started >= 10:
                raise RuntimeError("Numerical scheduling limit reached.")
            started = perf_counter()
            arcs = biarc(case)
            row.update(audit(case, arcs))
            row["evaluated"] = True
            row["math_seconds"] = perf_counter() - started
            routes.append(arcs)
        _state["math_seconds"] = perf_counter() - math_started
        display_started = perf_counter()
        budget.check("trajectory_component")
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = adsk.core.Vector3D.create(64, 0, 0)
        parent = design.rootComponent.occurrences.addNewComponent(matrix).component
        parent.name = NAME
        for index, (case, arcs, row) in enumerate(zip(cases, routes, _state["rows"])):
            if perf_counter() - display_started >= 30:
                raise RuntimeError("Curve display scheduling limit reached.")
            budget.check(f"display_{case.name}")
            for name, expected in sources.items():
                local = Path(__file__).with_name(name) if "/" not in name else PROJECT_ROOT / name
                path = local if local.is_file() else PROJECT_ROOT / name
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise RuntimeError("Frozen source changed before trajectory display.")
            row["display_attempted"] = True
            started = perf_counter()
            transform = adsk.core.Matrix3D.create()
            transform.translation = adsk.core.Vector3D.create(
                (index % 2) * 12, -(index // 2) * 12, 0
            )
            component = parent.occurrences.addNewComponent(transform).component
            frame_status = (
                "frame fails"
                if not row["cap_width_rule_ok"] or not row["join_curvature_continuous"]
                else "frame checks only"
            )
            component.name = f"{index + 1} {case.name} - {frame_status}"
            sketch = component.sketches.add(component.xYConstructionPlane)
            sketch.name = "Trajectory spline - exact circular NURBS"
            points, weights, knots = rational_spline(arcs)
            native_points = [sketch.modelToSketchSpace(_point(p)) for p in points]
            curve = adsk.core.NurbsCurve3D.createRational(
                native_points, 2, list(knots), list(weights), False
            )
            if (
                curve is None
                or sketch.sketchCurves.sketchFixedSplines.addByNurbsCurve(curve) is None
            ):
                raise RuntimeError("Exact rational trajectory authoring failed.")
            guides = component.sketches.add(component.xYConstructionPlane)
            guides.name = "Fixed endpoint headings and ordered width guides"
            for endpoint, tangent, width in (
                (case.start, case.start_tangent, case.start_width),
                (case.end, case.end_tangent, case.end_width),
            ):
                for a, b in (
                    (endpoint, endpoint.translated(tangent, 10)),
                    (
                        endpoint.translated(width, -case.lines * case.diameter_mm / 2),
                        endpoint.translated(width, case.lines * case.diameter_mm / 2),
                    ),
                ):
                    line = guides.sketchCurves.sketchLines.addByTwoPoints(
                        guides.modelToSketchSpace(_point(a)), guides.modelToSketchSpace(_point(b))
                    )
                    if line is None:
                        raise RuntimeError("Endpoint guide drawing failed.")
                    line.isConstruction = True
            sketch.isLightBulbOn = True
            guides.isLightBulbOn = True
            row["displayed"] = True
            row["display_seconds"] = perf_counter() - started
        _state["display_seconds"] = perf_counter() - display_started
        budget.check("camera_archive")
        app = adsk.core.Application.get()
        camera = app.activeViewport.camera
        camera.isPerspective = False
        camera.target = adsk.core.Point3D.create(70, -4.5, 1.5)
        camera.eye = adsk.core.Point3D.create(80, -18.5, 17.5)
        camera.upVector = adsk.core.Vector3D.create(0, 0, 1)
        if not camera.setExtents(27, 24):
            raise RuntimeError("Trajectory camera extent failed.")
        app.activeViewport.camera = camera
        app.activeViewport.refresh()
        directory = (
            PROJECT_ROOT
            / "artifacts/verification/ribbon_cap_transition/biarc_trajectories"
            / uuid4().hex
        )
        directory.mkdir(parents=True, exist_ok=False)
        started = perf_counter()
        archive(design, directory / "candidates.f3d")
        app.activeViewport.saveAsImageFile(str(directory / "trajectories.png"), 1800, 1100)
        _state["archive_image_seconds"] = perf_counter() - started
        _state["directory"] = str(directory)
        current = _bodies(design)
        _state["retained_names_volumes_unchanged"] = len(current) == len(baseline) and all(
            any(
                b["token"] == old["token"]
                and b["volume_cm3"] == old["volume_cm3"]
                and b["name"] == old["name"]
                for b in current
            )
            for old in baseline
        )
        _state["solid_count"] = len(current)
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        _state["stop_reason"] = str(error)
    finally:
        _state["overall_seconds"] = perf_counter() - budget.started
        _state["cpu_seconds"] = process_time() - cpu_started
        _state["maximum_sampled_rss_kib"] = max(int(s["rss_kib"]) for s in budget.samples)
        _state["final_rss_kib"] = resident_kib()
    return _state
