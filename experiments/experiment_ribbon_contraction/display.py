"""
Retain frozen contraction guides and measurements without rebuilding native bodies.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.constraint_geometry import Overlay
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from devtools.ribbon_analysis.solver_details import retain_solver_details
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.material_native import native_point

from .runner import restore


@dataclass(frozen=True)
class DisplaySource:
    """
    Identify the immutable route and numerical evidence shown by the native panel.
    """

    identifier: str
    fingerprint: str


def retain_guides(component: Any, route: FoldRoute, budget: NativeBudget) -> float:
    """
    Retain three hidden piecewise cubic guides with unchanged material side identity.

    Match the existing0.025radian Hermite display policy, split at each lane's
    physical fold boundaries. Native samples compare to the analytic material map;
    this is a display approximation check, not another physical route audit.
    """
    maximum = 0.0
    for name, q in (
        ("Left", route.half_width_mm),
        ("Center", 0.0),
        ("Right", -route.half_width_mm),
    ):
        budget.check("retain original material guide")
        matches = [s for s in component.sketches if s.name == "Original material guide " + name]
        if len(matches) > 1:
            raise RuntimeError("Duplicate original guide sketches")
        existing = bool(matches)
        sketch = matches[0] if existing else component.sketches.add(component.xYConstructionPlane)
        if existing and sketch.sketchCurves.sketchFixedSplines.count != len(route.pieces):
            raise RuntimeError("Incomplete original guide requires review")
        if not existing:
            sketch.name = "Original material guide " + name
            sketch.isLightBulbOn = False
        for index, piece in enumerate(route.pieces):
            budget.check("author original guide piece")
            geometry = piece.geometry
            breaks = [0.0, 1.0]
            if isinstance(geometry, CylindricalFold):
                low, high = geometry.bend_interval(q)
                count = math.ceil(abs(geometry.angle_radians) / 0.025)
                breaks = sorted(
                    {
                        0.0,
                        1.0,
                        *(
                            min(1.0, max(0.0, low + (high - low) * i / count))
                            for i in range(count + 1)
                        ),
                    }
                )
            controls = []
            for first, last in zip(breaks, breaks[1:]):
                point, velocity, _, _ = piece.surface(first, q)
                end, end_velocity, _, _ = piece.surface(last, q)
                if not controls:
                    controls.append(native_point(point))
                controls.extend(
                    (
                        native_point(point.translated(velocity, (last - first) / 3)),
                        native_point(end.translated(end_velocity, -(last - first) / 3)),
                        native_point(end),
                    )
                )
            knots = [0.0] * 4 + [value for value in breaks[1:-1] for _ in range(3)] + [1.0] * 4
            if existing:
                entity = sketch.sketchCurves.sketchFixedSplines.item(index)
            else:
                curve = adsk.core.NurbsCurve3D.createNonRational(controls, 3, knots, False)
                if curve is None:
                    raise RuntimeError("Original material guide curve unavailable")
                entity = sketch.sketchCurves.sketchFixedSplines.addByNurbsCurve(curve)
            if entity is None:
                raise RuntimeError("Original material guide sketch unavailable")
            for u in (0.0, 0.17, 0.53, 0.91, 1.0):
                ok, actual = entity.geometry.evaluator.getPointAtParameter(u)
                if not ok:
                    raise RuntimeError("Original material guide evaluation failed")
                maximum = max(maximum, actual.distanceTo(native_point(piece.surface(u, q)[0])) * 10)
    if maximum > 1e-6:
        raise RuntimeError("Original guide display approximation exceeds1e-6mm")
    return maximum


def annotate(run_path: str) -> None:
    """
    Add guides and visible measurement panels to four owned immutable results once.
    """
    run = Path(run_path)
    plan = json.loads((run / "plan.json").read_text())
    root_path = Path(plan["root"])
    budget = NativeBudget(maximum_seconds=120, maximum_rss_kib=4194304)
    budget.check("launch annotation")
    if budget.memory() >= 3984588:
        raise RuntimeError("Annotation launch RSS headroom")
    for relative, digest in plan["sources"].items():
        if hashlib.sha256((root_path / relative).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Annotation source drift: " + relative)
    app = adsk.core.Application.get()
    if (
        app.activeDocument.creationId != "86e5d125-ed43-4b89-b175-dcca0966fae6"
        or app.userInterface.activeCommand != "SelectCommand"
    ):
        raise RuntimeError("Annotation requires owned idle design")
    root = adsk.fusion.Design.cast(app.activeProduct).rootComponent
    numerical = json.loads(
        (root_path / "artifacts/verification/ribbon_contract258/result.json").read_text()
    )
    records = []
    try:
        for row in numerical["cases"]:
            budget.check("annotate case")
            native = json.loads(
                (
                    root_path / f"artifacts/verification/ribbon_contract259/{row['id']}-native.json"
                ).read_text()
            )
            occurrences = [o for o in root.occurrences if o.component.name == native["component"]]
            if len(occurrences) != 1:
                raise RuntimeError("Owned native result missing or duplicated")
            component = occurrences[0].component
            body = component.bRepBodies.item(0)
            if body.revisionId != native["revision"]:
                raise RuntimeError("Native body changed")
            route_path = (
                root_path / f"artifacts/verification/ribbon_contract258/{row['id']}-contracted.json"
            )
            route = restore(json.loads(route_path.read_text()))
            maximum = retain_guides(component, route, budget)
            evidence = DisplaySource(row["id"], hashlib.sha256(route_path.read_bytes()).hexdigest())
            overlay = Overlay(
                "solver_limits",
                "Deterministic straight contraction",
                (("gain_mm", row["gain_mm"]),),
                (),
                (
                    f"Length: {row['baseline_length_mm']:.3f} -> {row['final_length_mm']:.3f} mm ({row['gain_percent']:.2f}% shorter)",
                    "4 accepted updates; iteration budget reached; minimum not established",
                    f"Contraction: {row['contraction_seconds']:.3f}s; generation: {native['generation_seconds']:.3f}s",
                    "Fold geometry and face count unchanged; named fidelity checks pass",
                ),
                Vector3(route.targets.start.x, route.targets.start.y + 10, 0),
            )
            retain_solver_details(
                component, evidence, overlay, lambda: budget.check("measurement panel")
            )
            if body.revisionId != native["revision"]:
                raise RuntimeError("Annotations changed native body")
            records.append(
                {
                    "id": row["id"],
                    "native_guide_maximum_error_mm": maximum,
                    "sketches": component.sketches.count,
                    "body_revision_unchanged": True,
                }
            )
    finally:
        (run / "result.json").write_text(
            json.dumps(
                {
                    "cases": records,
                    "unattempted_or_incomplete": [
                        row["id"]
                        for row in numerical["cases"]
                        if row["id"] not in {item["id"] for item in records}
                    ],
                    "elapsed_seconds": time.perf_counter() - budget.started,
                    "rss_samples": budget.samples,
                },
                indent=2,
            )
        )
    print(json.dumps(records))
