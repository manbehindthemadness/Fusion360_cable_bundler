"""
Run two frozen continuation stages on all retained spatial edge refinements.

No boundary or acceptance change. Each stage restarts the declared damped update
from its predecessor;this expands warm-start search depth,not independent coverage.
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

from . import edge_opt_native
from .edge_display import draw
from .edge_first import EdgeCandidate
from .edge_optimization import improve
from .native_budget import NativeBudget, resident_kib

NAME = "Two edge continuation stages - paths50-54"
STAGES = 2
_state: dict[str, Any] | None = None
_candidates: list[EdgeCandidate] = []
_stages: list[list[EdgeCandidate]] = []


# noinspection PyProtectedMember
def _sources() -> dict[str, str]:
    """
    Fingerprint this adapter together with the unchanged refinement implementation.
    """
    path = Path(__file__)
    return {
        **edge_opt_native._sources(),
        str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest(),
    }


# noinspection PyProtectedMember
def run() -> dict[str, Any]:
    """
    Continue at most two stages,holding any fully compatible case unchanged.

    Up to10new warm refinements,49screens of33stations each plus257station
    audits;490screenings max. Final5displays only,all intermediate outcomes kept.
    Offset bounds are relative to each stage seed,so cumulative search extent
    increases;fixed targets,curvature,sphere and regularity rules do not change.
    Limits10s math/30s draw/60s overall/2GiB sampledRSS,no solids or local retries.
    """
    global _state, _candidates
    if _state is not None:
        raise RuntimeError("Edge continuation already started.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle owned scratch.")
    root = design.rootComponent
    if (
        root.occurrences.count != 6
        or root.occurrences.item(5).component.name != edge_opt_native.NAME
    ):
        raise RuntimeError("Retained interior-refinement array unavailable.")
    baseline = edge_opt_native._state
    if baseline is None or baseline["stop_reason"] is not None:
        raise RuntimeError("Completed first interior refinement required.")
    sources = _sources()
    if any(sources.get(p) != digest for p, digest in baseline["plan"]["sources"].items()):
        raise RuntimeError("Refinement source drift.")
    current = list(edge_opt_native._candidates)
    if len(current) != 5:
        raise RuntimeError("Five complete spatial seeds required.")
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    cpu_started = process_time()
    state: dict[str, Any] = {
        "plan": {
            "algorithm": "boundary-preserving-LM-continuation-v1",
            "sources": sources,
            "inputs": deepcopy(baseline["plan"]["inputs"]),
            "baseline_rows": deepcopy(baseline["rows"]),
            "procedure": "Two additional6round stages on all5cached spatial seeds. Same49screenings/33stations plus257audit per stage. Each seed-relative displacement[-1,1]chordunits;damping reinitialized as declared by improve. Fully compatible cases held unchanged. Exact endpoints/first3derivatives preserved. Draw only final5,retain both stage outcomes.",
            "limits": "10refinements/490screenings max,5native path displays,0solids/retries,10s math/30s draw/60s total/2GiB sampledRSS",
            "scope": "Same8development configurations,3controls cached;additional search depth,not new coverage or cold-start transfer evidence.",
            "hypothesis": "A little more boundary-preserving interior freedom may remove the residual folding without relaxing geometric checks.",
        },
        "controls": deepcopy(baseline["controls"]),
        "rows": [
            {
                "stage": stage + 1,
                "case": seed.case.name,
                "evaluated": False,
                "drawn": False,
                "overall": "unattempted",
            }
            for stage in range(STAGES)
            for seed in current
        ],
        "stop_reason": None,
    }
    _state = state
    math_started = perf_counter()
    last_rss = math_started

    def checkpoint() -> None:
        """
        Bound each numerical launch while sampling host memory every quarter-second.
        """
        nonlocal last_rss
        elapsed = perf_counter() - math_started
        if elapsed >= 10:
            raise RuntimeError("Numerical continuation budget reached.")
        if perf_counter() - last_rss >= 0.25:
            budget.check("continuation_screen")
            last_rss = perf_counter()

    try:
        final_rows: list[dict[str, Any]] = []
        for stage in range(STAGES):
            next_candidates = []
            _stages.append(next_candidates)
            stage_rows = []
            for case_index, seed in enumerate(current):
                checkpoint()
                if _sources() != sources:
                    raise RuntimeError("Source drift.")
                started = perf_counter()
                if seed.companion_allowed:
                    candidate, attempted, evaluations = seed, False, 0
                else:
                    if seed.curve is None:
                        raise RuntimeError("Spatial seed lacks its boundary.")
                    candidate, counters = improve(seed.case, seed.curve, checkpoint)
                    evaluations, attempted = counters["evaluations"], True
                row = state["rows"][stage * len(current) + case_index]
                row.update(
                    candidate.metrics,
                    evaluated=True,
                    attempted=attempted,
                    evaluations=evaluations,
                    stage_seconds=perf_counter() - started,
                    companion_allowed=candidate.companion_allowed,
                    overall="unresolved" if candidate.companion_allowed else "failed",
                )
                stage_rows.append(row)
                next_candidates.append(candidate)
            current, final_rows = next_candidates, stage_rows
        _candidates = current
        state["numerical_seconds"] = perf_counter() - math_started
        checkpoint()
        display_started = perf_counter()
        pitch = float(baseline["display_pitch_cm"])
        origin = adsk.core.Matrix3D.create()
        origin.translation = adsk.core.Vector3D.create(0, -14 * pitch, 0)
        parent = root.occurrences.addNewComponent(origin).component
        parent.name = NAME
        for index, (candidate, row) in enumerate(zip(current, final_rows)):
            budget.check("draw_" + str(index + 50))
            drawing_elapsed = perf_counter() - display_started
            if drawing_elapsed >= 30 or _sources() != sources:
                raise RuntimeError("Drawing budget/source gate.")
            started = perf_counter()
            placement = adsk.core.Matrix3D.create()
            placement.translation = adsk.core.Vector3D.create(index * pitch, 0, 0)
            occurrence = parent.occurrences.addNewComponent(placement)
            component = occurrence.component
            component.name = f"{index + 50:02d} - {candidate.case.name} - {row['overall']}"
            draw(component, candidate, index + 50)
            row.update(drawn=True, number=index + 50, draw_seconds=perf_counter() - started)
        state["drawing_seconds"] = perf_counter() - display_started
        if state["drawing_seconds"] >= 30:
            raise RuntimeError("Drawing budget exceeded.")
        app.activeViewport.fit()
        app.activeViewport.refresh()
        budget.check("archive")
        archive_started = perf_counter()
        directory = (
            PROJECT_ROOT
            / "artifacts/verification/ribbon_cap_transition/edge_continuation"
            / uuid4().hex
        )
        directory.mkdir(parents=True)
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "paths.png"), 1800, 1200):
            raise RuntimeError("Continuation image export failed.")
        state.update(
            directory=str(directory),
            display_pitch_cm=pitch,
            archive_seconds=perf_counter() - archive_started,
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
