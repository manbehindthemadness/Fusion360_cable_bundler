"""
Generate one face-colored, banked solid for a discrete ribbon group.
"""

from __future__ import annotations

import json
import math
from typing import Optional
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...domain import CableGroupDefinition, CableMaterialSettings
from ...routing import (
    RibbonFrame,
    RibbonShape,
    RoutePreview,
    Vector3,
    ribbon_lane_points,
    ribbon_line_lengths,
    solve_ribbon_shape,
)
from ...routing.geometry import difference, dot
from ..harness_gateway import ATTRIBUTE_GROUP
from .constants import GENERATED_CABLE_GROUP_ATTRIBUTE, GENERATED_OUTPUT_MODE_KEY
from .materials import cable_appearance, material_metadata
from .metadata import fusion_point, route_in_component_space, route_metadata
from .sweep_geometry import is_straight


class RibbonLoftUnavailable(RuntimeError):
    """
    Signal that a complete loft attempt can safely fall back to the sweep.
    """


def _section_point(
    section: adsk.fusion.Sketch,
    frame: RibbonFrame,
    across_mm: float,
    height_mm: float,
    transform: adsk.core.Matrix3D,
) -> adsk.core.Point3D:
    """
    Locate one procedural profile point in the initial sketch plane.
    """
    world = frame.origin.translated(frame.width, across_mm).translated(frame.thickness, height_mm)
    return section.modelToSketchSpace(fusion_point(world, transform))


def _add_section(
    component: adsk.fusion.Component,
    route_curve: adsk.fusion.Path,
    frame: RibbonFrame,
    group: CableGroupDefinition,
    transform: adsk.core.Matrix3D,
    offsets_mm: tuple[float, ...] = (),
    path_fraction: float = 0.0,
) -> tuple[adsk.fusion.Sketch, adsk.fusion.ConstructionPlane]:
    """
    Draw a joined moderate-groove profile with two lobe arcs per line.
    """
    plane_input = component.constructionPlanes.createInput()
    distance = adsk.core.ValueInput.createByReal(path_fraction)
    if hasattr(plane_input, "setByPath"):
        positioned = plane_input.setByPath(
            route_curve,
            adsk.fusion.PathDistanceTypes.ProportionalPathDistanceType,
            distance,
        )
    else:
        positioned = plane_input.setByDistanceOnPath(route_curve, distance)
    if not positioned:
        raise RuntimeError("Fusion could not orient the ribbon cross-section.")
    plane = component.constructionPlanes.add(plane_input)
    if plane is None:
        raise RuntimeError("Fusion did not create the ribbon cross-section plane.")
    plane.name = "Ribbon section plane"
    section = component.sketches.add(plane)
    if section is None:
        raise RuntimeError("Fusion did not create the ribbon section sketch.")
    section.name = "Discrete ribbon section"
    diameter = group.diameter_mm
    radius = diameter / 2.0
    valley = radius * 0.60
    half_width = group.ribbon_lines * diameter / 2.0
    arcs = section.sketchCurves.sketchArcs
    shifts = offsets_mm or (0.0,) * group.ribbon_lines
    if len(shifts) != group.ribbon_lines:
        raise ValueError("Ribbon section shifts must match its line count.")
    for index in range(group.ribbon_lines):
        left = -half_width + index * diameter
        right = left + diameter
        center = (left + right) / 2.0
        left_shift = shifts[0] if index == 0 else (shifts[index - 1] + shifts[index]) / 2.0
        right_shift = (
            shifts[index]
            if index == group.ribbon_lines - 1
            else (shifts[index] + shifts[index + 1]) / 2.0
        )
        for start_x, start_y, peak_y, end_x, end_y in (
            (left, left_shift + valley, shifts[index] + radius, right, right_shift + valley),
            (right, right_shift - valley, shifts[index] - radius, left, left_shift - valley),
        ):
            arc = arcs.addByThreePoints(
                _section_point(section, frame, start_x, start_y, transform),
                _section_point(section, frame, center, peak_y, transform),
                _section_point(section, frame, end_x, end_y, transform),
            )
            if arc is None:
                raise RuntimeError("Fusion could not draw a ribbon line lobe.")
    cap_extension = radius * 0.2
    for side in (-1.0, 1.0):
        x = side * half_width
        shift = shifts[-1] if side > 0 else shifts[0]
        top_y, bottom_y = (
            (shift + valley, shift - valley)
            if side > 0
            else (
                shift - valley,
                shift + valley,
            )
        )
        cap = arcs.addByThreePoints(
            _section_point(section, frame, x, top_y, transform),
            _section_point(section, frame, x + side * cap_extension, shift, transform),
            _section_point(section, frame, x, bottom_y, transform),
        )
        if cap is None:
            raise RuntimeError("Fusion could not close the ribbon section.")
    if section.profiles.count != 1:
        raise RuntimeError("Fusion did not produce one joined ribbon profile.")
    return section, plane


