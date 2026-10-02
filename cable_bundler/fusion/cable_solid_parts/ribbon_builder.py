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
from ...domain.ffc import FfcDimensions
from ...routing import (
    RIBBON_NEIGHBOR_PITCH_LIMIT,
    RibbonEndFit,
    RibbonFrame,
    RibbonShape,
    RoutePreview,
    Vector3,
    ribbon_lane_points,
    ribbon_line_lengths,
)
from ...routing.geometry import cross, difference, dot, unit
from ..harness_gateway import ATTRIBUTE_GROUP
from ..ribbon_geometry import RibbonGuidePlane
from ..solid_ribbon import (
    SOLID_RIBBON_LEAD_FRACTIONS,
    SolidRibbonPlan,
    SolidRibbonSection,
)
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


def _lane_section_point(
    section: adsk.fusion.Sketch,
    frame: RibbonFrame,
    centers: tuple[Vector3, ...],
    normals: tuple[Vector3, ...],
    end_fit: RibbonEndFit | None,
    across_mm: float,
    height_mm: float,
    diameter_mm: float,
    transform: adsk.core.Matrix3D,
) -> adsk.core.Point3D:
    """
    Interpolate a lobe point from measured lanes before sketch-plane projection.
    """
    position = across_mm / diameter_mm + (len(centers) - 1) / 2.0
    edge_index = round(position + 0.5)
    if (
        end_fit is not None
        and len(end_fit.edges) == len(centers) + 1
        and len(end_fit.edge_normals) == len(end_fit.edges)
        and 0 <= edge_index <= len(centers)
        and abs(position - (edge_index - 0.5)) < 1e-8
    ):
        center = end_fit.edges[edge_index]
        normal = end_fit.edge_normals[edge_index]
    elif len(centers) == 1:
        center = centers[0].translated(frame.width, across_mm)
        normal = normals[0]
    else:
        left = max(0, min(len(centers) - 2, math.floor(position)))
        fraction = position - left
        center = centers[left].translated(difference(centers[left + 1], centers[left]), fraction)
        normal = normals[left].translated(difference(normals[left + 1], normals[left]), fraction)
    world = center.translated(normal, height_mm)
    return section.modelToSketchSpace(fusion_point(world, transform))


def _direct_guide_plane(guide: RibbonGuidePlane, transform: adsk.core.Matrix3D) -> adsk.core.Plane:
    """
    Transform a nonparametric end sketch's plane into harness-local space.
    """
    origin = fusion_point(guide.origin, transform)
    tip = fusion_point(guide.origin.translated(guide.normal, 10.0), transform)
    normal = adsk.core.Vector3D.create(tip.x - origin.x, tip.y - origin.y, tip.z - origin.z)
    if not normal.normalize():
        raise ValueError("A ribbon guide plane has no usable normal.")
    return adsk.core.Plane.create(origin, normal)


