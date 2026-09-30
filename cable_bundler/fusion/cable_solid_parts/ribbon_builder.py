"""
Generate one face-colored, banked solid for a discrete ribbon group.
"""

from __future__ import annotations

import json
import math
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...domain import CableGroupDefinition, CableMaterialSettings
from ...routing import RibbonFrame, RoutePreview, Vector3
from ...routing.geometry import difference, dot
from ..harness_gateway import ATTRIBUTE_GROUP
from .constants import GENERATED_CABLE_GROUP_ATTRIBUTE, GENERATED_OUTPUT_MODE_KEY
from .materials import cable_appearance, material_metadata
from .metadata import fusion_point, route_in_component_space, route_metadata
from .sweep_geometry import is_straight


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
    route_curve: adsk.fusion.SketchCurve,
    frame: RibbonFrame,
    group: CableGroupDefinition,
    transform: adsk.core.Matrix3D,
) -> tuple[adsk.fusion.Sketch, adsk.fusion.ConstructionPlane]:
    """
    Draw a joined moderate-groove profile with two lobe arcs per line.
    """
    plane_input = component.constructionPlanes.createInput()
    if not plane_input.setByDistanceOnPath(route_curve, adsk.core.ValueInput.createByReal(0)):
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
    for index in range(group.ribbon_lines):
        left = -half_width + index * diameter
        right = left + diameter
        center = (left + right) / 2.0
        for start_x, peak_y, end_x, edge_y in (
            (left, radius, right, valley),
            (right, -radius, left, -valley),
        ):
            arc = arcs.addByThreePoints(
                _section_point(section, frame, start_x, edge_y, transform),
                _section_point(section, frame, center, peak_y, transform),
                _section_point(section, frame, end_x, edge_y, transform),
            )
            if arc is None:
                raise RuntimeError("Fusion could not draw a ribbon line lobe.")
    cap_extension = radius * 0.2
    for side in (-1.0, 1.0):
        x = side * half_width
        top_y, bottom_y = (valley, -valley) if side > 0 else (-valley, valley)
        cap = arcs.addByThreePoints(
            _section_point(section, frame, x, top_y, transform),
            _section_point(section, frame, x + side * cap_extension, 0.0, transform),
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
) -> None:
    """
    Sweep one visible joined ribbon and color its physical lobe faces.
    """
    if not route.curves or len(frames) < 2:
        raise ValueError("A discrete ribbon needs one curved route and banking frames.")
    center_sketch, center_path, first_curve = _build_path(component, route, transform)
    rail_sketch, rail_path = _build_guide_rail(component, frames, group, transform)
    section, plane = _add_section(component, first_curve, frames[0], group, transform)
    profile = section.profiles.item(0)
    sweeps = component.features.sweepFeatures
    sweep_input = sweeps.createInput(
        profile, center_path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    if sweep_input is None:
        raise RuntimeError("Fusion could not define the discrete ribbon sweep.")
    sweep_input.guideRail = rail_path
    sweep_input.profileScaling = adsk.fusion.SweepProfileScalingOptions.SweepProfileNoScalingOption
    sweep = sweeps.add(sweep_input)
    if sweep is None or sweep.bodies.count != 1:
        raise RuntimeError("Fusion did not produce one discrete ribbon solid.")
    body = sweep.bodies.item(0)
    if not body.isSolid or not math.isfinite(body.volume) or body.volume <= 0:
        raise RuntimeError("Fusion produced an invalid discrete ribbon solid.")
    body.name = f"Cable Group {group_index + 1} Discrete Ribbon"
    body.isLightBulbOn = True
    body.appearance = cable_appearance(design, materials.main_color, materials.appearance)
    line_colors = group.resolved_ribbon_line_colors(materials.main_color)
    for face_index in range(sweep.sideFaces.count):
        face = sweep.sideFaces.item(face_index)
        if face is not None:
            lane = _face_lane(face, frames, transform, group)
            face.appearance = cable_appearance(design, line_colors[lane])
            if face.attributes.add(ATTRIBUTE_GROUP, "ribbon_lane", str(lane)) is None:
                raise RuntimeError("Fusion could not retain ribbon face-to-line identity.")
    center_sketch.isLightBulbOn = False
    rail_sketch.isLightBulbOn = False
    section.isLightBulbOn = False
    plane.isLightBulbOn = False
    sweep.name = "Discrete ribbon sweep"
    length_mm = sum(
        math.dist(
            (left.origin.x, left.origin.y, left.origin.z),
            (right.origin.x, right.origin.y, right.origin.z),
        )
        for left, right in zip(frames, frames[1:])
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