def _build_path(
    component: adsk.fusion.Component,
    route: RoutePreview,
    transform: adsk.core.Matrix3D,
) -> tuple[adsk.fusion.Sketch, adsk.fusion.Path, adsk.fusion.SketchCurve]:
    """
    Translate the exact routed cubics into one Fusion centerline path.
    """
    sketch = component.sketches.add(component.xYConstructionPlane)
    if sketch is None:
        raise RuntimeError("Fusion did not create the ribbon centerline sketch.")
    sketch.name = "Ribbon centerline"
    curves = adsk.core.ObjectCollection.create()
    for curve in route.curves:
        points = tuple(
            sketch.modelToSketchSpace(fusion_point(point, transform))
            for point in (curve.start, curve.control_a, curve.control_b, curve.end)
        )
        entity = (
            sketch.sketchCurves.sketchLines.addByTwoPoints(points[0], points[3])
            if is_straight(curve)
            else sketch.sketchCurves.sketchControlPointSplines.add(
                points, adsk.fusion.SplineDegrees.SplineDegreeThree
            )
        )
        if entity is None or not curves.add(entity):
            raise RuntimeError("Fusion could not draw a ribbon centerline segment.")
    path = component.features.createPath(curves, False)
    if path is None:
        raise RuntimeError("Fusion could not join the ribbon centerline path.")
    return sketch, path, curves.item(0)


def _build_guide_rail(
    component: adsk.fusion.Component,
    frames: tuple[RibbonFrame, ...],
    group: CableGroupDefinition,
    transform: adsk.core.Matrix3D,
) -> tuple[adsk.fusion.Sketch, adsk.fusion.Path]:
    """
    Make a width-edge rail that controls bank without scaling the section.
    """
    sketch = component.sketches.add(component.xYConstructionPlane)
    if sketch is None:
        raise RuntimeError("Fusion did not create the ribbon bank guide sketch.")
    sketch.name = "Ribbon banking rail"
    offset = (group.ribbon_lines + 0.2) * group.diameter_mm / 2.0
    points = tuple(
        sketch.modelToSketchSpace(
            fusion_point(frame.origin.translated(frame.width, offset), transform)
        )
        for frame in frames
    )
    rail = sketch.sketchCurves.sketchControlPointSplines.add(
        points, adsk.fusion.SplineDegrees.SplineDegreeThree
    )
    if rail is None:
        raise RuntimeError("Fusion could not draw the ribbon banking rail.")
    path = component.features.createPath(rail)
    if path is None:
        raise RuntimeError("Fusion could not create the ribbon banking path.")
    return sketch, path


def _face_lane(
    face: adsk.fusion.BRepFace,
    frames: tuple[RibbonFrame, ...],
    transform: adsk.core.Matrix3D,
    group: CableGroupDefinition,
) -> int:
    """
    Match one generated side face to its nearest transported line lane.
    """
    inverse = transform.copy()
    if not inverse.invert():
        raise RuntimeError("Ribbon color mapping could not invert the harness placement.")
    point = face.pointOnFace.copy()
    if not point.transformBy(inverse):
        raise RuntimeError("Ribbon color mapping could not transform a face point.")
    world = Vector3(point.x * 10.0, point.y * 10.0, point.z * 10.0)
    nearest = min(
        frames,
        key=lambda frame: math.dist(
            (world.x, world.y, world.z),
            (frame.origin.x, frame.origin.y, frame.origin.z),
        ),
    )
    position = dot(difference(world, nearest.origin), nearest.width)
    lane = round(position / group.diameter_mm + (group.ribbon_lines - 1) / 2.0)
    return max(0, min(group.ribbon_lines - 1, lane))