def _add_section(
    component: adsk.fusion.Component,
    route_curve: adsk.fusion.Path,
    frame: RibbonFrame,
    group: CableGroupDefinition,
    transform: adsk.core.Matrix3D,
    offsets_mm: tuple[float, ...] = (),
    path_fraction: float = 0.0,
    lane_centers: tuple[Vector3, ...] = (),
    lane_normals: tuple[Vector3, ...] = (),
    end_fit: RibbonEndFit | None = None,
    guide_plane: RibbonGuidePlane | None = None,
) -> tuple[adsk.fusion.Sketch, adsk.fusion.ConstructionPlane]:
    """
    Draw a joined moderate-groove profile with two lobe arcs per line.
    """
    plane_input = component.constructionPlanes.createInput()
    distance = adsk.core.ValueInput.createByReal(path_fraction)
    if guide_plane is not None:
        if guide_plane.reference_plane is not None:
            positioned = plane_input.setByOffset(
                guide_plane.reference_plane, adsk.core.ValueInput.createByReal(0.0)
            )
        else:
            positioned = plane_input.setByPlane(_direct_guide_plane(guide_plane, transform))
    elif hasattr(plane_input, "setByPath"):
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
    plane.isLightBulbOn = False
    section = component.sketches.add(plane)
    if section is None:
        raise RuntimeError("Fusion did not create the ribbon section sketch.")
    section.name = "Discrete ribbon section"
    section.isLightBulbOn = False
    diameter = group.diameter_mm
    radius = diameter / 2.0
    valley = radius * 0.60
    half_width = group.ribbon_lines * diameter / 2.0
    arcs = section.sketchCurves.sketchArcs
    shifts = offsets_mm or (0.0,) * group.ribbon_lines
    if len(shifts) != group.ribbon_lines:
        raise ValueError("Ribbon section shifts must match its line count.")
    if lane_centers and (
        len(lane_centers) != group.ribbon_lines or len(lane_normals) != group.ribbon_lines
    ):
        raise ValueError("Ribbon section lanes must match its line count.")

    def point(across_mm: float, height_mm: float) -> adsk.core.Point3D:
        """
        Use the final sampled lanes for fitted lofts and legacy coordinates for sweeps.
        """
        if lane_centers:
            return _lane_section_point(
                section,
                frame,
                lane_centers,
                lane_normals,
                end_fit,
                across_mm,
                height_mm,
                diameter,
                transform,
            )
        return _section_point(section, frame, across_mm, height_mm, transform)

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
                point(start_x, start_y),
                point(center, peak_y),
                point(end_x, end_y),
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
            point(x, top_y),
            point(x + side * cap_extension, shift),
            point(x, bottom_y),
        )
        if cap is None:
            raise RuntimeError("Fusion could not close the ribbon section.")
    if section.profiles.count != 1:
        if section.isValid and not section.deleteMe():
            raise RuntimeError("Fusion could not clean an invalid ribbon section sketch.")
        if plane.isValid and not plane.deleteMe():
            raise RuntimeError("Fusion could not clean an invalid ribbon section plane.")
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


def _face_world_point(
    face: adsk.fusion.BRepFace,
    transform: adsk.core.Matrix3D,
) -> Vector3:
    """
    Locate a Fusion face sample in the millimeter routing coordinate system.
    """
    inverse = transform.copy()
    if not inverse.invert():
        raise RuntimeError("Ribbon color mapping could not invert the harness placement.")
    point = face.pointOnFace.copy()
    if not point.transformBy(inverse):
        raise RuntimeError("Ribbon color mapping could not transform a face point.")
    return Vector3(point.x * 10.0, point.y * 10.0, point.z * 10.0)


def _nearest_solid_station(world: Vector3, plan: SolidRibbonPlan) -> SolidRibbonSection:
    """
    Find the transported section closest to a generated loft face.
    """
    return min(
        plan.sections,
        key=lambda station: min(
            math.dist((world.x, world.y, world.z), (center.x, center.y, center.z))
            for center in station.centers
        ),
    )


def _ffc_trace_land_lane(
    world: Vector3,
    plan: SolidRibbonPlan,
    ffc: FfcDimensions,
    thickness_mm: float,
) -> int | None:
    """
    Color only a trace's upper or lower flat land, never its edge or spacing web.

    Section notches separate each land from its web so each loft face receives
    one appearance. The face sample is tested in the nearest transported frame.
    """
    station = _nearest_solid_station(world, plan)
    lane = min(
        range(len(station.centers)),
        key=lambda index: math.dist(
            (world.x, world.y, world.z),
            (station.centers[index].x, station.centers[index].y, station.centers[index].z),
        ),
    )
    offset = difference(world, station.centers[lane])
    across_mm = abs(dot(offset, station.width))
    height = unit(cross(station.normal, station.width))
    height_mm = abs(dot(offset, height))
    if across_mm >= ffc.trace_width_mm / 2.0 or height_mm < thickness_mm * 0.4:
        return None
    return lane


