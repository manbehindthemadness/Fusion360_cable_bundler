"""
Refine five retained edge seeds while preserving exact terminal boundary data.

All three analytic controls stay cached and visible. One bounded warm-started
refinement per spatial configuration;no solids or automatic retries.
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

from . import edge_speed_native
from .edge_display import draw
from .edge_first import EdgeCandidate
from .edge_optimization import improve
from .native_budget import NativeBudget, resident_kib

NAME = "Compatible edge interior refinement - paths45-49"
EDGE_PATH = "experiments/experiment_ribbon_cap_transition/edge_first.py"
OLD_EDGE_HASH = "881d9bc37e46715cf7e68c41b2baec05cf71b3363c5cf5c1a859c83f925bd26d"
_state: dict[str, Any] | None = None
_candidates: list[EdgeCandidate] = []


# noinspection PyProtectedMember
def _sources() -> dict[str, str]:
    """
    Freeze inherited sources and both new refinement modules.
    """
    inherited = edge_speed_native._sources()
    for name in ("edge_optimization.py", "edge_opt_native.py"):
        path = Path(__file__).with_name(name)
        inherited[str(path.relative_to(PROJECT_ROOT))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    return inherited


# noinspection PyProtectedMember
def run() -> dict[str, Any]:
    """
    Refine five cached seeds and independently audit their companion permission.

    Five spatial poses plus three cached controls account for8development inputs.
    Up to6rounds/49screenings of33stations per spatial case,then257station audit;
    exact terminal data remain structural.10s math/30s draw/60s total/2GiB RSS.
    Stop source/resource/API/harness failure,with no local retry or state reset.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Interior edge refinement already started.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle experimental scratch.")
    root = design.rootComponent
    if (
        root.occurrences.count != 5
        or root.occurrences.item(4).component.name != edge_speed_native.NAME
    ):
        raise RuntimeError("Retained speed-grid array unavailable.")
    baseline = edge_speed_native._state
    if baseline is None or baseline["stop_reason"] is not None:
        raise RuntimeError("Complete speed grid unavailable.")
    if baseline["plan"]["sources"].get(EDGE_PATH) != OLD_EDGE_HASH:
        raise RuntimeError("Unexpected prior edge implementation.")
    sources = _sources()
    if any(
        sources.get(p) != digest
        for p, digest in baseline["plan"]["sources"].items()
        if p != EDGE_PATH
    ):
        raise RuntimeError("Unreviewed inherited source drift.")
    selected: list[int] = list(baseline["selected_indices"])
    seeds: list[EdgeCandidate] = [edge_speed_native._candidates[index] for index in selected]
    if len(seeds) != 5 or any(seed.curve is None for seed in seeds):
        raise RuntimeError("Five complete spatial seed curves required.")
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    cpu_started = process_time()
    state: dict[str, Any] = {
        "plan": {
            "algorithm": "boundary-preserving-interior-LM-v1",
            "hypothesis": "Interior boundary control freedom can reduce folding while exact edge targets/arrival frames are preserved structurally.",
            "inputs": deepcopy(baseline["plan"]["inputs"]),
            "sources": sources,
            "seed_rows": [deepcopy(baseline["rows"][index]) for index in selected],
            "procedure": "Elevate each selected cached degree7seed to degree9;moveonlyP4/P5(6coordinates),leaving first3endpoint derivatives fixed.6LMrounds,6forward probes(1e-4),2trials/round,49screenings max,33stations/screen. Log1p folding/center-curvature/three-guide-sphere violations plus0.001coordinate regularization. Jacobian0.1 is search goal,not acceptance. Stepnorm0.25,coords[-1,1]chordunits,strict objective improvement. Final unchanged257station physical-reference gate.",
            "limits": "5warm-started spatial refinements+3cached controls,245screenings max,no solids/retries,10s math/30s draw/60s total/2GiB sampledRSS",
            "scope": "Examined development seeds,not coldstarts/holdouts/generalized success. PermanentA,no outside-edge handoffs;native interpolation/full compliance unmeasured.",
            "reviewed_change": "edge_first permits degree9 and supplied reference_curve;default degree7/gates unchanged.",
        },
        "controls": deepcopy(baseline["controls"]),
        "rows": [
            {
                "number": 45 + i,
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
    last_memory_sample = numerical_started

    def checkpoint() -> None:
        """
        Check time every evaluation and sampled memory at least every0.25seconds.
        """
        nonlocal last_memory_sample
        now = perf_counter()
        if now - last_memory_sample >= 0.25:
            budget.check("edge_screen")
            last_memory_sample = now
        if now - numerical_started >= 10:
            raise RuntimeError("Numerical budget reached during interior refinement.")

    try:
        for seed, row in zip(seeds, state["rows"]):
            checkpoint()
            if _sources() != sources:
                raise RuntimeError("Source drift.")
            curve = seed.curve
            if curve is None:
                raise RuntimeError("Seed curve unavailable.")
            started = perf_counter()
            candidate, counters = improve(seed.case, curve, checkpoint)
            _candidates.append(candidate)
            row.update(
                candidate.metrics,
                evaluated=True,
                solve_and_audit_seconds=perf_counter() - started,
                companion_allowed=candidate.companion_allowed,
                overall="unresolved" if candidate.companion_allowed else "failed",
                evaluations=counters["evaluations"],
            )
        state["numerical_seconds"] = perf_counter() - numerical_started
        checkpoint()
        display_started = perf_counter()
        pitch = float(baseline["display_pitch_cm"])
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = adsk.core.Vector3D.create(0, -13 * pitch, 0)
        parent = root.occurrences.addNewComponent(matrix).component
        parent.name = NAME
        for i, (candidate, row) in enumerate(zip(_candidates, state["rows"])):
            budget.check("draw_" + str(row["number"]))
            if perf_counter() - display_started >= 30 or _sources() != sources:
                raise RuntimeError("Drawing budget/source gate.")
            started = perf_counter()
            placement = adsk.core.Matrix3D.create()
            placement.translation = adsk.core.Vector3D.create(i * pitch, 0, 0)
            component = parent.occurrences.addNewComponent(placement).component
            component.name = f"{row['number']:02d} - {candidate.case.name} - {row['overall']}"
            draw(component, candidate, row["number"])
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
            / "artifacts/verification/ribbon_cap_transition/edge_interior"
            / uuid4().hex
        )
        directory.mkdir(parents=True)
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "paths.png"), 1800, 1200):
            raise RuntimeError("Interior edge image export failed.")
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