def _build_folded_loft(
    component: adsk.fusion.Component,
    center_path: adsk.fusion.Path,
    shape: RibbonShape,
    group: CableGroupDefinition,
    transform: adsk.core.Matrix3D,
) -> tuple[
    adsk.fusion.LoftFeature,
    tuple[adsk.fusion.Sketch, ...],
    tuple[adsk.fusion.ConstructionPlane, ...],
]:
    """
    Loft matching, locally buckled lobe profiles into one joined solid.
    """
    sections: list[adsk.fusion.Sketch] = []
    planes: list[adsk.fusion.ConstructionPlane] = []
    loft = None
    try:
        try:
            loft_input = component.features.loftFeatures.createInput(
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            raise RibbonLoftUnavailable("Fusion has no folded ribbon loft input.") from error
        if loft_input is None:
            raise RibbonLoftUnavailable("Fusion could not define a folded ribbon loft.")
        for section_index, frame in enumerate(shape.frames):
            shifts = tuple(
                dot(difference(lane[section_index], frame.origin), frame.thickness)
                for lane in shape.lanes
            )
            section, plane = _add_section(
                component,
                center_path,
                frame,
                group,
                transform,
                shifts,
                section_index / (len(shape.frames) - 1),
            )
            sections.append(section)
            planes.append(plane)
            loft_input.loftSections.add(section.profiles.item(0))
        loft_input.isSolid = True
        try:
            loft = component.features.loftFeatures.add(loft_input)
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            raise RibbonLoftUnavailable("Fusion rejected the folded ribbon sections.") from error
        if loft is None or loft.bodies.count != 1:
            raise RibbonLoftUnavailable("Fusion did not produce one folded ribbon body.")
        body = loft.bodies.item(0)
        if body is None or not body.isSolid or not math.isfinite(body.volume) or body.volume <= 0:
            raise RibbonLoftUnavailable("Fusion produced an invalid folded ribbon solid.")
        return loft, tuple(sections), tuple(planes)
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        if loft is not None and loft.isValid and not loft.deleteMe():
            raise RuntimeError("Fusion could not clean an invalid ribbon loft.") from error
        for sketch in reversed(sections):
            if sketch.isValid and not sketch.deleteMe():
                raise RuntimeError("Fusion could not clean a ribbon section sketch.") from error
        for plane in reversed(planes):
            if plane.isValid and not plane.deleteMe():
                raise RuntimeError("Fusion could not clean a ribbon section plane.") from error
        raise


def build_discrete_ribbon_solid(
    component: adsk.fusion.Component,
    group: CableGroupDefinition,
    group_index: int,
    route: RoutePreview,
    frames: tuple[RibbonFrame, ...],
    transform: adsk.core.Matrix3D,
    harness_id: UUID,
    materials: CableMaterialSettings,
    design: adsk.fusion.Design,
    output_mode: str,
    notices: Optional[list[str]] = None,
) -> None:
    """
    Build one visible joined ribbon and color its physical lobe faces.
    """
    if not route.curves or len(frames) < 2:
        raise ValueError("A discrete ribbon needs one curved route and banking frames.")
    shape = solve_ribbon_shape(frames, group.ribbon_lines, group.diameter_mm)
    center_sketch, center_path, _first_curve = _build_path(component, route, transform)
    feature = None
    folded = False
    if shape.folded:
        try:
            feature, sections, planes = _build_folded_loft(
                component, center_path, shape, group, transform
            )
            folded = True
            for section in sections:
                section.isLightBulbOn = False
            for plane in planes:
                plane.isLightBulbOn = False
        except RibbonLoftUnavailable as error:
            if notices is not None:
                notices.append(
                    f"Cable Group {group_index + 1}: folded loft unavailable ({error}); "
                    "using the original sweep with unequal line lengths."
                )
    if feature is None:
        rail_sketch, rail_path = _build_guide_rail(component, frames, group, transform)
        section, plane = _add_section(component, center_path, frames[0], group, transform)
        sweeps = component.features.sweepFeatures
        sweep_input = sweeps.createInput(
            section.profiles.item(0),
            center_path,
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        )
        if sweep_input is None:
            raise RuntimeError("Fusion could not define the discrete ribbon sweep.")
        sweep_input.guideRail = rail_path
        sweep_input.profileScaling = (
            adsk.fusion.SweepProfileScalingOptions.SweepProfileNoScalingOption
        )
        feature = sweeps.add(sweep_input)
        if feature is None or feature.bodies.count != 1:
            raise RuntimeError("Fusion did not produce one discrete ribbon solid.")
        rail_sketch.isLightBulbOn = False
        section.isLightBulbOn = False
        plane.isLightBulbOn = False
    body = feature.bodies.item(0)
    if not body.isSolid or not math.isfinite(body.volume) or body.volume <= 0:
        raise RuntimeError("Fusion produced an invalid discrete ribbon solid.")
    body.name = f"Cable Group {group_index + 1} Discrete Ribbon"
    body.isLightBulbOn = True
    body.appearance = cable_appearance(design, materials.main_color, materials.appearance)
    line_colors = group.resolved_ribbon_line_colors(materials.main_color)
    for face_index in range(feature.sideFaces.count):
        face = feature.sideFaces.item(face_index)
        if face is not None:
            lane = _face_lane(face, frames, transform, group)
            face.appearance = cable_appearance(design, line_colors[lane])
            if face.attributes.add(ATTRIBUTE_GROUP, "ribbon_lane", str(lane)) is None:
                raise RuntimeError("Fusion could not retain ribbon face-to-line identity.")
    center_sketch.isLightBulbOn = False
    feature.name = "Discrete ribbon folded loft" if folded else "Discrete ribbon sweep"
    lengths = (
        shape.lengths_mm
        if folded
        else ribbon_line_lengths(ribbon_lane_points(frames, group.ribbon_lines, group.diameter_mm))
    )
    length_mm = max(lengths)
    spread = (length_mm - min(lengths)) / length_mm
    maximum_pitch_ratio = shape.maximum_pitch_ratio if folded else 1.0
    if notices is not None:
        status = "meets" if spread <= 0.01 + 1e-9 else "exceeds"
        notices.append(
            f"{'Warning: ' if status == 'exceeds' else ''}"
            f"Cable Group {group_index + 1}: ribbon lines "
            f"{min(lengths):.2f}–{length_mm:.2f} mm "
            f"({spread:.1%} spread; {status} 1% target; "
            f"maximum adjacent pitch {maximum_pitch_ratio:.2f}× nominal)."
        )
    component.name = f"Cable Group {group_index + 1}_{length_mm:.2f}mm"
    local_route = route_in_component_space(route, transform)
    metadata = json.dumps(
        {
            "harness_id": str(harness_id),
            "cable_group_id": str(group.cable_group_id),
            GENERATED_OUTPUT_MODE_KEY: output_mode,
            "diameter_mm": group.diameter_mm,
            "ribbon_lines": group.ribbon_lines,
            "length_mm": length_mm,
            "ribbon_line_lengths_mm": lengths,
            "ribbon_length_spread": spread,
            "ribbon_folded": folded,
            "ribbon_maximum_pitch_ratio": maximum_pitch_ratio,
            "route_legs": [
                {
                    "route_id": str(route.cable_id),
                    "label": route.cable_number,
                    "length_mm": length_mm,
                    "route_curves_mm": route_metadata(local_route),
                }
            ],
            "connection_branches": [],
            "main_insulation_body_count": 1,
            "main_pullbacks": [],
            "main_welds": [],
            **material_metadata(materials),
        },
        sort_keys=True,
    )
    if component.attributes.add(ATTRIBUTE_GROUP, GENERATED_CABLE_GROUP_ATTRIBUTE, metadata) is None:
        raise RuntimeError("Fusion could not store the generated ribbon identity.")