def _face_lane(
    face: adsk.fusion.BRepFace,
    frames: tuple[RibbonFrame, ...],
    transform: adsk.core.Matrix3D,
    group: CableGroupDefinition,
    solid_plan: SolidRibbonPlan | None = None,
) -> int:
    """
    Match one generated side face to its nearest transported line lane.
    """
    world = _face_world_point(face, transform)
    if solid_plan is not None:
        nearest_station = _nearest_solid_station(world, solid_plan)
        return min(
            range(group.ribbon_lines),
            key=lambda index: math.dist(
                (world.x, world.y, world.z),
                (
                    nearest_station.centers[index].x,
                    nearest_station.centers[index].y,
                    nearest_station.centers[index].z,
                ),
            ),
        )
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
    guide_planes: tuple[RibbonGuidePlane | None, RibbonGuidePlane | None],
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
            centers = tuple(lane[section_index] for lane in shape.lanes)
            fit: RibbonEndFit | None = (
                shape.start_fit
                if section_index == 0
                else shape.end_fit
                if section_index == len(shape.frames) - 1
                else None
            )
            normals = fit.normals if fit is not None else (frame.thickness,) * group.ribbon_lines
            guide_plane = (
                guide_planes[0]
                if section_index == 0
                else guide_planes[1]
                if section_index == len(shape.frames) - 1
                else None
            )
            try:
                section, plane = _add_section(
                    component,
                    center_path,
                    frame,
                    group,
                    transform,
                    path_fraction=section_index / (len(shape.frames) - 1),
                    lane_centers=centers,
                    lane_normals=normals,
                    end_fit=fit,
                    guide_plane=guide_plane,
                )
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                raise RibbonLoftUnavailable(
                    f"Ribbon section {section_index + 1} could not be drawn ({error})."
                ) from error
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
        raise RibbonLoftUnavailable(str(error)) from error


def _add_solid_section(
    component: adsk.fusion.Component,
    station: SolidRibbonSection,
    diameter_mm: float,
    transform: adsk.core.Matrix3D,
    ffc: FfcDimensions | None = None,
) -> tuple[adsk.fusion.Sketch, adsk.fusion.ConstructionPlane]:
    """
    Draw one constant-thickness profile with variable web and lobe width.
    """
    origin = station.centers[0]
    plane_input = component.constructionPlanes.createInput()
    guide = RibbonGuidePlane(origin, station.normal)
    if not plane_input.setByPlane(_direct_guide_plane(guide, transform)):
        raise RuntimeError("Fusion could not orient a Solid ribbon section.")
    plane = component.constructionPlanes.add(plane_input)
    if plane is None:
        raise RuntimeError("Fusion could not create a Solid ribbon section plane.")
    plane.name = "Solid ribbon section plane"
    plane.isLightBulbOn = False
    sketch = component.sketches.add(plane)
    if sketch is None:
        raise RuntimeError("Fusion could not create a Solid ribbon section sketch.")
    sketch.name = "Solid ribbon section"
    sketch.isLightBulbOn = False
    thickness = Vector3(
        station.normal.y * station.width.z - station.normal.z * station.width.y,
        station.normal.z * station.width.x - station.normal.x * station.width.z,
        station.normal.x * station.width.y - station.normal.y * station.width.x,
    )
    if ffc is not None:
        _draw_ffc_section(sketch, station, thickness, diameter_mm, ffc, transform)
        if sketch.profiles.count != 1:
            raise RuntimeError("Fusion did not produce one joined FFC section.")
        return sketch, plane
    radius = diameter_mm / 2.0
    valley = radius * 0.60
    half_width = station.lobe_width_mm / 2.0

    def point(index: int, across: float, height: float) -> adsk.core.Point3D:
        """
        Place a lobe or web endpoint on this section's own plane.
        """
        world = (
            station.centers[index].translated(station.width, across).translated(thickness, height)
        )
        return sketch.modelToSketchSpace(fusion_point(world, transform))

    arcs = sketch.sketchCurves.sketchArcs
    lines = sketch.sketchCurves.sketchLines
    nodes: list[tuple[adsk.fusion.SketchPoint, ...]] = []
    for index in range(len(station.centers)):
        junctions = tuple(
            sketch.sketchPoints.add(point(index, across, height))
            for across, height in (
                (-half_width, valley),
                (half_width, valley),
                (half_width, -valley),
                (-half_width, -valley),
            )
        )
        if any(junction is None for junction in junctions):
            raise RuntimeError("Fusion could not place a Solid ribbon contour junction.")
        nodes.append(junctions)
        left_top, right_top, right_bottom, left_bottom = junctions
        if arcs.addByThreePoints(left_top, point(index, 0.0, radius), right_top) is None:
            raise RuntimeError("Fusion could not draw a Solid ribbon top lobe.")
        if arcs.addByThreePoints(right_bottom, point(index, 0.0, -radius), left_bottom) is None:
            raise RuntimeError("Fusion could not draw a Solid ribbon bottom lobe.")
        if index:
            if lines.addByTwoPoints(nodes[index - 1][1], left_top) is None:
                raise RuntimeError("Fusion could not join a Solid ribbon top web.")
            if lines.addByTwoPoints(left_bottom, nodes[index - 1][2]) is None:
                raise RuntimeError("Fusion could not join a Solid ribbon bottom web.")
    for index, sign, top, bottom in (
        (0, -1.0, nodes[0][0], nodes[0][3]),
        (len(station.centers) - 1, 1.0, nodes[-1][1], nodes[-1][2]),
    ):
        if (
            arcs.addByThreePoints(
                top,
                point(index, sign * (half_width + radius * 0.2), 0.0),
                bottom,
            )
            is None
        ):
            raise RuntimeError("Fusion could not cap a Solid ribbon section.")
    profile_count = sketch.profiles.count
    if profile_count != 1:
        raise RuntimeError(
            "Fusion did not produce one joined Solid ribbon section "
            f"(profiles={profile_count}, lines={len(station.centers)}, "
            f"lobe width={station.lobe_width_mm:.3f} mm)."
        )
    return sketch, plane


