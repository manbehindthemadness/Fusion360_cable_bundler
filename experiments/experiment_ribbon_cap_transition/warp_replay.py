"""
Validate and reference retained diagnostic contours without rebuilding their curves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import adsk.fusion

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame

from .curve_context import connected_curve_order, occurrence_curve
from .section_flex import FlexSection


def retained_path(
    component: adsk.fusion.Component,
    source: adsk.fusion.Sketch,
    occurrence: adsk.fusion.Occurrence,
    frame: RibbonFrame,
    flex: FlexSection,
    number: int,
) -> tuple[adsk.fusion.Sketch, adsk.fusion.Path, float]:
    """
    Verify all210 existing fit points against frozen math, then reference a closed Path.

    This validates authoring samples, not interpolation or mechanical compliance.
    Any unexpected topology or moved fit point stops replay; nothing is repaired.
    """
    matches = [s for s in component.sketches if s.name == f"Three-anchor flex section {number:02}"]
    if len(matches) != 1 or source.sketchCurves.sketchArcs.count != 42:
        raise RuntimeError("Retained section/source is missing or changed.")
    sketch = matches[0]
    splines = sketch.sketchCurves.sketchFittedSplines
    if splines.count != 42:
        raise RuntimeError("Retained spline topology changed.")
    maximum_error = 0.0
    for index, arc in enumerate(source.sketchCurves.sketchArcs):
        evaluator = arc.geometry.evaluator
        valid, start, stop = evaluator.getParameterExtents()
        if not valid or splines.item(index).fitPoints.count != 5:
            raise RuntimeError("Retained contour sampling structure changed.")
        for step in range(5):
            valid, point = evaluator.getPointAtParameter(start + (stop - start) * step / 4)
            if not valid:
                raise RuntimeError("Original arc sample unavailable.")
            world = source.sketchToModelSpace(point)
            offset = difference(Vector3(world.x * 10, world.y * 10, world.z * 10), frame.origin)
            expected = flex.point(dot(offset, frame.width), dot(offset, frame.thickness))
            actual = splines.item(index).fitPoints.item(step).worldGeometry
            error = magnitude(
                difference(Vector3(actual.x * 10, actual.y * 10, actual.z * 10), expected)
            )
            maximum_error = max(maximum_error, error)
    if maximum_error > 1e-7:
        raise RuntimeError("Retained native fit points differ from frozen warp math.")
    # noinspection PyUnresolvedReferences
    import adsk.core

    # noinspection PyUnresolvedReferences
    import adsk.fusion

    curves = adsk.core.ObjectCollection.create()
    for spline in connected_curve_order(splines):
        curves.add(occurrence_curve(spline, occurrence))
    path = adsk.fusion.Path.create(curves, adsk.fusion.ChainedCurveOptions.noChainedCurves)
    if path is None or path.count != 42 or not path.isClosed:
        raise RuntimeError("Retained contour Path is incomplete.")
    return sketch, path, maximum_error
