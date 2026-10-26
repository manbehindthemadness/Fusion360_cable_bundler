"""
Run one direct-edge construction per fixed pose,with gated companion drawing.

Retain all earlier arrays and evidence;five spatial curves are new,three exact
controls reused. No search,solid attempts,retries or report files.
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

from . import ablation_native
from .edge_display import draw
from .edge_first import EdgeCandidate, construct
from .event_cases import cases
from .native_budget import NativeBudget, resident_kib

NAME = "Edge-first arrival gate - paths17-24"
_state: dict[str, Any] | None = None
_candidates: list[EdgeCandidate] = []


# noinspection PyProtectedMember
def _sources() -> dict[str, str]:
    """
    Fingerprint inherited policy and all new edge-first sources before execution.
    """
    sources = ablation_native._sources()
    for name in ("edge_first.py", "edge_display.py", "edge_native.py"):
        path = Path(__file__).with_name(name)
        sources[str(path.relative_to(PROJECT_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return sources


# noinspection PyProtectedMember
def run() -> dict[str, Any]:
    """
    Evaluate eight unchanged poses once and retain all rejected companion gates.

    Direct curve closure is a boundary construction property,not evidence that
    physical routing is solved. Compatibility is sampled at257stations;native
    interpolation,elasticity,full width clearance and solids remain unmeasured.
    Limits are10s numerical/30s drawing/60s overall/2GiB sampledRSS;stop first
    harness,resource,source or retained-control regression without local retry.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Edge-first run already started;no replay.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle experimental scratch.")
    root = design.rootComponent
    if (
        root.occurrences.count != 2
        or root.occurrences.item(1).component.name != ablation_native.NAME
    ):
        raise RuntimeError("Expected the two retained comparison arrays.")
    baseline = ablation_native._state
    if baseline is None or baseline["stop_reason"] is not None:
        raise RuntimeError("Complete ablation baseline unavailable.")
    inputs, sources = cases(), _sources()
    if [asdict(case) for case in inputs] != baseline["plan"]["inputs"]:
        raise RuntimeError("Fixed endpoint input drift.")
    if any(sources.get(path) != digest for path, digest in baseline["plan"]["sources"].items()):
        raise RuntimeError("Inherited source drift.")
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    cpu_started = process_time()
    state: dict[str, Any] = {
        "plan": {
            "algorithm": "direct-A-boundary-first-v1",
            "hypothesis": "Fix A-edge arrival before companion work;derive developable companions only when edge frame supports positive finite-width material coordinates.",
            "inputs": [asdict(case) for case in inputs],
            "sources": sources,
            "baseline_rows": deepcopy(baseline["rows"]),
            "procedure": "Five direct degree7 spatial boundaries,three cached analytic controls. Speeds=D,accelerations=D*(W cross T),jerks=-D*T at endpoints. Frame W=Frenet binormal,eta=torsion/curvature. Positive sampled1+q*eta_s across q[-fullwidth,0] before companion derivation;retain center macaroni,three-guide radius/sphere and terminal frame checks.",
            "limits": "8fixed cases,one construction/case,no search/retries/solids,257compatibility stations/case,10s math/30s draw/60s total/2GiB sampledRSS",
            "scope": "Permanent A boundary reference,no turn-event handoffs.8development configurations,no holdouts or invalid controls. Exact edge arrival alone is not ribbon success;0native solid attempts.",
            "stop": "Source/resource/API/harness or retained-control regression;geometric compatibility rejection remains an explicit case outcome.",
            "renewal": "User explicitly authorized further iterations without repeated resource proposals;each batch remains bounded and preserves failures.",
        },
        "rows": [
            {
                "number": i + 17,
                "case": case.name,
                "evaluated": False,
                "drawn": False,
                "overall": "unattempted",
            }
            for i, case in enumerate(inputs)
        ],
        "stop_reason": None,
    }
    _state = state
    try:
        numerical_started = perf_counter()
        for index, (case, row) in enumerate(zip(inputs, state["rows"])):
            budget.check("edge_" + case.name)
            if perf_counter() - numerical_started >= 10 or _sources() != sources:
                raise RuntimeError("Numerical budget/source gate.")
            control = ablation_native._plans[index] if index in (2, 3, 7) else None
            started = perf_counter()
            candidate = construct(case, control)
            _candidates.append(candidate)
            row.update(
                candidate.metrics,
                evaluated=True,
                solve_and_audit_seconds=perf_counter() - started,
                companion_allowed=candidate.companion_allowed,
                overall="unresolved" if candidate.companion_allowed else "failed",
            )
            if control is not None and not candidate.companion_allowed:
                raise RuntimeError("Retained control regression:" + case.name)
        state["numerical_seconds"] = perf_counter() - numerical_started
        if state["numerical_seconds"] >= 10:
            raise RuntimeError("Numerical budget exceeded.")
        display_started = perf_counter()
        parent_matrix = adsk.core.Matrix3D.create()
        pitch = float(baseline["display_pitch_cm"])
        parent_matrix.translation = adsk.core.Vector3D.create(0, -6 * pitch, 0)
        parent = root.occurrences.addNewComponent(parent_matrix).component
        parent.name = NAME
        for index, (candidate, row) in enumerate(zip(_candidates, state["rows"])):
            budget.check("draw_" + candidate.case.name)
            if perf_counter() - display_started >= 30 or _sources() != sources:
                raise RuntimeError("Drawing budget/source gate.")
            started = perf_counter()
            matrix = adsk.core.Matrix3D.create()
            matrix.translation = adsk.core.Vector3D.create(
                (index % 3) * pitch, -(index // 3) * pitch, 0
            )
            occurrence = parent.occurrences.addNewComponent(matrix)
            component = occurrence.component
            component.name = f"{index + 17:02d} - {candidate.case.name} - {row['overall']}"
            draw(component, candidate, index + 17)
            row.update(drawn=True, draw_seconds=perf_counter() - started)
        state["drawing_seconds"] = perf_counter() - display_started
        if state["drawing_seconds"] >= 30:
            raise RuntimeError("Drawing budget exceeded.")
        app.activeViewport.fit()
        app.activeViewport.refresh()
        budget.check("archive")
        started = perf_counter()
        directory = (
            PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/edge_first" / uuid4().hex
        )
        directory.mkdir(parents=True)
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "paths.png"), 1800, 1200):
            raise RuntimeError("Edge-first image export failed.")
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
