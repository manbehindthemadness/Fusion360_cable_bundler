"""
Run one frozen seven-case coupled-frame diagnostic and display its three guides.

Limits: 10 seconds numerical, 30 seconds drawing, 60 seconds overall, 2 GiB
sampled RSS; no searches, retries, solids or new report files. Baselines precede
all adjusted solves. Stop on control regression, source, resource or API failure.
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

from .biarc_route import audit as baseline_audit
from .biarc_route import biarc
from .coupled_motion import CoupledMotion
from .coupled_route import CoupledRejection, audit, cases, construct, spline_controls
from .endpoint_first import EndpointCase
from .lateral_native import _bodies, _design
from .native_budget import NativeBudget, resident_kib
from .trace_sweep_native import _point

NAME = "Coupled bend and rotation - three guide diagnostic"
_state: dict[str, Any] | None = None


def _fingerprints() -> dict[str, str]:
    """
    Freeze source, fixture and rule content without generating a report file.
    """
    paths = tuple(
        Path(__file__).with_name(name)
        for name in (
            "coupled_motion.py",
            "coupled_route.py",
            "coupled_native.py",
            "biarc_route.py",
            "endpoint_first.py",
            "endpoint_reference.py",
            "endpoint_lateral.py",
            "lateral_native.py",
            "native_budget.py",
            "trace_sweep_native.py",
        )
    ) + tuple(
        PROJECT_ROOT / name
        for name in ("experiment_testing_rules.txt", "rollback_end_loft_notes.txt")
    )
    return {
        str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def _guides(component: Any, case: EndpointCase) -> None:
    """
    Show frozen endpoint positions, headings and ordered width extents, even on failure.
    """
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketch.name = "Fixed endpoint headings and ordered width guides"
    half = case.lines * case.diameter_mm / 2
    for p, tangent, width in (
        (case.start, case.start_tangent, case.start_width),
        (case.end, case.end_tangent, case.end_width),
    ):
        for a, b in (
            (p, p.translated(tangent, 10)),
            (p.translated(width, -half), p.translated(width, half)),
        ):
            line = sketch.sketchCurves.sketchLines.addByTwoPoints(
                sketch.modelToSketchSpace(_point(a)), sketch.modelToSketchSpace(_point(b))
            )
            if line is None:
                raise RuntimeError("Frozen endpoint guide construction failed.")
            line.isConstruction = True
    sketch.isLightBulbOn = True


def _curves(component: Any, case: EndpointCase, motions: tuple[CoupledMotion, ...]) -> None:
    """
    Draw center and two outer mid-thickness edges as explicit cubic diagnostics.
    """
    half = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    for name, offset in (
        ("Center trajectory", 0.0),
        ("Negative width edge", -half),
        ("Positive width edge", half),
    ):
        sketch = component.sketches.add(component.xYConstructionPlane)
        sketch.name = name + " - cubic approximation, not a compliance certificate"
        points, knots = spline_controls(motions, offset)
        native_points = [sketch.modelToSketchSpace(_point(point)) for point in points]
        curve = adsk.core.NurbsCurve3D.createNonRational(native_points, 3, list(knots), False)
        if curve is None or sketch.sketchCurves.sketchFixedSplines.addByNurbsCurve(curve) is None:
            raise RuntimeError("Coupled diagnostic spline construction failed.")
        sketch.isLightBulbOn = True


def run() -> dict[str, Any]:
    """
    Freeze all seven endpoint inputs, retain every outcome and leave one project open.

    Rejected travel systems display endpoint guides only. Constructed but rejected
    numerical routes may display as explicitly failed diagnostics. Approximate
    curves are not native ribbon sweeps or post-build compliance evidence.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Coupled diagnostic already started; no retry.")
    _document, design = _design()
    if any(component.name == NAME for component in design.allComponents):
        raise RuntimeError("Coupled diagnostic already exists; no duplicate.")
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    retained = _bodies(design)
    inputs, sources = cases(), _fingerprints()
    _state = {
        "plan": {
            "algorithm": "oblique-ABA-frame-factorization-positive-length-solve-v1",
            "inputs": [asdict(case) for case in inputs],
            "sources": sources,
            "degrees_of_freedom": "Three positive lengths, one linear solve; fixed Euler branch and quintic angle law. Centerline may reroute.",
            "baseline": "Same fixed input poses through equal-distance biarc, all baseline rows before new solves.",
            "controls": ["control", "reference_broad_return"],
            "collateral": ["quarter_plus", "quarter_minus", "half_oblique"],
            "hypothesis": "Coupled oblique-axis motion enforces modeled no-edgewise bending while fixed endpoint pose closure is attempted without search.",
            "native_prediction": "Unknown; zero ribbon solid attempts authorized.",
            "evidence": "Analytic frame/curvature, sampled lane/envelope checks, approximate center and edges; no full compliance claim.",
            "limits": {
                "cases": 7,
                "solves_per_case": 1,
                "search": 0,
                "retries": 0,
                "solid_attempts": 0,
                "math_seconds": 10,
                "drawing_seconds": 30,
                "overall_seconds": 60,
                "rss_kib": 2097152,
            },
            "stop": "Control regression, source/fixture change, API/harness failure, or any resource limit; no local fixes or reruns.",
            "lineage": "All seven are existing examined development cases; no holdouts.",
        },
        "rows": [
            {
                "case": case.name,
                "baseline_evaluated": False,
                "evaluated": False,
                "display_attempted": False,
                "displayed_curves": False,
                "overall": "unattempted",
            }
            for case in inputs
        ],
        "stop_reason": None,
    }
    cpu_started = process_time()
    routes: list[tuple[CoupledMotion, ...] | None] = []
    try:
        numerical_started = perf_counter()
        for case, row in zip(inputs, _state["rows"]):
            budget.check("baseline_" + case.name)
            if perf_counter() - numerical_started >= 10:
                raise RuntimeError("Numerical time limit reached.")
            started = perf_counter()
            try:
                row["baseline"] = baseline_audit(case, biarc(case))
            except ValueError as error:
                row["baseline"] = {"construction_rejection": str(error)}
            row["baseline_evaluated"] = True
            row["baseline_seconds"] = perf_counter() - started
        for case, row in zip(inputs, _state["rows"]):
            budget.check("solve_" + case.name)
            if perf_counter() - numerical_started >= 10:
                raise RuntimeError("Numerical time limit reached.")
            if _fingerprints() != sources:
                raise RuntimeError("Frozen source or fixture changed before solve.")
            started = perf_counter()
            try:
                motions = construct(case)
            except CoupledRejection as error:
                row.update({"overall": "failed", "construction_rejection": str(error)})
                motions = None
            row["solve_seconds"] = perf_counter() - started
            started = perf_counter()
            if motions is not None:
                row.update(audit(case, motions))
            row["audit_seconds"] = perf_counter() - started
            row["evaluated"] = True
            routes.append(motions)
            if case.name in ("control", "reference_broad_return") and row["overall"] == "failed":
                raise RuntimeError("Representative control regression: " + case.name)
        _state["numerical_seconds"] = perf_counter() - numerical_started
        display_started = perf_counter()
        budget.check("create_array")
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = adsk.core.Vector3D.create(96, 0, 0)
        parent = design.rootComponent.occurrences.addNewComponent(matrix).component
        parent.name = NAME
        for index, (case, motions, row) in enumerate(zip(inputs, routes, _state["rows"])):
            budget.check("display_" + case.name)
            if perf_counter() - display_started >= 30:
                raise RuntimeError("Drawing time limit reached.")
            if _fingerprints() != sources:
                raise RuntimeError("Frozen source changed before drawing.")
            row["display_attempted"] = True
            started = perf_counter()
            transform = adsk.core.Matrix3D.create()
            transform.translation = adsk.core.Vector3D.create(
                (index % 3) * 16, -(index // 3) * 16, 0
            )
            component = parent.occurrences.addNewComponent(transform).component
            component.name = f"{index + 1} {case.name} - {row['overall']}"
            _guides(component, case)
            if motions is not None:
                _curves(component, case, motions)
                row["displayed_curves"] = True
            row["display_seconds"] = perf_counter() - started
        _state["display_seconds"] = perf_counter() - display_started
        budget.check("archive_camera")
        app = adsk.core.Application.get()
        camera = app.activeViewport.camera
        camera.isPerspective = False
        camera.target = adsk.core.Point3D.create(111, -13, 1.5)
        camera.eye = adsk.core.Point3D.create(125, -35, 29)
        camera.upVector = adsk.core.Vector3D.create(0, 0, 1)
        if not camera.setExtents(59, 47):
            raise RuntimeError("Coupled diagnostic camera failed.")
        app.activeViewport.camera = camera
        app.activeViewport.refresh()
        directory = (
            PROJECT_ROOT
            / "artifacts/verification/ribbon_cap_transition/coupled_guides"
            / uuid4().hex
        )
        directory.mkdir(parents=True, exist_ok=False)
        started = perf_counter()
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "trajectories.png"), 1800, 1100):
            raise RuntimeError("Coupled diagnostic image export failed.")
        _state["archive_image_seconds"] = perf_counter() - started
        _state["directory"] = str(directory)
        current = _bodies(design)
        _state["original_solids_unchanged"] = len(current) == len(retained) and all(
            old in current for old in retained
        )
        if not _state["original_solids_unchanged"]:
            raise RuntimeError("Original solid identity or geometry changed.")
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        _state["stop_reason"] = str(error)
    finally:
        _state["overall_seconds"] = perf_counter() - budget.started
        _state["cpu_seconds"] = process_time() - cpu_started
        _state["maximum_sampled_rss_kib"] = max(int(sample["rss_kib"]) for sample in budget.samples)
        _state["final_rss_kib"] = resident_kib()
    return _state
