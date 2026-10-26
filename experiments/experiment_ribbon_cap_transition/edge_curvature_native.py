"""
Apply the denser all-lane curvature objective to every retained spatial edge.

All endpoint and final-audit constraints are unchanged. This is one more bounded
warm development stage,with three cached controls and full prior evidence kept.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
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

from . import edge_continue_native
from .edge_display import draw
from .edge_first import EdgeCandidate
from .edge_optimization import improve
from .native_budget import NativeBudget, resident_kib

NAME = "All-lane edge curvature refinement - paths55-59"
OPT_PATH = "experiments/experiment_ribbon_cap_transition/edge_optimization.py"
OLD_OPT_HASH = "a67df6b9450ec8858e43ec0586ec5ddc27ea0333cd5f43351d259042a1c95c96"
_state: dict[str, Any] | None = None
_candidates: list[EdgeCandidate] = []


# noinspection PyProtectedMember
def _sources() -> dict[str, str]:
    """
    Include this adapter and the explicitly reviewed objective change.
    """
    source_path = Path(__file__)
    inherited = edge_continue_native._sources()
    relative = str(source_path.relative_to(PROJECT_ROOT))
    return {**inherited, relative: hashlib.sha256(source_path.read_bytes()).hexdigest()}


# noinspection PyProtectedMember
def run() -> dict[str, Any]:
    """
    Refine all five warm seeds once,then apply the original dense companion gate.

    Same6rounds/49screens per case,now65stations with lane-radius objective;
    final257station acceptance unchanged.245screens max,0solids/retries,
    10s math/30s drawing/60s total/2GiB sampledRSS. Stop source/resource/API or
    harness failure without replacing prior failures or unattempted case rows.
    """
    global _state
    if _state is not None:
        raise RuntimeError("All-lane edge refinement already started.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle experimental scratch.")
    root = design.rootComponent
    if (
        root.occurrences.count != 7
        or root.occurrences.item(6).component.name != edge_continue_native.NAME
    ):
        raise RuntimeError("Retained edge continuation array unavailable.")
    baseline = edge_continue_native._state
    if baseline is None or baseline["stop_reason"] is not None:
        raise RuntimeError("Complete continuation baseline required.")
    if baseline["plan"]["sources"].get(OPT_PATH) != OLD_OPT_HASH:
        raise RuntimeError("Unexpected previous objective implementation.")
    sources = _sources()
    if any(
        sources.get(p) != digest
        for p, digest in baseline["plan"]["sources"].items()
        if p != OPT_PATH
    ):
        raise RuntimeError("Unreviewed inherited source drift.")
    seeds = list(edge_continue_native._candidates)
    if len(seeds) != 5:
        raise RuntimeError("Five complete seed curves required.")
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    cpu_started = process_time()
    state: dict[str, Any] = {
        "plan": {
            "algorithm": "boundary-preserving-all-lane-LM-v2",
            "sources": sources,
            "inputs": deepcopy(baseline["plan"]["inputs"]),
            "baseline_rows": deepcopy(baseline["rows"]),
            "hypothesis": "Matching the screening objective to lane radius and increasing sampling resolves the remaining curvature failures without sacrificing fixed arrival.",
            "procedure": "Same degree9 six-coordinate interior update,6rounds/49screens max. Objective now65stations and explicit minimum-Jacobian lane radius penalty;folding/center curvature/sphere/regularization unchanged. Final257station physical-reference gates unchanged. Seed-relative displacement bounds explicitly permit another warm stage.",
            "limits": "5warm spatial refinements+3cached controls,245screens max of65stations plus257finalaudit/case,5native path displays,0solids/retries,10s math/30s draw/60s total/2GiB sampledRSS",
            "scope": "Same8development configurations,no holdouts/coldstarts or outside-edge handoffs;native cubic/full cable compliance unmeasured.",
        },
        "controls": deepcopy(baseline["controls"]),
        "rows": [
            {
                "number": 55 + i,
                "case": seed.case.name,
                "evaluated": False,
                "drawn": False,
                "overall": "unattempted",
            }
            for i, seed in enumerate(seeds)
        ],
        "stop_reason": None,
    }
    _state = state
    numerical_started = perf_counter()
    memory_sample_time = numerical_started

    def checkpoint() -> None:
        """
        Check numerical time on every launch and sample memory every quarter-second.
        """
        nonlocal memory_sample_time
        now = perf_counter()
        if now - numerical_started >= 10:
            raise RuntimeError("All-lane numerical budget reached.")
        if now - memory_sample_time >= 0.25:
            budget.check("all_lane_screen")
            memory_sample_time = now

    try:
        for seed, row in zip(seeds, state["rows"]):
            checkpoint()
            if _sources() != sources:
                raise RuntimeError("Source drift.")
            if seed.curve is None:
                raise RuntimeError("Seed boundary unavailable.")
            started = perf_counter()
            candidate, counters = improve(seed.case, seed.curve, checkpoint)
            _candidates.append(candidate)
            row.update(
                candidate.metrics,
                evaluated=True,
                solve_and_audit_seconds=perf_counter() - started,
                companion_allowed=candidate.companion_allowed,
                evaluations=counters["evaluations"],
                overall="unresolved" if candidate.companion_allowed else "failed",
            )
        state["numerical_seconds"] = perf_counter() - numerical_started
        checkpoint()
        display_started = perf_counter()
        pitch = float(baseline["display_pitch_cm"])
        origin = adsk.core.Matrix3D.create()
        origin.translation = adsk.core.Vector3D.create(0, -15 * pitch, 0)
        parent = root.occurrences.addNewComponent(origin).component
        parent.name = NAME
        for index, (candidate, row) in enumerate(zip(_candidates, state["rows"])):
            budget.check("draw_" + str(index + 55))
            elapsed = perf_counter() - display_started
            if elapsed >= 30 or _sources() != sources:
                raise RuntimeError("Drawing budget/source gate.")
            started = perf_counter()
            label = f"{index + 55:02d} - {candidate.case.name} - {row['overall']}"
            placement = adsk.core.Matrix3D.create()
            placement.translation = adsk.core.Vector3D.create(index * pitch, 0, 0)
            component = parent.occurrences.addNewComponent(placement).component
            component.name = label
            draw(component, candidate, index + 55)
            row.update(drawn=True, draw_seconds=perf_counter() - started)
        state["drawing_seconds"] = perf_counter() - display_started
        if state["drawing_seconds"] >= 30:
            raise RuntimeError("Drawing budget exceeded.")
        app.activeViewport.fit()
        app.activeViewport.refresh()
        budget.check("archive")
        started = perf_counter()
        directory = (
            PROJECT_ROOT
            / "artifacts/verification/ribbon_cap_transition/edge_all_lane"
            / uuid4().hex
        )
        directory.mkdir(parents=True)
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "paths.png"), 1800, 1200):
            raise RuntimeError("All-lane edge image export failed.")
        state.update(
            directory=str(directory),
            display_pitch_cm=pitch,
            archive_seconds=perf_counter() - started,
        )
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        state["stop_reason"] = str(error)
    state.update(
        overall_seconds=perf_counter() - budget.started,
        cpu_seconds=process_time() - cpu_started,
        maximum_sampled_rss_kib=max(cast(int, s["rss_kib"]) for s in budget.samples),
        final_rss_kib=resident_kib(),
    )
    return state
