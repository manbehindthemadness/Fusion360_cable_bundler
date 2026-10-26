"""
Compare three frozen endpoint-curvature policies across all five spatial poses.

Controls and the first direct-edge trial remain cached and visible. This is a
development shape comparison,not15independent configurations or an adaptive search.
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

from . import edge_native
from .edge_display import draw
from .edge_first import EdgeCandidate, construct
from .event_cases import cases
from .native_budget import NativeBudget, resident_kib

NAME = "Fixed edge curvature comparison - paths25-39"
RATIOS = (0.2, 0.4, 0.6)
EDGE_PATH = "experiments/experiment_ribbon_cap_transition/edge_first.py"
OLD_EDGE_HASH = "8835d21049ccdca4aff4a139840e6c282f758b6d74d99a9489c2af8118722526"
_state: dict[str, Any] | None = None
_candidates: list[EdgeCandidate] = []


# noinspection PyProtectedMember
def _sources() -> dict[str, str]:
    """
    Retain inherited sources and the reviewed fixed-shape comparison adapter.
    """
    sources = edge_native._sources()
    path = Path(__file__)
    sources[str(path.relative_to(PROJECT_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return sources


# noinspection PyProtectedMember
def run() -> dict[str, Any]:
    """
    Evaluate three declared curvature policies once on every spatial input.

    Keep three controls as cached comparison rows,without replaying their solves.
    Make15new edge constructions,no adaptive selection/repair/retries/solids.
    Use257stations/candidate,10s math/30s draw/60s overall/2GiB sampled RSS.
    Stop on source,resource or harness/API failure;retain compatibility rejections.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Fixed edge-shape comparison already started.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle owned scratch.")
    root = design.rootComponent
    if root.occurrences.count != 3 or root.occurrences.item(2).component.name != edge_native.NAME:
        raise RuntimeError("First edge array unavailable;no document deletion authorized.")
    baseline = edge_native._state
    if baseline is None or baseline["stop_reason"] is not None:
        raise RuntimeError("Complete first edge trial unavailable.")
    if baseline["plan"]["sources"].get(EDGE_PATH) != OLD_EDGE_HASH:
        raise RuntimeError("Unexpected original edge implementation.")
    sources = _sources()
    if any(
        sources.get(p) != digest
        for p, digest in baseline["plan"]["sources"].items()
        if p != EDGE_PATH
    ):
        raise RuntimeError("Unreviewed inherited source drift.")
    inputs = cases()
    spatial = [(i, case) for i, case in enumerate(inputs) if i not in (2, 3, 7)]
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    cpu_started = process_time()
    state: dict[str, Any] = {
        "plan": {
            "algorithm": "direct-edge-fixed-curvature-comparison-v1",
            "hypothesis": "Increasing prescribed endpoint bending within the retained curvature budget may spread frame rotation and improve finite-width compatibility.",
            "inputs": deepcopy(baseline["plan"]["inputs"]),
            "sources": sources,
            "baseline_rows": deepcopy(baseline["rows"]),
            "ratios": RATIOS,
            "procedure": "Endpoint speed D;curvature=ratio/reach;acceleration=D^2*k*(W cross T),jerk=-D^3*k^2*T. All15spatial variants frozen before evaluation;no result-driven selection. Same edge/compatibility gates as first trial. Cached controls retained separately.",
            "source_change": "Only optional endpoint-curvature parameter added to edge_first;original default arithmetic retained.",
            "limits": "8independent development configurations,15new spatial shapes plus3cached control rows,257stations/candidate,no search/retries/solids,10s math/30s draw/60s total/2GiB sampledRSS",
        },
        "controls": [deepcopy(baseline["rows"][i]) for i in (2, 3, 7)],
        "rows": [
            {
                "number": 25 + j * 5 + k,
                "case": case.name,
                "ratio": ratio,
                "evaluated": False,
                "drawn": False,
                "overall": "unattempted",
            }
            for j, ratio in enumerate(RATIOS)
            for k, (_, case) in enumerate(spatial)
        ],
        "stop_reason": None,
    }
    _state = state
    try:
        numerical_started = perf_counter()
        for row in state["rows"]:
            budget.check("shape_" + str(row["number"]))
            if perf_counter() - numerical_started >= 10 or _sources() != sources:
                raise RuntimeError("Numerical budget/source gate.")
            case = next(c for _, c in spatial if c.name == row["case"])
            started = perf_counter()
            candidate = construct(case, endpoint_ratio=row["ratio"])
            _candidates.append(candidate)
            row.update(
                candidate.metrics,
                evaluated=True,
                solve_and_audit_seconds=perf_counter() - started,
                companion_allowed=candidate.companion_allowed,
                overall="unresolved" if candidate.companion_allowed else "failed",
            )
        state["numerical_seconds"] = perf_counter() - numerical_started
        if state["numerical_seconds"] >= 10:
            raise RuntimeError("Numerical budget exceeded.")
        display_started = perf_counter()
        pitch = float(baseline["display_pitch_cm"])
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = adsk.core.Vector3D.create(0, -9 * pitch, 0)
        parent = root.occurrences.addNewComponent(matrix).component
        parent.name = NAME
        for i, (candidate, row) in enumerate(zip(_candidates, state["rows"])):
            budget.check("draw_" + str(row["number"]))
            if perf_counter() - display_started >= 30 or _sources() != sources:
                raise RuntimeError("Drawing budget/source gate.")
            started = perf_counter()
            placement = adsk.core.Matrix3D.create()
            placement.translation = adsk.core.Vector3D.create((i % 5) * pitch, -(i // 5) * pitch, 0)
            component = parent.occurrences.addNewComponent(placement).component
            component.name = f"{row['number']:02d} - ratio{row['ratio']} - {candidate.case.name} - {row['overall']}"
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
            PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/edge_shapes" / uuid4().hex
        )
        directory.mkdir(parents=True)
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "paths.png"), 1800, 1200):
            raise RuntimeError("Fixed edge-shape export failed.")
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
