"""
Compare four free interior controls against the retained two-control edge family.

Five warm spatial cases and three cached controls,no new independent coverage.
All hard endpoint and material-reference gates remain unchanged.
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

from . import edge_curvature_native
from .edge_display import draw
from .edge_first import EdgeCandidate
from .edge_optimization import EXPANDED, improve
from .native_budget import NativeBudget, resident_kib

NAME = "Four-control edge family - paths60-64"
REVIEWED_BASELINE = {
    "experiments/experiment_ribbon_cap_transition/edge_first.py": "0db7bf66e132f3a7fa51a7043e22b65b987385702eb25555abd108639ef5ea4d",
    "experiments/experiment_ribbon_cap_transition/edge_optimization.py": "4c520c710e38ccdc13fc4adaabfb2f29d03cf1cb5ec8abf30ca2b5fe056ebade",
}
_state: dict[str, Any] | None = None
_candidates: list[EdgeCandidate] = []


# noinspection PyProtectedMember
def _sources() -> dict[str, str]:
    """
    Fingerprint the reviewed degree/freedom extension and this adapter.
    """
    path = Path(__file__)
    return {
        **edge_curvature_native._sources(),
        str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest(),
    }


# noinspection PyProtectedMember
def run() -> dict[str, Any]:
    """
    Make one three-round expanded-family refinement on every spatial seed.

    Twelve coordinates,12forward probes+2trials/round,43screens/case of65stations;
    Keep257station final gates,215screenings max batch,0solids/retries.
    Limits are10s math/30s drawing/60s total/2GiB sampledRSS. Stop source/resource/
    API/harness failure and preserve every partial/unattempted row.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Expanded edge-family experiment already started.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle experimental scratch.")
    root = design.rootComponent
    if (
        root.occurrences.count != 8
        or root.occurrences.item(7).component.name != edge_curvature_native.NAME
    ):
        raise RuntimeError("Retained all-lane edge array unavailable.")
    baseline = edge_curvature_native._state
    if baseline is None or baseline["stop_reason"] is not None:
        raise RuntimeError("Complete all-lane baseline required.")
    sources = _sources()
    for path, digest in baseline["plan"]["sources"].items():
        if path in REVIEWED_BASELINE:
            if digest != REVIEWED_BASELINE[path]:
                raise RuntimeError("Unexpected reviewed baseline:" + path)
        elif sources.get(path) != digest:
            raise RuntimeError("Unreviewed source drift:" + path)
    seeds = list(edge_curvature_native._candidates)
    if len(seeds) != 5:
        raise RuntimeError("Five complete spatial seeds required.")
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    cpu_started = process_time()
    state: dict[str, Any] = {
        "plan": {
            "algorithm": "boundary-preserving-four-control-LM-v1",
            "sources": sources,
            "inputs": deepcopy(baseline["plan"]["inputs"]),
            "baseline_rows": deepcopy(baseline["rows"]),
            "hypothesis": "Four free degree11interior controls provide local shape freedom that the two-control degree9family lacked,while terminal derivatives remain exact.",
            "procedure": "Elevate cached degree9to11;freeP4..P7(12coordinates),preserve terminal derivatives throughthirdorder. EXPANDED policy3LMrounds,43screens max of65stations then unchanged257audit. Same objective and physical criteria,step.25,seedrelativebounds[-1,1]chordunits. This changes representation/searchbudget explicitly.",
            "limits": "5warm spatial cases+3cached controls,215screens max,no solids/retries,5path displays,10s math/30s draw/60s total/2GiB RSS",
            "scope": "Same8examined development configurations,no holdouts/coldstarts/eventhandoffs. Native interpolation/thickness/full compliance unmeasured.",
        },
        "controls": deepcopy(baseline["controls"]),
        "rows": [
            {
                "number": 60 + i,
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
    last_sample = numerical_started

    def checkpoint() -> None:
        """
        Check time per screening and sampled memory every quarter-second.
        """
        nonlocal last_sample
        now = perf_counter()
        if now - numerical_started >= 10:
            raise RuntimeError("Expanded-family numerical budget reached.")
        if now - last_sample >= 0.25:
            budget.check("expanded_screen")
            last_sample = now

    try:
        for seed, row in zip(seeds, state["rows"]):
            checkpoint()
            if _sources() != sources:
                raise RuntimeError("Source drift.")
            if seed.curve is None:
                raise RuntimeError("Seed boundary unavailable.")
            started = perf_counter()
            candidate, counters = improve(seed.case, seed.curve, checkpoint, policy=EXPANDED)
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
        placement = adsk.core.Matrix3D.create()
        placement.translation = adsk.core.Vector3D.create(0, -16 * pitch, 0)
        parent = root.occurrences.addNewComponent(placement).component
        parent.name = NAME
        for i, (candidate, row) in enumerate(zip(_candidates, state["rows"])):
            budget.check("draw_" + str(i + 60))
            if perf_counter() - display_started >= 30:
                raise RuntimeError("Expanded-family drawing budget exceeded.")
            if _sources() != sources:
                raise RuntimeError("Source drift during expanded drawing.")
            started = perf_counter()
            label = f"{i + 60:02d} - {candidate.case.name} - {row['overall']}"
            transform = adsk.core.Matrix3D.create()
            transform.translation = adsk.core.Vector3D.create(i * pitch, 0, 0)
            component = parent.occurrences.addNewComponent(transform).component
            component.name = label
            draw(component, candidate, i + 60)
            row.update(drawn=True, draw_seconds=perf_counter() - started)
        state["drawing_seconds"] = perf_counter() - display_started
        if state["drawing_seconds"] >= 30:
            raise RuntimeError("Drawing budget exceeded.")
        app.activeViewport.fit()
        app.activeViewport.refresh()
        budget.check("archive")
        started = perf_counter()
        directory = (
            PROJECT_ROOT / "artifacts/verification/ribbon_cap_transition/edge_freedom" / uuid4().hex
        )
        directory.mkdir(parents=True)
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "paths.png"), 1800, 1200):
            raise RuntimeError("Expanded-family image export failed.")
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