def _draw_ffc_section(
    sketch: adsk.fusion.Sketch,
    station: SolidRibbonSection,
    normal: Vector3,
    thickness_mm: float,
    ffc: FfcDimensions,
    transform: adsk.core.Matrix3D,
) -> None:
    """
    Separate flat trace lands from spacing webs with shallow V notches.

    Keep each colorable land exactly trace_width_mm wide; notch relief uses
    only the neighboring spacing and preserves the overall thickness.
    """
    half_height = thickness_mm / 2.0
    notch_depth = thickness_mm * 0.05
    notch_half_width = min(ffc.trace_width_mm, ffc.spacing_mm) * 0.03
    half_trace = ffc.trace_width_mm / 2.0
    half_pitch = ffc.pitch_mm / 2.0
    count = len(station.centers)
    top = [(0, -half_pitch, half_height)]
    for index in range(count):
        top.extend(
            (
                (index, -half_trace - 2.0 * notch_half_width, half_height),
                (index, -half_trace - notch_half_width, half_height - notch_depth),
                (index, -half_trace, half_height),
                (index, half_trace, half_height),
                (index, half_trace + notch_half_width, half_height - notch_depth),
                (index, half_trace + 2.0 * notch_half_width, half_height),
            )
        )
    top.append((count - 1, half_pitch, half_height))
    bottom = [(index, across, -height) for index, across, height in reversed(top)]
    contour = top + bottom

    def point(index: int, across: float, height: float) -> adsk.core.Point3D:
        """
        Locate one flat-section corner in the loft station's sketch plane.
        """
        world = station.centers[index].translated(station.width, across).translated(normal, height)
        return sketch.modelToSketchSpace(fusion_point(world, transform))

    corners = tuple(sketch.sketchPoints.add(point(*corner)) for corner in contour)
    if any(corner is None for corner in corners):
        raise RuntimeError("Fusion could not place an FFC section corner.")
    for start, end in zip(corners, (*corners[1:], corners[0])):
        if sketch.sketchCurves.sketchLines.addByTwoPoints(start, end) is None:
            raise RuntimeError("Fusion could not draw an FFC section edge.")


