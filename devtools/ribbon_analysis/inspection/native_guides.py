"""
Retain selected replay cubics as hidden native sketches without rerunning geometry.
"""

from __future__ import annotations

from typing import Any, Callable

# noinspection PyUnresolvedReferences
import adsk.core

from .archive import snapshot_payload
from .geometry import PathSnapshot


def retain(component: Any, snapshot: PathSnapshot, checkpoint: Callable[[], None]) -> None:
    """
    Author the exact frozen guide controls within a new disposable replay scene.

    Each attempt is stamped before spline creation. Validate native point mapping
    independently; no route repair, solver evaluation or body construction occurs.
    Existing scenes are never reused or retried by this function.
    """
    digest = snapshot_payload(snapshot)["sha256"]
    for trace in snapshot.guides:
        checkpoint()
        sketch = component.sketches.add(component.xYConstructionPlane)
        sketch.name = f"Original frozen guide {trace.number} / {snapshot.identifier}"
        sketch.isLightBulbOn = False
        sketch.attributes.add("RibbonInspection", "source", f"{digest}:{trace.number}")
        points = [
            sketch.modelToSketchSpace(adsk.core.Point3D.create(p.x / 10, p.y / 10, p.z / 10))
            for p in trace.controls
        ]
        curve = adsk.core.NurbsCurve3D.createNonRational(points, 3, list(trace.knots), False)
        if curve is None:
            raise RuntimeError("Frozen guide NURBS creation failed.")
        entity = sketch.sketchCurves.sketchFixedSplines.addByNurbsCurve(curve)
        if entity is None:
            raise RuntimeError("Frozen guide sketch creation failed.")
        ok, low, high = entity.geometry.evaluator.getParameterExtents()
        if not ok:
            raise RuntimeError("Frozen guide native parameter range is unavailable.")
        maximum = 0.0
        for i in range(33):
            u = i / 32
            ok, point = entity.geometry.evaluator.getPointAtParameter(low + (high - low) * u)
            if not ok:
                raise RuntimeError("Frozen guide native point evaluation failed.")
            actual = sketch.sketchToModelSpace(point)
            index = min(int(u * len(trace.curves)), len(trace.curves) - 1)
            expected = trace.curves[index].point(u * len(trace.curves) - index)
            maximum = max(
                maximum,
                sum(
                    (getattr(actual, axis) * 10 - getattr(expected, axis)) ** 2
                    for axis in ("x", "y", "z")
                )
                ** 0.5,
            )
        if maximum > 1e-7:
            raise RuntimeError("Frozen guide native translation exceeds 1e-7mm.")
        sketch.attributes.add("RibbonInspection", "point_error_mm", repr(maximum))
