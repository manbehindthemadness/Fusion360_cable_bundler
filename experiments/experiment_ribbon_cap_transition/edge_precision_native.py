"""
Apply one denser correction step with conservative search margins to all five edges.

Final physical-reference gates stay unchanged;this is warm development refinement,
not a tolerance adjustment or a new set of independent cases.
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

from . import edge_freedom_native
from .edge_display import draw
from .edge_first import EdgeCandidate
from .edge_optimization import PRECISION, improve
from .native_budget import NativeBudget, resident_kib

NAME = "Dense edge correction - paths65-69"
OPT_PATH = "experiments/experiment_ribbon_cap_transition/edge_optimization.py"
OLD_OPT_HASH = "7d9fc38781e37814220e8ac327d3dc4601f0dc9853a419290f17b40305368ce4"
_state: dict[str, Any] | None = None
_candidates: list[EdgeCandidate] = []


# noinspection PyProtectedMember
def _sources() -> dict[str, str]:
    """
    Fingerprint this adapter and the reviewed precision-policy extension.
    """
    current_path = Path(__file__)
    relative = str(current_path.relative_to(PROJECT_ROOT))
    return {
        **edge_freedom_native._sources(),
        relative: hashlib.sha256(current_path.read_bytes()).hexdigest(),
    }


# noinspection PyProtectedMember
def run() -> dict[str, Any]:
    """
    Run one12coordinate LM round per case,129screen stations and257final stations.

    Up to15screenings/case,75batch;searchgoals center.78,lane3.1diameters,sphere
    .98times allowed radius. Final gates remain center.8,lane3diameters,original
    sphere,positiveJacobian and exact endpoints.10s math/30s draw/60s total/2GiB
    sampledRSS,0solids/retries. Stop resource/source/API/harness failure.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Dense edge correction already started.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle scratch.")
    root = design.rootComponent
    if (
        root.occurrences.count != 9
        or root.occurrences.item(8).component.name != edge_freedom_native.NAME
    ):
        raise RuntimeError("Retained four-control array unavailable.")
    baseline = edge_freedom_native._state
    if baseline is None or baseline["stop_reason"] is not None:
        raise RuntimeError("Completed four-control baseline required.")
    if baseline["plan"]["sources"].get(OPT_PATH) != OLD_OPT_HASH:
        raise RuntimeError("Unexpected prior optimizer implementation.")
    sources = _sources()
    if any(
        sources.get(p) != digest
        for p, digest in baseline["plan"]["sources"].items()
        if p != OPT_PATH
    ):
        raise RuntimeError("Unreviewed source drift.")
    seeds = list(edge_freedom_native._candidates)
    if len(seeds) != 5:
        raise RuntimeError("Five complete seeds required.")
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    cpu_started = process_time()
    state: dict[str, Any] = {
        "plan": {
            "algorithm": "boundary-preserving-precision-LM-v1",
            "sources": sources,
            "inputs": deepcopy(baseline["plan"]["inputs"]),
            "baseline_rows": deepcopy(baseline["rows"]),
            "hypothesis": "A denser step with conservative search goals leaves enough geometric margin for the final dense audit without relaxing physical limits.",
            "procedure": "PRECISION registered policy,degree11fourinteriorcontrols/12coordinates,oneLMround(15screensmax),129stations. Searchgoals center.78,lane3.1D,sphere.98radius,Jgoal.1. Same final257station criteria center.8,lane3D,sphere1.0radius,J>0,exact terminal data. Same seed-relativebounds and step.25.",
            "limits": "5warm spatial cases+3cached controls,75screensmax,0solids/retries,5native path displays,10s math/30s draw/60s total/2GiB sampledRSS",
            "scope": "Same8examined development configurations,not holdouts/coldstarts/generalized success. All previous failures preserved;native full compliance unmeasured.",
        },
        "controls": deepcopy(baseline["controls"]),
        "rows": [
            {
                "number": 65 + i,
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
    math_started = perf_counter()
    sampled_at = math_started

    def checkpoint() -> None:
        """
        Check elapsed time per screen and sampled host memory every quarter-second.
        """
        nonlocal sampled_at
        now = perf_counter()
        if now - math_started >= 10:
            raise RuntimeError("Dense correction numerical budget reached.")
        if now - sampled_at >= 0.25:
            budget.check("precision_screen")
            sampled_at = now

    try:
        for index, seed in enumerate(seeds):
            row = state["rows"][index]
            curve = seed.curve
            if curve is None:
                raise RuntimeError("Dense correction seed boundary unavailable.")
            checkpoint()
            current_sources = _sources()
            if current_sources != sources:
                raise RuntimeError("Source drift.")
            started = perf_counter()
            candidate, counters = improve(seed.case, curve, checkpoint, policy=PRECISION)
            _candidates.append(candidate)
            row.update(candidate.metrics)
            row["evaluated"] = True
            row["solve_and_audit_seconds"] = perf_counter() - started
            row["companion_allowed"] = candidate.companion_allowed
            row["evaluations"] = counters["evaluations"]
            row["overall"] = "unresolved" if candidate.companion_allowed else "failed"
        state["numerical_seconds"] = perf_counter() - math_started
        checkpoint()
        drawing_started = perf_counter()
        pitch = float(baseline["display_pitch_cm"])
        placement = adsk.core.Matrix3D.create()
        placement.translation = adsk.core.Vector3D.create(0, -17 * pitch, 0)
        array = root.occurrences.addNewComponent(placement).component
        array.name = NAME
        for i, (candidate, row) in enumerate(zip(_candidates, state["rows"])):
            budget.check("draw_" + str(i + 65))
            if perf_counter() - drawing_started >= 30:
                raise RuntimeError("Dense correction drawing budget exceeded.")
            if _sources() != sources:
                raise RuntimeError("Dense correction source drift.")
            started = perf_counter()
            name = f"{i + 65:02d} - {candidate.case.name} - {row['overall']}"
            transform = adsk.core.Matrix3D.create()
            transform.translation = adsk.core.Vector3D.create(i * pitch, 0, 0)
            component = array.occurrences.addNewComponent(transform).component
            component.name = name
            draw(component, candidate, i + 65)
            row.update(drawn=True, draw_seconds=perf_counter() - started)
        state["drawing_seconds"] = perf_counter() - drawing_started
        if state["drawing_seconds"] >= 30:
            raise RuntimeError("Drawing budget exceeded.")
        app.activeViewport.fit()
        app.activeViewport.refresh()
        budget.check("archive")
        archive_started = perf_counter()
        directory = (
            PROJECT_ROOT
            / "artifacts/verification/ribbon_cap_transition/edge_precision"
            / uuid4().hex
        )
        directory.mkdir(parents=True)
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "paths.png"), 1800, 1200):
            raise RuntimeError("Dense correction image export failed.")
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
