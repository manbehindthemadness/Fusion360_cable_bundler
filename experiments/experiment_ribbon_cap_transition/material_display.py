"""
Draw center and true material-edge approximations in the owned Fusion scratch.
"""

from __future__ import annotations

from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

from .material_guides import spline_controls
from .material_strip import MaterialStrip
from .trace_sweep_native import _point


def curves(component: Any, strip: MaterialStrip) -> None:
    """
    Author three fixed cubic guide splines without profiles, sweeps or solids.
    """
    for name, offset in (
        ("Material center trajectory", 0.0),
        ("Negative material edge", -strip.half_width_mm),
        ("Positive material edge", strip.half_width_mm),
    ):
        sketch = component.sketches.add(component.xYConstructionPlane)
        sketch.name = name + " - cubic approximation, not a compliance certificate"
        points, knots = spline_controls(strip, offset)
        native = [sketch.modelToSketchSpace(_point(point)) for point in points]
        curve = adsk.core.NurbsCurve3D.createNonRational(native, 3, list(knots), False)
        if curve is None or sketch.sketchCurves.sketchFixedSplines.addByNurbsCurve(curve) is None:
            raise RuntimeError("Material guide spline construction failed.")
        sketch.isLightBulbOn = True
