"""
Draw frozen unconstrained guides beside current and changed native ribbon results.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.graphics import draw_lines
from experiments.experiment_optional_appearance.host import capture
from experiments.experiment_ribbon_fold_route.material_native import native_point

from .guide import Guide


def _draw(component: Any, guide: Guide, budget: NativeBudget) -> float:
    """
    Retain one exact native cubic plus magenta display polyline; refuse duplicate work.
    """
    name = "Reference - Unconstrained endpoint spline270"
    if any(sketch.name == name for sketch in component.sketches):
        raise RuntimeError("Reference spline already drawn; no automatic duplicate/retry")
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketch.name = name
    sketch.isLightBulbOn = False
    curve = adsk.core.NurbsCurve3D.createNonRational(
        [native_point(p) for p in guide.controls], 3, [0.0] * 4 + [1.0] * 4, False
    )
    if curve is None:
        raise RuntimeError("Reference cubic unavailable")
    entity = sketch.sketchCurves.sketchFixedSplines.addByNurbsCurve(curve)
    if entity is None:
        raise RuntimeError("Reference spline sketch unavailable")
    maximum = 0.0
    for i in range(17):
        budget.check("compare native reference spline")
        u = i / 16
        ok, actual = entity.geometry.evaluator.getPointAtParameter(u)
        if not ok:
            raise RuntimeError("Reference spline evaluator unavailable")
        maximum = max(maximum, actual.distanceTo(native_point(guide.sample(u)[0])) * 10)
    if maximum > 1e-8:
        raise ArithmeticError("Reference spline differs from frozen guide")
    group = component.customGraphicsGroups.add()
    draw_lines(
        group,
        tuple(guide.sample(i / 128)[0] for i in range(129)),
        (220, 35, 180),
        "Unconstrained endpoint guide - magenta",
    )
    return maximum


def show(run_path: str) -> None:
    """
    Annotate only pinned owned results, capture every comparison and focus Gym3.

    No solves, body construction, appearances or body edits occur. Old views and
    visibility remain intact; only new guides and the camera change. Native cubic
    sketches start hidden, while their magenta graphics are visible for reference.
    """
    run = Path(run_path)
    plan = json.loads((run / "plan.json").read_text())
    root_path = Path(plan["root"])
    budget = NativeBudget(maximum_seconds=120, maximum_rss_kib=4194304)
    budget.check("guide display launch")
    if budget.memory() >= 3984588:
        raise RuntimeError("Reference display launch headroom")
    for relative, digest in plan["sources"].items():
        if hashlib.sha256((root_path / relative).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Reference display source drift: " + relative)
    app = adsk.core.Application.get()
    if (
        app.activeDocument.creationId != "86e5d125-ed43-4b89-b175-dcca0966fae6"
        or app.userInterface.activeCommand != "SelectCommand"
    ):
        raise RuntimeError("Reference display requires the owned idle design")
    root = adsk.fusion.Design.cast(app.activeProduct).rootComponent
    output: dict[str, Any] = {
        "cases": [],
        "unattempted": [item["id"] for item in plan["cases"]],
        "solves": 0,
        "native_builds": 0,
    }
    try:
        for entry in plan["cases"]:
            budget.check("draw reference comparison")
            payload = json.loads((root_path / entry["guide"]).read_text())
            guide = Guide(
                tuple(Vector3(**p) for p in payload["controls"]),
                tuple(payload["parameters"]),
                tuple(payload["distances"]),
            )
            record: dict[str, Any] = {"id": entry["id"], "variants": []}
            output["cases"].append(record)
            for variant in entry["variants"]:
                native = json.loads((root_path / variant["native"]).read_text())
                matches = [o for o in root.occurrences if o.component.name == native["component"]]
                if len(matches) != 1:
                    raise RuntimeError("Reference result missing or duplicated")
                occurrence = matches[0]
                body = occurrence.component.bRepBodies.item(0)
                if body.revisionId != native["revision"]:
                    raise RuntimeError("Reference body changed")
                error = _draw(occurrence.component, guide, budget)
                if not body.isVisible:
                    raise RuntimeError("Reference comparison body is hidden")
                capture(app, occurrence, run / f"{entry['id']}-{variant['label']}.png")
                if body.revisionId != native["revision"]:
                    raise RuntimeError("Reference drawing changed body revision")
                record["variants"].append(
                    {
                        "label": variant["label"],
                        "component": native["component"],
                        "guide_error_mm": error,
                        "revision_unchanged": True,
                    }
                )
            output["unattempted"].remove(entry["id"])
        output["status"] = "completed"
    finally:
        output.update(elapsed_seconds=time.monotonic() - budget.started, rss_samples=budget.samples)
        (run / "result.json").write_text(json.dumps(output, indent=2))
