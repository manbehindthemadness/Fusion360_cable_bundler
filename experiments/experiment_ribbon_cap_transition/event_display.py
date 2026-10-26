"""
Add visible example IDs and sparse observational labels without splitting path curves.
"""

from __future__ import annotations

from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

from .event_labels import EventKind, EventReadout
from .material_strip import MaterialStrip
from .trace_sweep_native import _point


def _text(sketch: Any, text: str, x: float, y: float, height: float) -> None:
    """
    Add one visible planar annotation using Fusion's text expression API.
    """
    text_input = sketch.sketchTexts.createInput3(
        "'" + text + "'", adsk.core.ValueInput.createByReal(height)
    )
    placed = text_input.setAsMultiLine(
        adsk.core.Point3D.create(x, y, 0),
        adsk.core.Point3D.create(x + 5, y + 2, 0),
        adsk.core.HorizontalAlignments.LeftHorizontalAlignment,
        adsk.core.VerticalAlignments.TopVerticalAlignment,
        0,
    )
    if not placed or sketch.sketchTexts.add(text_input) is None:
        raise RuntimeError("Conceptual event text annotation failed.")


def annotate(component: Any, number: int, strip: MaterialStrip, readout: EventReadout) -> None:
    """
    Number the whole example and show up to six edge-proxy region labels.

    A/B are permanent material sides, not renamed conductors. EQ means equal
    edge-curvature proxy during motion; N means sampled straight motion. Labels
    and construction leaders are annotations, not physical event boundaries.
    Full label sequences remain in the numerical readout when six markers omit
    additional regions. Center and edge splines are never split or rewritten.
    """
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketch.name = f"Example {number:02d} - conceptual labels only, no geometric segmentation"
    start = strip.jet(0)[0]
    _text(sketch, f"{number:02d}", start.x / 10 - 3, start.y / 10 - 5, 0.9)
    names = {EventKind.A: "A", EventKind.B: "B", EventKind.BALANCED: "EQ", EventKind.STRAIGHT: "N"}
    for index, region in enumerate(readout.edge_regions[:6]):
        point = strip.jet((region.start_mm + region.end_mm) / 2)[0]
        x, y = point.x / 10, point.y / 10 + 2 + (index % 2) * 1.5
        _text(sketch, names[region.kind], x, y, 0.35)
        leader = sketch.sketchCurves.sketchLines.addByTwoPoints(
            sketch.modelToSketchSpace(_point(point)), adsk.core.Point3D.create(x, y, 0)
        )
        if leader is None:
            raise RuntimeError("Conceptual event annotation leader failed.")
        leader.isConstruction = True
    sketch.isLightBulbOn = True