def _build_single_trace_ffc_loft(
    component: adsk.fusion.Component,
    plan: SolidRibbonPlan,
    thickness_mm: float,
    transform: adsk.core.Matrix3D,
    ffc: FfcDimensions,
    station_indices: tuple[int, ...],
) -> adsk.fusion.LoftFeature:
    """
    Join two-section lofts where Fusion rejects one loft over the bent lane.

    The same station profiles and solver drive every span. Shared sketches
    make each adjacent loft meet at exactly the same cross-section.
    """
    sections: list[adsk.fusion.Sketch] = []
    planes: list[adsk.fusion.ConstructionPlane] = []
    lofts: list[adsk.fusion.LoftFeature] = []
    try:
        for section_index in station_indices:
            section, plane = _add_solid_section(
                component, plan.sections[section_index], thickness_mm, transform, ffc
            )
            sections.append(section)
            planes.append(plane)
        for span_index, (start, end) in enumerate(zip(sections, sections[1:])):
            operation = (
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
                if span_index == 0
                else adsk.fusion.FeatureOperations.JoinFeatureOperation
            )
            loft_input = component.features.loftFeatures.createInput(operation)
            if loft_input is None:
                raise RuntimeError(f"Fusion could not define FFC span {span_index + 1}.")
            loft_input.loftSections.add(start.profiles.item(0))
            loft_input.loftSections.add(end.profiles.item(0))
            loft_input.isSolid = True
            loft_input.isTangentEdgesMerged = True
            loft = component.features.loftFeatures.add(loft_input)
            if loft is None:
                raise RuntimeError(f"Fusion rejected FFC span {span_index + 1}.")
            lofts.append(loft)
            if component.bRepBodies.count != 1:
                raise RuntimeError(f"Fusion did not join FFC span {span_index + 1}.")
        body = component.bRepBodies.item(0)
        if body is None or not body.isSolid or not math.isfinite(body.volume) or body.volume <= 0:
            raise RuntimeError("Fusion produced an invalid single-trace FFC body.")
        return lofts[-1]
    except (AttributeError, RuntimeError, TypeError, ValueError):
        for loft in reversed(lofts):
            if loft.isValid:
                loft.deleteMe()
        for section in reversed(sections):
            if section.isValid:
                section.deleteMe()
        for plane in reversed(planes):
            if plane.isValid:
                plane.deleteMe()
        raise


