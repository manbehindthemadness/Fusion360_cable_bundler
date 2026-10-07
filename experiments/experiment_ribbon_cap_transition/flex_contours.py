"""
Translate fixed mathematical section flex into diagnostic nonplanar loft paths.
"""

from __future__ import annotations

import math

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame

from .curve_context import connected_curve_order, occurrence_curve
from .section_flex import FlexSection


def guide_tangent(spline: adsk.fusion.SketchFittedSpline, index: int) -> Vector3:
    """
    Evaluate the existing physical guide at its exact station fit point.
    """
    evaluator = spline.worldGeometry.evaluator
    point = spline.fitPoints.item(index).worldGeometry
    valid, parameter = evaluator.getParameterAtPoint(point)
    if not valid:
        raise RuntimeError("Guide station parameter unavailable.")
    valid, derivative = evaluator.getFirstDerivative(parameter)
    if not valid:
        raise RuntimeError("Guide station derivative unavailable.")
    return unit(Vector3(derivative.x, derivative.y, derivative.z))


def flex_contour(
    component: adsk.fusion.Component,
    source: adsk.fusion.Sketch,
    frame: RibbonFrame,
    flex: FlexSection,
    number: int,
    occurrence: adsk.fusion.Occurrence,
) -> tuple[adsk.fusion.Sketch, adsk.fusion.Path, dict[str, object]]:
    """
    Fit five points per original arc, sharing endpoints in one closed 3D path.

    This is a native interpolation approximation, not the exact mapped contour.
    Preserve original cap sketches by referencing their original curves. All Path
    entities have explicit owned occurrence context, without geometric copies.
    Retain new diagnostic sketches on failure; never flatten or retry them.
    """
    curves = adsk.core.ObjectCollection.create()
    if number in (1, 32):
        for arc in connected_curve_order(source.sketchCurves.sketchArcs):
            curves.add(occurrence_curve(arc, occurrence))
        path = adsk.fusion.Path.create(curves, adsk.fusion.ChainedCurveOptions.noChainedCurves)
        if path is None or path.count != 42 or not path.isClosed:
            raise RuntimeError("Original terminal contour path unavailable.")
        return source, path, {"section": number, "exact_terminal": True}
    name = f"Three-anchor flex section {number:02}"
    existing = [sketch for sketch in component.sketches if sketch.name == name]
    if existing and (number != 2 or len(existing) != 1):
        raise RuntimeError("Unexpected existing flex contour; no reconstruction.")
    retained = existing[0] if existing else None
    sketch = (
        retained if retained is not None else component.sketches.add(component.xYConstructionPlane)
    )
    if retained is None:
        sketch.name = name
        sketch.isComputeDeferred = True
    elif sketch.sketchCurves.sketchFittedSplines.count != 42:
        raise RuntimeError("Retained contour topology changed.")
    endpoints: dict[tuple[float, float, float], adsk.fusion.SketchPoint] = {}
    maximum_displacement = 0.0
    maximum_fit_error = 0.0
    maximum_plane_departure = 0.0
    try:
        for arc_index, arc in enumerate(source.sketchCurves.sketchArcs):
            retained_spline = (
                sketch.sketchCurves.sketchFittedSplines.item(arc_index)
                if retained is not None
                else None
            )
            evaluator = arc.geometry.evaluator
            valid, start, stop = evaluator.getParameterExtents()
            if not valid:
                raise RuntimeError("Original contour parameter range unavailable.")
            points = adsk.core.ObjectCollection.create()
            mapped_points = []
            for step in range(5):
                valid, original = evaluator.getPointAtParameter(start + (stop - start) * step / 4)
                if not valid:
                    raise RuntimeError("Original contour sample unavailable.")
                world = source.sketchToModelSpace(original)
                nominal = Vector3(world.x * 10, world.y * 10, world.z * 10)
                offset = difference(nominal, frame.origin)
                mapped = flex.point(dot(offset, frame.width), dot(offset, frame.thickness))
                mapped_points.append(mapped)
                maximum_displacement = max(
                    maximum_displacement, magnitude(difference(mapped, nominal))
                )
                maximum_plane_departure = max(
                    maximum_plane_departure,
                    abs(dot(difference(mapped, frame.origin), frame.tangent)),
                )
                key = (round(mapped.x, 10), round(mapped.y, 10), round(mapped.z, 10))
                local = sketch.modelToSketchSpace(
                    adsk.core.Point3D.create(mapped.x / 10, mapped.y / 10, mapped.z / 10)
                )
                if step in (0, 4):
                    if key not in endpoints:
                        endpoints[key] = (
                            retained_spline.fitPoints.item(step)
                            if retained_spline is not None
                            else sketch.sketchPoints.add(local)
                        )
                    points.add(endpoints[key])
                else:
                    points.add(local)
            spline = (
                retained_spline
                if retained_spline is not None
                else sketch.sketchCurves.sketchFittedSplines.add(points)
            )
            if spline is None or spline.fitPoints.count != 5:
                raise RuntimeError("Flex contour interpolation failed.")
            for index, expected in enumerate(mapped_points):
                actual = spline.fitPoints.item(index).worldGeometry
                error = magnitude(
                    difference(Vector3(actual.x * 10, actual.y * 10, actual.z * 10), expected)
                )
                maximum_fit_error = max(maximum_fit_error, error)
    finally:
        if retained is None:
            sketch.isComputeDeferred = False
    if len(endpoints) != 42:
        raise RuntimeError("Flex contour endpoint topology changed.")
    if maximum_fit_error > 1e-7:
        raise RuntimeError("Native contour differs from fixed mathematical fit points.")
    for spline in connected_curve_order(sketch.sketchCurves.sketchFittedSplines):
        curves.add(occurrence_curve(spline, occurrence))
    path = adsk.fusion.Path.create(curves, adsk.fusion.ChainedCurveOptions.noChainedCurves)
    if path is None or path.count != 42 or not path.isClosed:
        raise RuntimeError("Nonplanar contour path unavailable/incomplete.")
    ratios = []
    for lane in range(18):
        x = (lane - 9) * 1.5
        ratios.append(magnitude(difference(flex.point(x + 1.5, 0), flex.point(x, 0))) / 1.5)
    if not all(math.isfinite(value) for value in ratios):
        raise RuntimeError("Nonfinite flex spacing measurement.")
    return (
        sketch,
        path,
        {
            "section": number,
            "exact_terminal": False,
            "retained_contour_reused": retained is not None,
            "segments": curves.count,
            "maximum_sample_displacement_mm": maximum_displacement,
            "maximum_sample_plane_departure_mm": maximum_plane_departure,
            "maximum_native_fit_point_error_mm": maximum_fit_error,
            "minimum_sample_center_pitch_ratio": min(ratios),
            "maximum_sample_center_pitch_ratio": max(ratios),
            "interpolation_error_between_fit_points": "unmeasured",
        },
    )
