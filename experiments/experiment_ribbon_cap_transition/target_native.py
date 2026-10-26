"""
Run one bounded joint endpoint-closure trial in the empty owned Fusion scratch.

Eight fixed development poses,12updates/181evaluations per spatial pose,zero
solid attempts/retries. Preserve the earlier event results as the baseline and
write only F3D/PNG,with all numerical outcomes retained in memory.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, process_time
from typing import Any, cast
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT
from experiments.experiment_ribbon_diagnosis.storage import archive

from . import coupled_native, event_native
from .endpoint_first import EndpointCase
from .event_cases import cases
from .event_display import annotate
from .event_labels import inspect
from .material_allocation import MaterialPlan
from .material_display import curves
from .material_guides import audit
from .native_budget import NativeBudget, resident_kib
from .radius_native import _gap
from .target_shooting import construct

NAME = "Joint target closure - continuous ribbon paths"
_state: dict[str, Any] | None = None
_plans: list[MaterialPlan] = []


# noinspection PyProtectedMember
def _display_paths(component: Any, case: EndpointCase, plan: MaterialPlan) -> None:
    """
    Draw fixed target guides,continuous material paths and the remaining gap.

    Reuse the frozen diagnostic adapters without modifying their baseline sources.
    """
    coupled_native._guides(component, case)
    curves(component, plan.strip)
    _gap(component, plan, case.end)


# noinspection PyProtectedMember
def _sources() -> dict[str, str]:
    """
    Freeze all inherited sources plus this trial's solver and adapter.
    """
    sources = event_native._sources()
    for name in ("target_shooting.py", "target_native.py"):
        path = Path(__file__).with_name(name)
        sources[str(path.relative_to(PROJECT_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return sources


# noinspection PyProtectedMember
def run() -> dict[str, Any]:
    """
    Solve and audit the unchanged eight poses once,then draw numbered guides.

    Stop on source/control/invariant/API/resource failure without local repair.
    Limits are10s numerical/30s drawing/60s overall/2GiB sampled RSS. A closure
    miss is retained as a failed case,not repaired or treated as kernel failure.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Joint closure trial already started;no retry.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle empty scratch.")
    root = design.rootComponent
    if root.occurrences.count or root.sketches.count or root.bRepBodies.count:
        raise RuntimeError("Expected empty scratch;no deletion authorized.")
    baseline = event_native._state
    if baseline is None or baseline["stop_reason"] is not None:
        raise RuntimeError("Complete earlier baseline unavailable.")
    for path, digest in baseline["plan"]["sources"].items():
        if event_native._sources().get(path) != digest:
            raise RuntimeError("Inherited source drift:" + path)
    inputs, sources = cases(), _sources()
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    cpu_started = process_time()
    state: dict[str, Any] = {
        "plan": {
            "algorithm": "joint-target-shooting-v1",
            "hypothesis": "Joint turn-axis/angle/travel adjustment reduces endpoint residual without violating material constraints;improvement safeguard prevents oscillating worse iterates.",
            "inputs": [asdict(case) for case in inputs],
            "sources": sources,
            "baseline_rows": deepcopy(baseline["rows"]),
            "degrees_of_freedom": "3angles in[-pi,pi],3eta in[-4,4],7nonnegative travel surpluses;13coordinates initialized from original schedule,eta clipped;controls unchanged.",
            "procedure": "12damped joint rounds;13forward probes(1e-5)and at most2trialsteps each;stepnorm<=0.35,onlystrict residual improvement accepted. Position scaled by chord,tangent/width residuals unscaled.181evaluations maximum per spatial case;no outside-edge-first event routing.",
            "limits": "8cases,12updates/181evaluations per spatial case,0native solids/retries,10s numerical/30s drawing/60s overall/2GiB sampled RSS",
            "scope": "Examined development cases only;no holdouts/invalid controls. Same material floors/audit;frame closure also required. Native prediction unknown;0solid attempts.",
            "stop": "Source,material invariant,control,API or resource failure;no repair/retry.",
        },
        "rows": [
            {
                "number": i + 1,
                "case": case.name,
                "solved": False,
                "audited": False,
                "drawn": False,
                "overall": "unattempted",
            }
            for i, case in enumerate(inputs)
        ],
        "stop_reason": None,
    }
    _state = state
    observations = []
    try:
        numerical_started = perf_counter()

        def checkpoint() -> None:
            """
            Stop between joint rounds before scheduling additional numerical work.
            """
            budget.check("joint_round")
            if perf_counter() - numerical_started >= 10:
                raise RuntimeError("Numerical budget reached during joint solve.")

        for case, row in zip(inputs, state["rows"]):
            budget.check("solve_" + case.name)
            if perf_counter() - numerical_started >= 10 or _sources() != sources:
                raise RuntimeError("Numerical time or source gate.")
            started = perf_counter()
            plan, counters = construct(case, checkpoint=checkpoint)
            row.update(counters)
            row.update(
                {
                    "solved": True,
                    "solve_seconds": perf_counter() - started,
                    "endpoint_gap_mm": plan.endpoint_gap_mm,
                    "connected": plan.connected,
                    "updates": plan.updates,
                    "termination": plan.termination,
                }
            )
            _plans.append(plan)
            started = perf_counter()
            row.update(audit(case, plan))
            if max(row["endpoint_tangent_error"], row["endpoint_width_error"]) > 1e-8:
                row["findings"].append("ordered endpoint frame not reached")
                row["overall"] = "failed"
            row.update({"audited": True, "audit_seconds": perf_counter() - started})
            if (
                row["analytic_principal_curvature_ratio"] > 0.8
                or row["minimum_material_jacobian"] <= 0
                or row["sampled_material_speed_error"] > 1e-8
                or plan.lane_curvature_bound_per_mm > 1 / (3 * case.diameter_mm)
            ):
                raise RuntimeError("Material invariant contradicted:" + case.name)
            if (
                case.name in ("control", "reference_broad_return", "smooth_S_event_control")
                and row["overall"] == "failed"
            ):
                raise RuntimeError("Control regression:" + case.name)
            started = perf_counter()
            observation = inspect(plan.strip)
            observations.append(observation)
            row["observer_seconds"] = perf_counter() - started
        state["numerical_seconds"] = perf_counter() - numerical_started
        if state["numerical_seconds"] >= 10:
            raise RuntimeError("Numerical budget exceeded.")
        started_display = perf_counter()
        parent = root.occurrences.addNewComponent(adsk.core.Matrix3D.create()).component
        parent.name = NAME
        sampled = [
            [
                plan.strip.jet(plan.strip.length_mm * i / 32, v)[0]
                for v in (-plan.strip.half_width_mm, 0, plan.strip.half_width_mm)
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
        for i, (case, plan, row, observation) in enumerate(
            zip(inputs, _plans, state["rows"], observations)
        ):
            budget.check("draw_" + case.name)
            if perf_counter() - started_display >= 30 or _sources() != sources:
                raise RuntimeError("Drawing budget or source gate.")
            started = perf_counter()
            matrix = adsk.core.Matrix3D.create()
            matrix.translation = adsk.core.Vector3D.create((i % 3) * pitch, -(i // 3) * pitch, 0)
            occurrence = parent.occurrences.addNewComponent(matrix)
            comp = occurrence.component
            comp.name = f"{i + 1:02d} - {case.name} - {row['overall']}"
            _display_paths(comp, case, plan)
            annotate(comp, i + 1, plan.strip, observation)
            row.update({"drawn": True, "draw_seconds": perf_counter() - started})
        state["drawing_seconds"] = perf_counter() - started_display
        if state["drawing_seconds"] >= 30:
            raise RuntimeError("Drawing budget exceeded.")
        app.activeViewport.fit()
        app.activeViewport.refresh()
        budget.check("archive")
        started = perf_counter()
        directory = (
            PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/joint_target" / uuid4().hex
        )
        directory.mkdir(parents=True)
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "paths.png"), 1800, 1200):
            raise RuntimeError("Joint target image export failed.")
        state.update(
            {
                "archive_seconds": perf_counter() - started,
                "directory": str(directory),
                "display_pitch_cm": pitch,
            }
        )
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        state["stop_reason"] = str(error)
    state.update(
        {
            "overall_seconds": perf_counter() - budget.started,
            "cpu_seconds": process_time() - cpu_started,
            "maximum_sampled_rss_kib": max(cast(int, s["rss_kib"]) for s in budget.samples),
            "final_rss_kib": resident_kib(),
        }
    )
    return state