def _build_solid_loft(
    component: adsk.fusion.Component,
    plan: SolidRibbonPlan,
    diameter_mm: float,
    transform: adsk.core.Matrix3D,
    ffc: FfcDimensions | None = None,
) -> adsk.fusion.LoftFeature:
    """
    Loft a fixed-width ribbon through sparse route guides and both contact planes.
    """
    sections: list[adsk.fusion.Sketch] = []
    planes: list[adsk.fusion.ConstructionPlane] = []
    loft = None
    try:
        station_count = len(plan.sections)
        if station_count < 2:
            raise ValueError("Solid ribbon loft needs at least two sections.")
        lead_count = len(SOLID_RIBBON_LEAD_FRACTIONS)
        first_main = lead_count
        last_main = station_count - lead_count - 1
        main_indices = (
            tuple(
                first_main + math.ceil(fraction * (last_main - first_main))
                for fraction in (0.0, 0.25, 0.5, 0.75, 1.0)
            )
            if first_main <= last_main
            else ()
        )
        station_indices = tuple(dict.fromkeys((0, *main_indices, station_count - 1)))
        if ffc is not None and len(plan.sections[0].centers) == 1:
            return _build_single_trace_ffc_loft(
                component, plan, diameter_mm, transform, ffc, station_indices
            )
        loft_input = component.features.loftFeatures.createInput(
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        if loft_input is None:
            raise RuntimeError("Fusion could not define the Solid ribbon loft.")
        for section_index in station_indices:
            station = plan.sections[section_index]
            role = (
                "start contact lead"
                if section_index < lead_count
                else "end contact lead"
                if section_index >= station_count - lead_count
                else "main ribbon"
            )
            try:
                sketch, plane = (
                    _add_solid_section(component, station, diameter_mm, transform, ffc)
                    if ffc is not None
                    else _add_solid_section(component, station, diameter_mm, transform)
                )
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                raise RuntimeError(
                    f"section {section_index + 1}/{station_count} ({role}): {error}"
                ) from error
            sections.append(sketch)
            planes.append(plane)
            loft_input.loftSections.add(sketch.profiles.item(0))
        loft_input.isSolid = True
        loft_input.isTangentEdgesMerged = True
        loft = component.features.loftFeatures.add(loft_input)
        if loft is None:
            error_code, description = adsk.core.Application.get().getLastError()
            raise RuntimeError(
                "Fusion rejected the Solid ribbon loft "
                f"(error {error_code}: {description or 'no detail available'})."
            )
        feature_bodies = loft.bodies.count
        component_bodies = component.bRepBodies.count
        if feature_bodies != 1 or component_bodies != 1:
            solids = 0
            for index in range(feature_bodies):
                candidate = loft.bodies.item(index)
                if candidate is not None and candidate.isSolid:
                    solids += 1
            raise RuntimeError(
                "Fusion did not produce exactly one Solid ribbon body "
                f"(feature bodies={feature_bodies}, component bodies={component_bodies}, "
                f"solid bodies={solids}, "
                f"feature health={getattr(loft, 'healthState', 'unavailable')}, "
                f"detail={getattr(loft, 'errorOrWarningMessage', '') or 'none'})."
            )
        body = loft.bodies.item(0)
        if body is None or not body.isSolid or not math.isfinite(body.volume) or body.volume <= 0:
            raise RuntimeError("Fusion produced an invalid Solid ribbon body.")
        return loft
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        if loft is not None and loft.isValid:
            loft.deleteMe()
        for sketch in reversed(sections):
            if sketch.isValid:
                sketch.deleteMe()
        for plane in reversed(planes):
            if plane.isValid:
                plane.deleteMe()
        raise RuntimeError(f"Solid ribbon contact-to-contact loft failed: {error}") from error


def build_discrete_ribbon_solid(
    component: adsk.fusion.Component,
    group: CableGroupDefinition,
    group_index: int,
    route: RoutePreview,
    shape: RibbonShape,
    guide_planes: tuple[RibbonGuidePlane | None, RibbonGuidePlane | None],
    transform: adsk.core.Matrix3D,
    harness_id: UUID,
    materials: CableMaterialSettings,
    design: adsk.fusion.Design,
    output_mode: str,
    notices: Optional[list[str]] = None,
    solid_plan: SolidRibbonPlan | None = None,
    ffc: FfcDimensions | None = None,
) -> adsk.fusion.BRepBody:
    """
    Build one joined ribbon and color its physical trace or lobe faces.
    """
    frames = shape.frames
    if not route.curves or len(frames) < 2:
        raise ValueError("A discrete ribbon needs one curved route and banking frames.")
    center_sketch = None
    center_path = None
    if solid_plan is None:
        center_sketch, center_path, _first_curve = _build_path(component, route, transform)
    feature = None
    folded = False
    if solid_plan is not None:
        feature = _build_solid_loft(component, solid_plan, group.diameter_mm, transform, ffc)
        folded = True
    elif shape.folded or shape.start_fit is not None or shape.end_fit is not None:
        try:
            feature, sections, planes = _build_folded_loft(
                component, center_path, shape, group, transform, guide_planes
            )
            folded = True
            for section in sections:
                section.isLightBulbOn = False
            for plane in planes:
                plane.isLightBulbOn = False
        except RibbonLoftUnavailable as error:
            if notices is not None:
                notices.append(
                    f"Cable Group {group_index + 1}: fitted loft unavailable ({error}); "
                    "using the original sweep; guide fit and measured line lengths are not achieved."
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
    body = component.bRepBodies.item(0) if solid_plan is not None else feature.bodies.item(0)
    if not body.isSolid or not math.isfinite(body.volume) or body.volume <= 0:
        raise RuntimeError("Fusion produced an invalid discrete ribbon solid.")
    body.name = (
        f"Cable Group {group_index + 1} FFC Ribbon"
        if ffc is not None
        else f"Cable Group {group_index + 1} Solid Ribbon"
        if solid_plan is not None
        else f"Cable Group {group_index + 1} Discrete Ribbon"
    )
    body.isLightBulbOn = True
    body.appearance = cable_appearance(design, materials.main_color, materials.appearance)
    line_colors = group.resolved_ribbon_line_colors(materials.main_color)
    color_faces = body.faces if ffc is not None and group.ribbon_lines == 1 else feature.sideFaces
    for face_index in range(color_faces.count):
        face = color_faces.item(face_index)
        if face is not None:
            if ffc is not None:
                if solid_plan is None:
                    raise RuntimeError("FFC face colors require a solid ribbon plan.")
                lane = _ffc_trace_land_lane(
                    _face_world_point(face, transform), solid_plan, ffc, group.diameter_mm
                )
                if lane is None:
                    continue
            else:
                lane = _face_lane(face, frames, transform, group, solid_plan)
            face.appearance = cable_appearance(design, line_colors[lane])
            if face.attributes.add(ATTRIBUTE_GROUP, "ribbon_lane", str(lane)) is None:
                raise RuntimeError("Fusion could not retain ribbon face-to-line identity.")
    if center_sketch is not None:
        center_sketch.isLightBulbOn = False
    feature.name = (
        "FFC contact loft"
        if ffc is not None
        else "Solid ribbon contact loft"
        if solid_plan is not None
        else "Discrete ribbon folded loft"
        if folded
        else "Discrete ribbon sweep"
    )
    lengths = (
        ribbon_line_lengths(solid_plan.lanes)
        if solid_plan is not None
        else shape.lengths_mm
        if folded
        else ribbon_line_lengths(ribbon_lane_points(frames, group.ribbon_lines, group.diameter_mm))
    )
    length_mm = max(lengths)
    spread = (length_mm - min(lengths)) / length_mm
    maximum_pitch_ratio = shape.maximum_pitch_ratio if folded else 1.0
    if notices is not None:
        if (
            folded
            and maximum_pitch_ratio > RIBBON_NEIGHBOR_PITCH_LIMIT + 1e-6
            and not any(
                f"Cable Group {group_index + 1}:" in notice and "pitch target" in notice
                for notice in notices
            )
        ):
            notices.append(
                f"Warning: Cable Group {group_index + 1}: ribbon end fit exceeds "
                "the 3% adjacent-line pitch target."
            )
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
            "ribbon_body_type": group.ribbon_body_type.value,
            "ribbon_geometry": group.ribbon_geometry.value,
            "trace_width_mm": group.trace_width_mm,
            "trace_spacing_mm": group.trace_spacing_mm,
            "resolved_trace_width_mm": ffc.trace_width_mm if ffc is not None else None,
            "resolved_trace_spacing_mm": ffc.spacing_mm if ffc is not None else None,
            "ribbon_contact_ids": solid_plan.contact_ids if solid_plan is not None else None,
            "ribbon_attachment_ids": solid_plan.attachment_ids if solid_plan is not None else None,
            "ribbon_contact_signature": (
                solid_plan.contact_signature if solid_plan is not None else None
            ),
            "length_mm": length_mm,
            "ribbon_line_lengths_mm": lengths,
            "ribbon_length_spread": spread,
            "ribbon_folded": folded,
            "ribbon_maximum_pitch_ratio": maximum_pitch_ratio,
            "ribbon_end_lead_mm": shape.end_lead_mm if folded else None,
            "ribbon_minimum_end_radius_mm": shape.minimum_end_radius_mm if folded else None,
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
    return body
