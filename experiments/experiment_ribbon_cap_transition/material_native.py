"""
Display seven bounded developable material-strip endpoint diagnostics.

At most six scalar updates/case,19 projections and1197 algebraic bases;
no retries or solids. Limits:10s numerical/30s drawing/60s overall/2GiB sampled RSS.
Keep fixed targets and draw visible end gaps instead of concealing failed closure.
"""

from __future__ import annotations

import hashlib
import math
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, process_time
from typing import Any
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

from cable_bundler.routing.geometry import difference, magnitude
from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT
from experiments.experiment_ribbon_diagnosis.storage import archive

from . import closure_native, coupled_native
from .coupled_route import cases
from .lateral_native import _bodies, _design
from .material_allocation import MaterialPlan, construct
from .material_display import curves
from .material_guides import audit
from .native_budget import NativeBudget, resident_kib
from .radius_native import _gap

NAME = "Developable material paths - curved interior sections"
_state: dict[str, Any] | None = None
_plans: list[MaterialPlan] = []


def _sources() -> dict[str, str]:
    """
    Freeze new allocation code and every original baseline, guide, audit and rule source.
    """
    result = closure_native._sources()
    for name in (
        "material_strip.py",
        "material_policy.py",
        "material_allocation.py",
        "material_guides.py",
        "material_display.py",
        "material_native.py",
    ):
        path = Path(__file__).with_name(name)
        result[str(path.relative_to(PROJECT_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def run() -> dict[str, Any]:
    """
    Evaluate one bounded closure solve per frozen boundary and draw all outputs.

    Final unclosed traces are authored regardless of closure outcome
    solely for user inspection. They are never counted as connecting candidates,
    native ribbon builds or compliance passes. Archive only F3D/PNG; retain
    outcome counters and full provenance in memory for chat readout.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Material-strip diagnostic already started; no retry.")
    baseline, inputs = closure_native._state, cases()
    if baseline is None or baseline.get("stop_reason") is not None:
        raise RuntimeError("Completed closure baseline unavailable.")
    if baseline["plan"]["inputs"] != [asdict(case) for case in inputs]:
        raise RuntimeError("Fixed case inputs differ from baseline.")
    if closure_native._sources() != baseline["plan"]["sources"]:
        raise RuntimeError("Frozen baseline source or rules changed.")
    _document, design = _design()
    if any(component.name == NAME for component in design.allComponents):
        raise RuntimeError("Material-strip display already exists; no duplicate.")
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    originals, sources = _bodies(design), _sources()
    _state = {
        "plan": {
            "algorithm": "developable-material-strip-bounded-closure-v1",
            "hypothesis": "Explicit local isometry, finite-width rulings and principal-curvature floors may preserve physical bend/twist compatibility while attempting fixed-pose closure.",
            "inputs": [asdict(case) for case in inputs],
            "sources": sources,
            "baseline": deepcopy(baseline["rows"]),
            "baseline_policy": "Cached previous outcomes; old solves excluded from new timing.",
            "degrees_of_freedom": "Same preselected three-turn family; one internal bank-plane or in-plane factorization-axis angle plus seven travel lengths. Six scalar Gauss-Newton updates maximum. Central difference h=1e-4rad; step cap pi/12; total angle cap pi/2-h; endpoint threshold1e-8mm; stationary derivative squared threshold1e-20 or step1e-12rad. Nearest nonnegative travel projection above retained old floors plus principal surface curvature and finite-width ruling transition floors; no best-of fallback, alternate family, target movement or post-result adjustment.",
            "constraints": "Explicit isometric reference midsurface with curved interior material sections and exact terminal sections; pure twist inadmissible. Principal surface curvature*reach<=0.8; analytic material-lane radius>=3diameters,5-width sphere. Same continuous reference lane length follows kinematics,not length repair. Three-guide sampled containment and finite-speed checks; native/thick-cable compliance unmeasured.",
            "limits": {
                "cases": 7,
                "maximum_updates_per_case": 6,
                "maximum_projection_calls_per_case": 19,
                "linear_bases_per_projection": 63,
                "maximum_linear_bases_per_case": 1197,
                "maximum_schedule_evaluations_per_case": 19,
                "retries": 0,
                "solid_attempts": 0,
                "math_seconds": 10,
                "display_seconds": 30,
                "overall_seconds": 60,
                "rss_kib": 2097152,
            },
            "display_policy": "All seven material center/outer-edge splines. Unsuccessful closure draws its final trace labelled unclosed, with fixed endpoint gap. No fallback accepted cable.",
            "stop": "Material metric,regularity or curvature contradiction, control regression, source/fixture change, resource or API/harness failure; no repair or enlarged budget.",
            "native_prediction": "Unknown; zero ribbon-solid attempts authorized.",
            "coverage": "Seven existing development cases; no invalid controls or holdouts.",
        },
        "rows": [
            {
                "case": case.name,
                "evaluated": False,
                "display_attempted": False,
                "displayed_curves": False,
                "overall": "unattempted",
            }
            for case in inputs
        ],
        "native_attempts": 0,
        "native_built": 0,
        "full_post_build_audits": 0,
        "stop_reason": None,
    }
    cpu_started = process_time()
    plans = _plans
    try:
        started_math = perf_counter()
        for case, row in zip(inputs, _state["rows"]):
            budget.check("allocate_" + case.name)
            if perf_counter() - started_math >= 10:
                raise RuntimeError("Numerical scheduling limit reached.")
            if _sources() != sources:
                raise RuntimeError("Frozen sources changed before allocation.")
            started = perf_counter()
            plan = construct(case)
            row["solve_seconds"] = perf_counter() - started
            row.update(
                {
                    "connected": plan.connected,
                    "endpoint_gap_mm": plan.endpoint_gap_mm,
                    "guide_kind": "connected candidate"
                    if plan.connected
                    else "unclosed material diagnostic",
                    "allocation_status": plan.allocation.status.value,
                    "checked_linear_bases": plan.allocation.checked_bases,
                    "separation_margin_mm": plan.allocation.separation_margin_mm,
                    "minimum_column_projection": plan.allocation.minimum_column_projection,
                    "lower_bounds_mm": plan.lower_bounds_mm,
                    "schedule_angle_radians": plan.schedule_angle,
                    "updates": plan.updates,
                    "projection_calls": plan.projection_calls,
                    "history_angle_gap_mm": plan.history,
                    "termination": plan.termination,
                    "schedule_kind": plan.schedule_kind.value,
                    "analytic_lane_curvature_bound_per_mm": plan.lane_curvature_bound_per_mm,
                    "analytic_lane_radius_lower_bound_mm": 1 / plan.lane_curvature_bound_per_mm
                    if plan.lane_curvature_bound_per_mm > 0
                    else math.inf,
                }
            )
            started = perf_counter()
            row.update(audit(case, plan))
            end_tangent, end_width = plan.motions[-1].frame(1)
            row["endpoint_tangent_error"] = magnitude(difference(end_tangent, case.end_tangent))
            row["endpoint_width_error"] = magnitude(difference(end_width, case.end_width))
            if (
                plan.lane_curvature_bound_per_mm > 1 / (3 * case.diameter_mm)
                or row["sampled_minimum_lane_radius_mm"] < 3 * case.diameter_mm
                or row["analytic_principal_curvature_ratio"] > 0.8
                or row["minimum_material_jacobian"] <= 0
                or row["sampled_material_speed_error"] > 1e-8
            ):
                raise RuntimeError(
                    "Reference material compatibility bound contradicted for " + case.name
                )
            old = next(item for item in baseline["rows"] if item["case"] == case.name)
            row["baseline_endpoint_gap_mm"] = old["endpoint_gap_mm"]
            row["endpoint_gap_change_mm"] = plan.endpoint_gap_mm - old["endpoint_gap_mm"]
            row["new_findings"] = sorted(set(row["findings"]) - set(old["findings"]))
            row["removed_findings"] = sorted(set(old["findings"]) - set(row["findings"]))
            row["audit_seconds"] = perf_counter() - started
            row["evaluated"] = True
            plans.append(plan)
            if case.name in ("control", "reference_broad_return") and row["overall"] == "failed":
                raise RuntimeError("Representative control regression: " + case.name)
        _state["numerical_seconds"] = perf_counter() - started_math
        if _state["numerical_seconds"] >= 10:
            raise RuntimeError("Numerical limit exceeded.")
        budget.check("create_array")
        started_display = perf_counter()
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = adsk.core.Vector3D.create(400, 0, 0)
        parent = design.rootComponent.occurrences.addNewComponent(matrix).component
        parent.name = NAME
        for occurrence in design.rootComponent.occurrences:
            if occurrence.component.name == closure_native.NAME:
                occurrence.isLightBulbOn = False
        bounds_by_case = []
        for plan in plans:
            points = [
                plan.strip.jet(plan.strip.length_mm * u / 32, offset)[0]
                for offset in (-plan.strip.half_width_mm, 0.0, plan.strip.half_width_mm)
                for u in range(33)
            ]
            bounds_by_case.append(
                max(
                    max(getattr(p, axis) for p in points) - min(getattr(p, axis) for p in points)
                    for axis in ("x", "y")
                )
            )
        pitch = max(20.0, max(bounds_by_case) / 10 + 8)
        _state["display_pitch_cm"] = pitch
        camera_points = []
        for index, (case, plan, row) in enumerate(zip(inputs, plans, _state["rows"])):
            budget.check("display_" + case.name)
            if perf_counter() - started_display >= 30:
                raise RuntimeError("Drawing scheduling limit reached.")
            if _sources() != sources:
                raise RuntimeError("Frozen sources changed before drawing.")
            row["display_attempted"] = True
            started = perf_counter()
            x_offset, y_offset = (index % 3) * pitch, -(index // 3) * pitch
            transform = adsk.core.Matrix3D.create()
            transform.translation = adsk.core.Vector3D.create(x_offset, y_offset, 0)
            component = parent.occurrences.addNewComponent(transform).component
            component.name = f"{index + 1} {case.name} - {row['guide_kind']} - {row['overall']}"
            coupled_native._guides(component, case)
            curves(component, plan.strip)
            _gap(component, plan, case.end)
            for point in (
                case.start,
                case.end,
                *(
                    plan.strip.jet(plan.strip.length_mm * u / 32, offset)[0]
                    for offset in (-plan.strip.half_width_mm, 0.0, plan.strip.half_width_mm)
                    for u in range(33)
                ),
            ):
                camera_points.append(
                    (400 + x_offset + point.x / 10, y_offset + point.y / 10, point.z / 10)
                )
            row["displayed_curves"] = True
            row["display_seconds"] = perf_counter() - started
        _state["display_seconds"] = perf_counter() - started_display
        if _state["display_seconds"] >= 30:
            raise RuntimeError("Drawing limit exceeded.")
        budget.check("archive_camera")
        app = adsk.core.Application.get()
        bounds = [
            (min(p[i] for p in camera_points) - 2, max(p[i] for p in camera_points) + 2)
            for i in range(3)
        ]
        middle = [(a + b) / 2 for a, b in bounds]
        extent = math.sqrt(sum((b - a) ** 2 for a, b in bounds)) * 1.1
        camera = app.activeViewport.camera
        camera.isPerspective = False
        camera.target = adsk.core.Point3D.create(*middle)
        camera.eye = adsk.core.Point3D.create(middle[0] + 14, middle[1] - 22, middle[2] + 28)
        camera.upVector = adsk.core.Vector3D.create(0, 0, 1)
        if not camera.setExtents(extent * 1.64, extent):
            raise RuntimeError("Conductor diagnostic camera extent failed.")
        app.activeViewport.camera = camera
        app.activeViewport.refresh()
        directory = (
            PROJECT_ROOT
            / "artifacts/verification/ribbon_cap_transition/material_strip"
            / uuid4().hex
        )
        directory.mkdir(parents=True, exist_ok=False)
        started = perf_counter()
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "trajectories.png"), 1800, 1100):
            raise RuntimeError("Conductor diagnostic image export failed.")
        _state["archive_image_seconds"] = perf_counter() - started
        _state["directory"] = str(directory)
        current = _bodies(design)
        _state["original_solids_unchanged"] = len(current) == len(originals) and all(
            old in current for old in originals
        )
        if not _state["original_solids_unchanged"]:
            raise RuntimeError("Original solids changed.")
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        _state["stop_reason"] = str(error)
    finally:
        _state["overall_seconds"] = perf_counter() - budget.started
        _state["cpu_seconds"] = process_time() - cpu_started
        _state["maximum_sampled_rss_kib"] = max(int(sample["rss_kib"]) for sample in budget.samples)
        _state["final_rss_kib"] = resident_kib()
    return _state
