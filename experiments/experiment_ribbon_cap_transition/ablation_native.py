"""
Compare one floor-policy change across eight fixed poses without replacing evidence.

The cached joint trial is the baseline;no baseline solve is replayed. Candidate
paths09..16 are displayed below01..08. Zero solids/retries,no report files.
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

from . import target_native
from .event_cases import cases
from .event_display import annotate
from .event_labels import inspect
from .material_ablation import minimum_travel
from .material_allocation import MaterialPlan
from .material_guides import audit
from .native_budget import NativeBudget, resident_kib
from .target_shooting import construct

NAME = "Surface-width floor ablation - paths09-16"
SHOOTING_PATH = "experiments/experiment_ribbon_cap_transition/target_shooting.py"
OLD_SHOOTING_HASH = "1c2a3fc196b7b5edbc0b9ae607436a6d01a666628b1012039417231534f1922a"
_state: dict[str, Any] | None = None
_plans: list[MaterialPlan] = []


# noinspection PyProtectedMember
def _sources() -> dict[str, str]:
    """
    Include all inherited sources plus the isolated policy and native adapter.
    """
    sources = target_native._sources()
    for name in ("material_ablation.py", "ablation_native.py"):
        path = Path(__file__).with_name(name)
        sources[str(path.relative_to(PROJECT_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return sources


# noinspection PyProtectedMember
def run() -> dict[str, Any]:
    """
    Freeze and run one eight-case ablation within the explicitly approved limits.

    Only the new surface-width floor is omitted. Its legacy audit finding stays
    visible separately. Original center/conductor rules,regularity and fixed
    endpoint requirements remain.10s numerical/30s draw/60s total/2GiB sampledRSS.
    Stop on invariant/control/source/API/resource failure without repair/retry.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Ablation already started;no retry.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle owned scratch.")
    root = design.rootComponent
    if root.occurrences.count != 1 or root.occurrences.item(0).component.name != target_native.NAME:
        raise RuntimeError("Expected exactly the retained joint-target array.")
    baseline = target_native._state
    if baseline is None or baseline["stop_reason"] is not None or len(target_native._plans) != 8:
        raise RuntimeError("Complete joint-target baseline unavailable.")
    if baseline["plan"]["sources"].get(SHOOTING_PATH) != OLD_SHOOTING_HASH:
        raise RuntimeError("Unexpected baseline shooting implementation.")
    sources = _sources()
    for path, digest in baseline["plan"]["sources"].items():
        if path != SHOOTING_PATH and sources.get(path) != digest:
            raise RuntimeError("Unreviewed inherited source drift:" + path)
    inputs = cases()
    if [asdict(case) for case in inputs] != baseline["plan"]["inputs"]:
        raise RuntimeError("Fixed input drift.")
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    cpu_started = process_time()
    state: dict[str, Any] = {
        "plan": {
            "algorithm": "surface-width-floor-ablation-v1",
            "hypothesis": "The added width-based principal-curvature floor inflates travel;isolate its effect with all other policies and joint-shooting parameters unchanged.",
            "inputs": [asdict(case) for case in inputs],
            "sources": sources,
            "baseline_rows": deepcopy(baseline["rows"]),
            "reviewed_source_change": "Only target_shooting travel-policy injection;default seed/probes/updates/acceptance unchanged.",
            "limits": "8fixed configurations,12rounds/181evaluations per spatial case,0solids/retries,10s math/30s drawing/60s overall/2GiB sampledRSS",
            "policy": "Retain inherited center/conductor curvature floors and flat transition regularity;omit only principal surface curvature times width authoring/rejection. Measure and retain that legacy finding separately.",
            "unchanged_limitation": "Three constant-ruling turns with four flat ruling transitions;no continuous bend/twist-ratio transition implemented.",
            "coverage": "Eight examined development configurations,no holdouts/invalid controls;0native solid attempts,prediction unknown.",
            "stop": "Source/control/material invariant/API/resource failure;no local repair or renewed search.",
        },
        "rows": [
            {
                "number": i + 9,
                "baseline_number": i + 1,
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
    numerical_started = perf_counter()

    def checkpoint() -> None:
        """
        Enforce the numerical and host budget before scheduling the next round.
        """
        budget.check("joint_round")
        if perf_counter() - numerical_started >= 10:
            raise RuntimeError("Numerical budget reached.")

    try:
        for case, row in zip(inputs, state["rows"]):
            checkpoint()
            if _sources() != sources:
                raise RuntimeError("Source drift.")
            started = perf_counter()
            plan, counters = construct(case, checkpoint=checkpoint, travel_policy=minimum_travel)
            row.update(
                counters,
                solved=True,
                solve_seconds=perf_counter() - started,
                endpoint_gap_mm=plan.endpoint_gap_mm,
                connected=plan.connected,
                updates=plan.updates,
                termination=plan.termination,
            )
            _plans.append(plan)
            started = perf_counter()
            row.update(audit(case, plan))
            if max(row["endpoint_tangent_error"], row["endpoint_width_error"]) > 1e-8:
                row["findings"].append("ordered endpoint frame not reached")
            row["legacy_findings"] = list(row["findings"])
            row["findings"] = [
                f for f in row["findings"] if f != "analytic principal surface curvature limit"
            ]
            row.update(
                {
                    "overall": "failed" if row["findings"] else "unresolved",
                    "audited": True,
                    "audit_seconds": perf_counter() - started,
                }
            )
            if (
                row["analytic_maximum_curvature_ratio"] > 0.8
                or row["minimum_material_jacobian"] <= 0
                or row["sampled_material_speed_error"] > 1e-8
                or plan.lane_curvature_bound_per_mm > 1 / (3 * case.diameter_mm)
            ):
                raise RuntimeError("Retained material invariant contradicted:" + case.name)
            if (
                case.name in ("control", "reference_broad_return", "smooth_S_event_control")
                and row["overall"] == "failed"
            ):
                raise RuntimeError("Control regression:" + case.name)
            started = perf_counter()
            observations.append(inspect(plan.strip))
            row["observer_seconds"] = perf_counter() - started
        state["numerical_seconds"] = perf_counter() - numerical_started
        checkpoint()
        display_started = perf_counter()
        parent = root.occurrences.addNewComponent(adsk.core.Matrix3D.create()).component
        parent.name = NAME
        pitch = float(baseline["display_pitch_cm"])
        for index, (case, plan, row, observation) in enumerate(
            zip(inputs, _plans, state["rows"], observations)
        ):
            budget.check("draw_" + case.name)
            if perf_counter() - display_started >= 30 or _sources() != sources:
                raise RuntimeError("Drawing budget/source gate.")
            started = perf_counter()
            matrix = adsk.core.Matrix3D.create()
            matrix.translation = adsk.core.Vector3D.create(
                (index % 3) * pitch, -(3 + index // 3) * pitch, 0
            )
            component = parent.occurrences.addNewComponent(matrix).component
            component.name = f"{index + 9:02d} - {case.name} - {row['overall']}"
            target_native._display_paths(component, case, plan)
            annotate(component, index + 9, plan.strip, observation)
            row.update({"drawn": True, "draw_seconds": perf_counter() - started})
        state["drawing_seconds"] = perf_counter() - display_started
        if state["drawing_seconds"] >= 30:
            raise RuntimeError("Drawing budget exceeded.")
        app.activeViewport.fit()
        app.activeViewport.refresh()
        budget.check("archive")
        started = perf_counter()
        directory = (
            PROJECT_ROOT
            / "artifacts/verification/ribbon_cap_transition/surface_ablation"
            / uuid4().hex
        )
        directory.mkdir(parents=True)
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "paths.png"), 1800, 1200):
            raise RuntimeError("Ablation image export failed.")
        state.update(
            {
                "directory": str(directory),
                "display_pitch_cm": pitch,
                "archive_seconds": perf_counter() - started,
            }
        )
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        state["stop_reason"] = str(error)
    state.update(
        {
            "overall_seconds": perf_counter() - budget.started,
            "cpu_seconds": process_time() - cpu_started,
            "maximum_sampled_rss_kib": max(
                cast(int, sample["rss_kib"]) for sample in budget.samples
            ),
            "final_rss_kib": resident_kib(),
        }
    )
    return state
