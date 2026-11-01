"""
Retain inspectable guides and measured bend reductions on newly owned native results.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.constraint_geometry import Overlay
from devtools.ribbon_analysis.solver_details import retain_solver_details
from experiments.experiment_optional_appearance.host import capture
from experiments.experiment_ribbon_contraction.display import DisplaySource, retain_guides
from experiments.experiment_ribbon_contraction.runner import restore


def show_case(run_path: str, case_id: str) -> None:
    """
    Add original guides, preserve native geometry and leave changed bodies visible.
    """
    run = Path(run_path)
    plan = json.loads((run / "plan.json").read_text())
    root_path = Path(plan["root"])
    native = json.loads((run / f"{case_id}-native.json").read_text())
    if native["status"] != "built_and_named_fidelity_checks_pass":
        return
    app = adsk.core.Application.get()
    if (
        app.activeDocument.creationId != "86e5d125-ed43-4b89-b175-dcca0966fae6"
        or app.userInterface.activeCommand != "SelectCommand"
    ):
        raise RuntimeError("Review requires the owned idle design")
    root = adsk.fusion.Design.cast(app.activeProduct).rootComponent
    matches = [o for o in root.occurrences if o.component.name == native["component"]]
    if len(matches) != 1:
        raise RuntimeError("Expected unique new native result")
    occurrence = matches[0]
    body = occurrence.component.bRepBodies.item(0)
    if body.revisionId != native["revision"]:
        raise RuntimeError("Review body changed")
    entry = next(item for item in plan["cases"] if item["id"] == case_id)
    route = restore(json.loads((root_path / entry["contracted"]).read_text()))
    numerical = json.loads((root_path / plan["numerical_results"]).read_text())
    row = next(item for item in numerical["cases"] if item["id"] == case_id)
    budget = NativeBudget(maximum_seconds=45, maximum_rss_kib=4194304)
    budget.check("review launch")
    maximum = retain_guides(occurrence.component, route, budget)
    evidence = DisplaySource(case_id, plan["sources"][entry["contracted"]])
    overlay = Overlay(
        "solver_limits",
        "Algebraic bend simplification",
        (("folds_removed", row["baseline_folds"] - row["final_folds"]),),
        (),
        (
            f"Bends {row['baseline_folds']} -> {row['final_folds']}; faces {native['original_face_count']} -> {native['face_count']}",
            f"Length {row['baseline_length_mm']:.3f} -> {row['final_length_mm']:.3f} mm",
            f"Bend rewrite and closure {row['reduction_seconds']:.4f}s; native generation {native['generation_seconds']:.3f}s",
            "Exact crease rule exhausted; no global minimum claim",
        ),
        Vector3(route.targets.start.x, route.targets.start.y + 10, 0),
    )
    panel = retain_solver_details(
        occurrence.component, evidence, overlay, lambda: budget.check("review panel")
    )
    # The user requested a clean geometry view; retain the panel for inspection.
    panel.isLightBulbOn = False
    body.isLightBulbOn = True
    occurrence.isLightBulbOn = True
    camera = app.activeViewport.camera
    capture(app, occurrence, run / f"{case_id}-visible.png")
    if case_id != "calibration":
        app.activeViewport.camera = camera
    if body.revisionId != native["revision"]:
        raise RuntimeError("Review changed body revision")
    result: dict[str, Any] = {
        "id": case_id,
        "body_visible": body.isVisible,
        "revision_unchanged": True,
        "native_guide_error_mm": maximum,
        "sketches": occurrence.component.sketches.count,
        "elapsed_seconds": budget.clock() - budget.started,
        "rss_samples": budget.samples,
    }
    (run / f"{case_id}-review.json").write_text(json.dumps(result, indent=2))
