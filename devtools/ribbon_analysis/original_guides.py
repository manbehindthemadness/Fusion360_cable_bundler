"""
Retain inspectable native routes alongside each frozen analysis result.

These sketches reproduce the measured cubic guides, including failed endpoints.
They are not repaired routes, conductor sweeps or physical compliance evidence.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

# noinspection PyUnresolvedReferences
import adsk.core

from .api import Evidence
from .provenance import mark_loaded
from .traces import TracePath

_GROUP = "RibbonAnalysisOriginal"
_NAMES = {-1: "A boundary", 0: "Center trajectory", -2: "B boundary"}


def _author(component: Any, evidence: Evidence, guide: TracePath) -> tuple[Any, float]:
    """
    Author one hidden fixed spline and verify its component-local translation.

    Mark incomplete sketches before API calls so a failure cannot be silently
    retried as a duplicate. Native point checks do not certify ribbon mechanics.
    """
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketch.name = f"{evidence.identifier} - Original {_NAMES[guide.number]}"
    sketch.isLightBulbOn = False
    sketch.attributes.add(_GROUP, "identity", f"{evidence.fingerprint}:{guide.number}")
    points = [
        sketch.modelToSketchSpace(adsk.core.Point3D.create(p.x / 10, p.y / 10, p.z / 10))
        for p in guide.controls
    ]
    curve = adsk.core.NurbsCurve3D.createNonRational(points, 3, list(guide.knots), False)
    if curve is None:
        raise RuntimeError("Original route NURBS creation failed.")
    entity = sketch.sketchCurves.sketchFixedSplines.addByNurbsCurve(curve)
    if entity is None:
        raise RuntimeError("Original route sketch creation failed.")
    evaluator = entity.geometry.evaluator
    ok, low, high = evaluator.getParameterExtents()
    if not ok:
        raise RuntimeError("Original route parameter domain is unavailable.")
    maximum = 0.0
    for u in (0.0, *((i + 0.5) / 32 for i in range(32)), 1.0):
        ok, point = evaluator.getPointAtParameter(low + (high - low) * u)
        if not ok:
            raise RuntimeError("Original route point evaluation failed.")
        actual = sketch.sketchToModelSpace(point)
        index = min(int(u * len(guide.curves)), len(guide.curves) - 1)
        expected = guide.curves[index].point(u * len(guide.curves) - index)
        error = (
            sum(
                (getattr(actual, axis) * 10 - getattr(expected, axis)) ** 2
                for axis in ("x", "y", "z")
            )
            ** 0.5
        )
        maximum = max(maximum, error)
    if maximum > 1e-7:
        raise RuntimeError("Original route native translation exceeds 1e-7 mm.")
    sketch.attributes.add(_GROUP, "point_error_mm", repr(maximum))
    return sketch, maximum


def retain_guides(
    component: Any, evidence: Evidence, checkpoint: Callable[[], None] = lambda: None
) -> dict[str, Any]:
    """
    Retain A, center and B as separate hidden sketches from immutable guide data.

    Reuse matching completed sketches without changing user visibility. Reject
    partial or duplicate records instead of retrying failed native authoring.
    Returns handles and separate authoring time/error; caller owns work limits.
    """
    if len(evidence.guides) != 3 or {g.number for g in evidence.guides} != set(_NAMES):
        raise ValueError("Original route geometry requires A, center and B guides.")
    started = perf_counter()
    retained: dict[int, Any] = {}
    maximum = 0.0
    for guide in evidence.guides:
        checkpoint()
        identity = f"{evidence.fingerprint}:{guide.number}"
        matching = []
        for sketch in component.sketches:
            stamp = sketch.attributes.itemByName(_GROUP, "identity")
            if stamp is not None and stamp.value == identity:
                matching.append(sketch)
        if len(matching) > 1:
            raise RuntimeError("Duplicate original route sketches require review.")
        if matching:
            sketch = matching[0]
            checked = sketch.attributes.itemByName(_GROUP, "point_error_mm")
            if checked is None:
                raise RuntimeError("Incomplete original route sketch requires review.")
            error = float(checked.value)
        else:
            sketch, error = _author(component, evidence, guide)
        retained[guide.number] = sketch
        maximum = max(maximum, error)
    return {
        "original_guides": retained,
        "original_guide_seconds": perf_counter() - started,
        "original_guide_maximum_error_mm": maximum,
    }


mark_loaded(__file__)
