"""
Redraw the five frozen precision candidates and measure native interpolation error.

Requires the retained precision and failed64interval audit in the owned scratch.
No new route solve, acceptance-policy change, solids or report files.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from time import perf_counter
from typing import Any, cast
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_production_split_ribbon.sources import PROJECT_ROOT
from experiments.experiment_ribbon_diagnosis.storage import archive

from . import edge_curve_audit, edge_precision_native
from .edge_display import draw
from .edge_native_checks import audit_curves, curve_findings
from .native_budget import NativeBudget

NAME = "Native interpolation512 - paths70-74"
DISPLAY_PATH = "experiments/experiment_ribbon_cap_transition/edge_display.py"
OLD_DISPLAY_HASH = "6fa5eb25304ee99e198e1e0435c06d6685c5d42cc2f52474bd3216f0b991f6c3"
_state: dict[str, Any] | None = None


# noinspection PyProtectedMember
def run() -> dict[str, Any]:
    """
    Draw512interval copies,then audit the three paths of reference-passing73.

    Five reused spatial configurations,three cached controls,zero new solves.
    Bounds:30s drawing,10s audit,60s overall,2GiB sampledRSS. Preserve partial
    evidence and stop on source/API/resource failure;no automatic retry.
    """
    global _state
    if _state is not None:
        raise RuntimeError("Interpolation comparison already started.")
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    baseline = edge_precision_native._state
    previous = edge_curve_audit._state
    if design is None or app.userInterface.activeCommand != "SelectCommand":
        raise RuntimeError("Expected idle owned scratch.")
    if baseline is None or baseline["stop_reason"] or previous is None or previous["stop_reason"]:
        raise RuntimeError("Completed precision and native audit required.")
    root = design.rootComponent
    if (
        root.occurrences.count != 10
        or root.occurrences.item(9).component.name != edge_precision_native.NAME
    ):
        raise RuntimeError("Expected retained ten arrays.")
    old = baseline["plan"]["sources"]
    sources = edge_precision_native._sources()
    if old.get(DISPLAY_PATH) != OLD_DISPLAY_HASH or any(
        sources.get(p) != h for p, h in old.items() if p != DISPLAY_PATH
    ):
        raise RuntimeError("Unreviewed inherited source drift.")
    for name in ("edge_interpolation.py", "edge_native_checks.py", "edge_interpolation_native.py"):
        path = Path(__file__).with_name(name)
        sources[str(path.relative_to(PROJECT_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    candidates = edge_precision_native._candidates
    if len(candidates) != 5 or not candidates[3].companion_allowed:
        raise RuntimeError("Expected five frozen candidates,quarter-minus reference pass.")
    budget = NativeBudget(maximum_seconds=60)
    budget.check("start")
    state: dict[str, Any] = {
        "plan": {
            "sources": sources,
            "intervals": 512,
            "new_solves": 0,
            "baseline_numbers": [65, 66, 67, 68, 69],
            "cached_controls": baseline["controls"],
            "limits": "30s draw/10s audit/60s overall/2GiB RSS;0solids/retries/reports",
        },
        "rows": [],
        "native_curves": [],
        "stop_reason": None,
        "findings": [],
        "overall": "unresolved",
    }
    _state = state
    try:
        pitch = float(baseline["display_pitch_cm"])
        transform = adsk.core.Matrix3D.create()
        transform.translation = adsk.core.Vector3D.create(0, -18 * pitch, 0)
        array = root.occurrences.addNewComponent(transform).component
        array.name = NAME
        drawing_started = perf_counter()
        audit_component = None
        for i, candidate in enumerate(candidates):
            budget.check("draw")
            if perf_counter() - drawing_started >= 30:
                raise RuntimeError("Interpolation drawing cap reached.")
            for path, digest in sources.items():
                if hashlib.sha256((PROJECT_ROOT / path).read_bytes()).hexdigest() != digest:
                    raise RuntimeError("Source drift during interpolation comparison.")
            started = perf_counter()
            placement = adsk.core.Matrix3D.create()
            placement.translation = adsk.core.Vector3D.create(i * pitch, 0, 0)
            component = array.occurrences.addNewComponent(placement).component
            component.name = f"{i + 70:02d} - {candidate.case.name} - native512 unresolved"
            draw(component, candidate, i + 70, intervals=512)
            state["rows"].append(
                {
                    "number": i + 70,
                    "case": candidate.case.name,
                    "draw_seconds": perf_counter() - started,
                    "reference_pass": candidate.companion_allowed,
                    "native_audit": "pending" if i == 3 else "unattempted:reference failed",
                }
            )
            if i == 3:
                audit_component = component
        state["drawing_seconds"] = perf_counter() - drawing_started
        if state["drawing_seconds"] >= 30 or audit_component is None:
            raise RuntimeError("Drawing incomplete or over budget.")
        audit_started = perf_counter()

        def checkpoint() -> None:
            """
            Enforce the focused native audit bound independently of drawing.
            """
            budget.check("native_audit")
            if perf_counter() - audit_started >= 10:
                raise RuntimeError("Native interpolation audit cap reached.")

        audit_curves(audit_component, candidates[3].case, 512, checkpoint, state["native_curves"])
        state["audit_seconds"] = perf_counter() - audit_started
        rows = state["native_curves"]
        if len(rows) != 3:
            raise RuntimeError("Expected three native paths.")
        state["findings"].extend(curve_findings(rows))
        state["rows"][3]["native_audit"] = (
            "failed" if state["findings"] else "sampled curve gates pass;full compliance unresolved"
        )
        budget.check("archive")
        directory = (
            PROJECT_ROOT
            / "artifacts/verification/ribbon_cap_transition/edge_interpolation"
            / uuid4().hex
        )
        directory.mkdir(parents=True)
        app.activeViewport.fit()
        app.activeViewport.refresh()
        archive(design, directory / "candidates.f3d")
        if not app.activeViewport.saveAsImageFile(str(directory / "paths.png"), 1800, 1200):
            raise RuntimeError("Interpolation image export failed.")
        state["directory"] = str(directory)
        budget.check("complete")
    except (RuntimeError, ValueError, TypeError, AttributeError) as error:
        state["stop_reason"] = str(error)
    state["overall_seconds"] = perf_counter() - budget.started
    state["maximum_sampled_rss_kib"] = max(cast(int, s["rss_kib"]) for s in budget.samples)
    return state
