"""
Run one bounded continuous-path event observation trial in an empty Fusion scratch.

Eight fixed endpoint configurations, at most six closure updates per spatial case,
zero solids/retries. Event labels observe finished continuous paths and cannot
change them.10s numerical/30s drawing/60s overall/2GiB sampled RSS; stop on a
control, material invariant, source, runtime or API failure without local repair.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, process_time
from typing import Any
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT
from experiments.experiment_ribbon_diagnosis.storage import archive

from . import closure_native, coupled_native, material_native
from .event_cases import S_NAME, cases, construct
from .event_display import annotate
from .event_labels import EventReadout, inspect
from .material_allocation import MaterialPlan
from .material_display import curves
from .material_guides import audit
from .native_budget import NativeBudget, resident_kib
from .radius_native import _gap

NAME = "Continuous ribbon paths - conceptual event observations"
OLD_MATERIAL_HASH = "3f5d37f4ae583c3690fa81040dffb1359b965cde7d691682004e96b5d6529790"
MATERIAL_PATH = "experiments/experiment_ribbon_cap_transition/material_strip.py"
_state: dict[str, Any] | None = None
_plans: list[MaterialPlan] = []


def _sources() -> dict[str, str]:
    """
    Hash all solver, observer, native adapter and inherited rule sources.
    """
    result = material_native._sources()
    for name in ("event_labels.py", "event_cases.py", "event_display.py", "event_native.py"):
        path = Path(__file__).with_name(name)
        result[str(path.relative_to(PROJECT_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _baseline() -> dict[str, Any]:
    """
    Preserve the stopped old trial and allow only the reviewed coordinate repair.

    Prior trial states are never reset or rerun. The original material source
    digest identifies the pre-repair baseline; every other inherited source must
    still match exactly. The last complete seven-case closure baseline is retained
    separately because the material trial reached only two shape solves.
    """
    previous = material_native._state
    if previous is None or previous["plan"]["sources"].get(MATERIAL_PATH) != OLD_MATERIAL_HASH:
        raise RuntimeError("Original stopped material baseline unavailable.")
    current = material_native._sources()
    for path, digest in previous["plan"]["sources"].items():
        if path != MATERIAL_PATH and current.get(path) != digest:
            raise RuntimeError("Unreviewed inherited source drift: " + path)
    if closure_native._state is None:
        raise RuntimeError("Complete earlier closure baseline unavailable.")
    return {
        "stopped_material": deepcopy(previous),
        "complete_closure_rows": deepcopy(closure_native._state["rows"]),
    }


def run() -> dict[str, Any]:
    """
    Freeze eight inputs, observe both signals, and draw numbered continuous guides.

    Accepts only an empty active design, preserving unrelated documents. Full
    provenance/results remain in memory; only F3D/PNG artifacts are written.
    This tests event-label hypotheses, not an outside-edge-first routing solver.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Event observation trial already started; no retry.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected an idle empty scratch design.")
    root = design.rootComponent
    if root.occurrences.count or root.sketches.count or root.bRepBodies.count:
        raise RuntimeError("Scratch is not empty; no deletion authorized.")
    baseline, inputs, sources = _baseline(), cases(), _sources()
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    _state = {
        "plan": {
            "algorithm": "continuous-material-path-event-observation-v1",
            "hypothesis": "Edge curvature difference may label sustained A/B handoffs and neutral regions; compare against signed center bending, including symmetric S ambiguity.",
            "inputs": [asdict(case) for case in inputs],
            "sources": sources,
            "baseline": baseline,
            "geometry_policy": "Same material solver with shared fsum prefix coordinates repaired; one analytic S control. Fixed endpoint inputs, continuous center/edges; labels do not alter geometry. This is event observation, not event-driven routing.",
            "observer": "257 matched material stations; curvature relative deadband0.001; straight bend/twist deadband1e-8/mm;3sample persistence. Heuristics,not calibrated mechanical laws.",
            "limits": {
                "cases": 8,
                "updates_per_spatial_case": 6,
                "projections_per_spatial_case": 19,
                "supports_per_projection": 63,
                "native_solid_attempts": 0,
                "retries": 0,
                "math_seconds": 10,
                "drawing_seconds": 30,
                "overall_seconds": 60,
                "rss_kib": 2097152,
            },
            "stop": "Source/fixture/resource/API failure,material invariant contradiction or control regression; no repair/retry or budget expansion.",
            "coverage": "Seven examined development fixtures plus one new development S control; no holdouts or invalid controls.",
            "native_prediction": "Unknown; zero native cable-solid attempts.",
        },
        "rows": [
            {
                "number": index + 1,
                "case": case.name,
                "solved": False,
                "audited": False,
                "drawn": False,
                "overall": "unattempted",
            }
            for index, case in enumerate(inputs)
        ],
        "stop_reason": None,
    }
    cpu_started = process_time()
    observations: list[EventReadout] = []
    try:
        started_math = perf_counter()
        for case, row in zip(inputs, _state["rows"]):
            budget.check("solve_" + case.name)
            if perf_counter() - started_math >= 10 or _sources() != sources:
                raise RuntimeError("Numerical budget or source gate reached.")
            started = perf_counter()
            plan = construct(case)
            row.update(
                {
                    "solved": True,
                    "solve_seconds": perf_counter() - started,
                    "endpoint_gap_mm": plan.endpoint_gap_mm,
                    "connected": plan.connected,
                    "updates": plan.updates,
                    "projection_calls": plan.projection_calls,
                    "supports": plan.checked_bases_total,
                    "history": plan.history,
                    "termination": plan.termination,
                }
            )
            _plans.append(plan)
            started = perf_counter()
            row.update(audit(case, plan))
            row.update({"audit_seconds": perf_counter() - started, "audited": True})
            if (
                row["analytic_principal_curvature_ratio"] > 0.8
                or row["minimum_material_jacobian"] <= 0
                or row["sampled_material_speed_error"] > 1e-8
                or plan.lane_curvature_bound_per_mm > 1 / (3 * case.diameter_mm)
            ):
                raise RuntimeError("Reference invariant contradicted: " + case.name)
            if (
                case.name in ("control", "reference_broad_return", S_NAME)
                and row["overall"] == "failed"
            ):
                raise RuntimeError("Control regression: " + case.name)
            started = perf_counter()
            observation = inspect(plan.strip)
            row["observer_seconds"] = perf_counter() - started
            row["events"] = asdict(observation)
            row["events"]["edge_regions"] = [
                {"kind": r.kind.value, "start_mm": r.start_mm, "end_mm": r.end_mm}
                for r in observation.edge_regions
            ]
            row["events"]["bend_regions"] = [
                {"kind": r.kind.value, "start_mm": r.start_mm, "end_mm": r.end_mm}
                for r in observation.bend_regions
            ]
            observations.append(observation)
        _state["numerical_seconds"] = perf_counter() - started_math
        if _state["numerical_seconds"] >= 10:
            raise RuntimeError("Numerical time exceeded.")
        budget.check("display")
        started_display = perf_counter()
        sampled = [
            [
                plan.strip.jet(plan.strip.length_mm * i / 32, h)[0]
                for h in (-plan.strip.half_width_mm, 0.0, plan.strip.half_width_mm)
                for i in range(33)
            ]
            for plan in _plans
        ]
        pitch = max(
            24.0,
            max(
                max(
                    max(getattr(p, a) for p in points) - min(getattr(p, a) for p in points)
                    for a in ("x", "y")
                )
                for points in sampled
            )
            / 10
            + 10,
        )
        parent = root.occurrences.addNewComponent(adsk.core.Matrix3D.create()).component
        parent.name = NAME
        camera_points = []
        for index, (case, plan, row, observation, points) in enumerate(
            zip(inputs, _plans, _state["rows"], observations, sampled)
        ):
            budget.check("draw_" + case.name)
            if perf_counter() - started_display >= 30 or _sources() != sources:
                raise RuntimeError("Drawing budget or source gate reached.")
            started = perf_counter()
            x, y = (index % 3) * pitch, -(index // 3) * pitch
            matrix = adsk.core.Matrix3D.create()
            matrix.translation = adsk.core.Vector3D.create(x, y, 0)
            component = parent.occurrences.addNewComponent(matrix).component
            component.name = f"{index + 1:02d} - {case.name} - {row['overall']}"
            coupled_native._guides(component, case)
            curves(component, plan.strip)
            _gap(component, plan, case.end)
            annotate(component, index + 1, plan.strip, observation)
            row.update({"drawn": True, "draw_seconds": perf_counter() - started})
            camera_points.extend(
                (x + p.x / 10, y + p.y / 10, p.z / 10) for p in (*points, case.start, case.end)
            )
        _state["drawing_seconds"] = perf_counter() - started_display
        if _state["drawing_seconds"] >= 30:
            raise RuntimeError("Drawing time exceeded.")
        bounds = [
            (min(p[i] for p in camera_points) - 6, max(p[i] for p in camera_points) + 6)
            for i in range(3)
        ]
        middle = [(a + b) / 2 for a, b in bounds]
        extent = sum((b - a) ** 2 for a, b in bounds) ** 0.5
        camera = app.activeViewport.camera
        camera.isPerspective = False
        camera.target = adsk.core.Point3D.create(*middle)
        camera.eye = adsk.core.Point3D.create(middle[0] + 14, middle[1] - 22, middle[2] + 28)
        camera.upVector = adsk.core.Vector3D.create(0, 0, 1)
        camera.setExtents(extent * 1.5, extent)
        app.activeViewport.camera = camera
        app.activeViewport.refresh()
        budget.check("archive")
        started = perf_counter()
        directory = (
            PROJECT_ROOT
            / "artifacts/verification/ribbon_cap_transition/event_observations"
            / uuid4().hex
        )
        directory.mkdir(parents=True, exist_ok=False)
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "paths.png"), 1800, 1200):
            raise RuntimeError("Event image export failed.")
        _state.update(
            {
                "archive_seconds": perf_counter() - started,
                "directory": str(directory),
                "display_pitch_cm": pitch,
            }
        )
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        _state["stop_reason"] = str(error)
    finally:
        _state.update(
            {
                "overall_seconds": perf_counter() - budget.started,
                "cpu_seconds": process_time() - cpu_started,
                "maximum_sampled_rss_kib": max(int(s["rss_kib"]) for s in budget.samples),
                "final_rss_kib": resident_kib(),
            }
        )
    return _state
