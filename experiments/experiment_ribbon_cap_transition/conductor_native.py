"""
Display seven adaptive three-turn results with analytic conductor-curvature bounds.

Seven allocation problems, at most 63 algebraic bases each, no geometric search,
retries or solids. Limits:10s numerical/30s drawing/60s overall/2GiB sampled RSS.
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

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT
from experiments.experiment_ribbon_diagnosis.storage import archive

from . import coupled_native, radius_native
from .conductor_allocation import ConductorGuidePlan, construct
from .coupled_route import audit, cases
from .lateral_native import _bodies, _design
from .native_budget import NativeBudget, resident_kib
from .radius_native import _gap

NAME = "Conductor-bounded three-turn trajectories"
_state: dict[str, Any] | None = None


def _sources() -> dict[str, str]:
    """
    Freeze new allocation code and every original baseline, guide, audit and rule source.
    """
    result = radius_native._sources()
    for name in ("banked_schedule.py", "conductor_allocation.py", "conductor_native.py"):
        path = Path(__file__).with_name(name)
        result[str(path.relative_to(PROJECT_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def run() -> dict[str, Any]:
    """
    Compare the frozen family under positive, curvature-bounded travel and draw all outputs.

    Unclosed minimum-length traces are authored regardless of allocation outcome
    solely for user inspection. They are never counted as connecting candidates,
    native ribbon builds or compliance passes. Archive only F3D/PNG; retain
    outcome counters and full provenance in memory for chat readout.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Conductor-bounded diagnostic already started; no retry.")
    baseline, inputs = radius_native._state, cases()
    if baseline is None or baseline.get("stop_reason") is not None:
        raise RuntimeError("Completed center-radius baseline unavailable.")
    if baseline["plan"]["inputs"] != [asdict(case) for case in inputs]:
        raise RuntimeError("Fixed case inputs differ from baseline.")
    if radius_native._sources() != baseline["plan"]["sources"]:
        raise RuntimeError("Frozen baseline source or rules changed.")
    _document, design = _design()
    if any(component.name == NAME for component in design.allComponents):
        raise RuntimeError("Conductor-bounded display already exists; no duplicate.")
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    originals, sources = _bodies(design), _sources()
    _state = {
        "plan": {
            "algorithm": "adaptive-three-turn-continuous-lane-bounds-v1",
            "hypothesis": "Three displacement-derived turns and continuous reference-lane bounds may remove tight conductor bends and improve fixed-pose connection.",
            "inputs": [asdict(case) for case in inputs],
            "sources": sources,
            "baseline": deepcopy(baseline["rows"]),
            "baseline_policy": "Cached previous outcomes; old solves excluded from new timing.",
            "degrees_of_freedom": "Three adaptive bank or chord-axis turns interleaved with four straights. One length allocation above center and conductor curvature floors; at most63 algebraic supports. No alternate strategy after failure.",
            "constraints": "0.8 centerline macaroni and analytic continuous reference-lane radius>=3diameters; no modeled width-axis bend,5-width sphere,1% length spread warning. Native interpolation remains unmeasured.",
            "limits": {
                "cases": 7,
                "allocation_calls": 7,
                "linear_bases_per_case": 63,
                "geometric_search": 0,
                "retries": 0,
                "solid_attempts": 0,
                "math_seconds": 10,
                "display_seconds": 30,
                "overall_seconds": 60,
                "rss_kib": 2097152,
            },
            "display_policy": "All seven center/outer-edge splines. Failed allocation draws required-minimum-length trace labelled unclosed, with fixed endpoint gap. No fallback accepted cable.",
            "stop": "Lane-bound contradiction, control regression, source/fixture change, resource or API/harness failure; no repair or enlarged budget.",
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
        "stop_reason": None,
    }
    cpu_started = process_time()
    plans: list[ConductorGuidePlan] = []
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
                    else "unclosed conductor-radius diagnostic",
                    "allocation_status": plan.allocation.status.value,
                    "checked_linear_bases": plan.allocation.checked_bases,
                    "separation_margin_mm": plan.allocation.separation_margin_mm,
                    "minimum_column_projection": plan.allocation.minimum_column_projection,
                    "lower_bounds_mm": plan.lower_bounds_mm,
                    "schedule_kind": plan.schedule_kind.value,
                    "analytic_lane_curvature_bound_per_mm": plan.lane_curvature_bound_per_mm,
                    "analytic_lane_radius_lower_bound_mm": 1 / plan.lane_curvature_bound_per_mm
                    if plan.lane_curvature_bound_per_mm > 0
                    else math.inf,
                }
            )
            started = perf_counter()
            row.update(audit(case, plan.motions))
            if (
                plan.lane_curvature_bound_per_mm > 1 / (3 * case.diameter_mm)
                or row["sampled_minimum_lane_radius_mm"] < 3 * case.diameter_mm
            ):
                raise RuntimeError(
                    "Reference conductor-curvature bound contradicted for " + case.name
                )
            if not plan.connected:
                row["findings"].append("fixed endpoint not reached; unclosed diagnostic only")
                row["overall"] = "failed"
            row["audit_seconds"] = perf_counter() - started
            row["evaluated"] = True
            plans.append(plan)
            if case.name in ("control", "reference_broad_return") and row["overall"] == "failed":
                raise RuntimeError("Representative control regression: " + case.name)
        _state["numerical_seconds"] = perf_counter() - started_math
        budget.check("create_array")
        started_display = perf_counter()
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = adsk.core.Vector3D.create(272, 0, 0)
        parent = design.rootComponent.occurrences.addNewComponent(matrix).component
        parent.name = NAME
        camera_points = []
        for index, (case, plan, row) in enumerate(zip(inputs, plans, _state["rows"])):
            budget.check("display_" + case.name)
            if perf_counter() - started_display >= 30:
                raise RuntimeError("Drawing scheduling limit reached.")
            if _sources() != sources:
                raise RuntimeError("Frozen sources changed before drawing.")
            row["display_attempted"] = True
            started = perf_counter()
            x_offset, y_offset = (index % 3) * 20, -(index // 3) * 20
            transform = adsk.core.Matrix3D.create()
            transform.translation = adsk.core.Vector3D.create(x_offset, y_offset, 0)
            component = parent.occurrences.addNewComponent(transform).component
            component.name = f"{index + 1} {case.name} - {row['guide_kind']} - {row['overall']}"
            coupled_native._guides(component, case)
            coupled_native._curves(component, case, plan.motions)
            _gap(component, plan, case.end)
            for point in (
                case.start,
                case.end,
                *(m.jet(u / 4)[0] for m in plan.motions for u in range(5)),
            ):
                camera_points.append(
                    (272 + x_offset + point.x / 10, y_offset + point.y / 10, point.z / 10)
                )
            row["displayed_curves"] = True
            row["display_seconds"] = perf_counter() - started
        _state["display_seconds"] = perf_counter() - started_display
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
            / "artifacts/verification/ribbon_cap_transition/conductor_allocation"
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
