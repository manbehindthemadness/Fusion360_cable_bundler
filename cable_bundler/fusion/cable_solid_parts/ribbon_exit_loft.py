"""
Build numbered ribbon exits as lobe-rooted lofts in their owning component.
"""

from __future__ import annotations

from dataclasses import dataclass

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...routing import CubicBezier, RibbonEndFit, RibbonFrame, RoutePreview, Vector3
from ...routing.geometry import difference, magnitude, unit
from ..ribbon_geometry import RibbonGuidePlane
from .metadata import fusion_point
from .ribbon_builder import _lane_section_point
from .sweep_geometry import route_tail_axis

_INWARD_OVERLAP_MM = 0.02
_END_FACE_TOLERANCE_CM = 0.01
_SAMPLE_PARAMETERS = (1.0, 0.75, 0.5, 0.25, 0.0)


@dataclass(frozen=True)
class RibbonExitEnd:
    """
    Retain the fitted cap geometry and ordered lanes for one ribbon end.
    """

    guide_plane: RibbonGuidePlane
    frame: RibbonFrame
    lane_centers: tuple[Vector3, ...]
    fit: RibbonEndFit


def _cap_face(
    ribbon: adsk.fusion.BRepBody,
    end: RibbonExitEnd,
    transform: adsk.core.Matrix3D,
) -> adsk.fusion.BRepFace:
    """
    Find the generated planar cap nearest the authored end guide.
    """
    origin = fusion_point(end.guide_plane.origin, transform)
    tip = fusion_point(end.guide_plane.origin.translated(end.guide_plane.normal, 10.0), transform)
    normal = adsk.core.Vector3D.create(tip.x - origin.x, tip.y - origin.y, tip.z - origin.z)
    if not normal.normalize():
        raise ValueError("A ribbon exit end guide has no normal.")
    candidates: list[tuple[float, adsk.fusion.BRepFace]] = []
    for face in ribbon.faces:
        if face.geometry.objectType != adsk.core.Plane.classType():
            continue
        sample = face.pointOnFace
        distance = abs(
            (sample.x - origin.x) * normal.x
            + (sample.y - origin.y) * normal.y
            + (sample.z - origin.z) * normal.z
        )
        candidates.append((distance, face))
    if not candidates:
        raise RuntimeError("The generated ribbon has no planar end face.")
    distance, face = min(candidates, key=lambda item: item[0])
    if distance > _END_FACE_TOLERANCE_CM:
        raise RuntimeError("No generated ribbon cap matches its fitted end guide.")
    return face


def _project_to_cap(point: adsk.core.Point3D, face: adsk.fusion.BRepFace) -> adsk.core.Point3D:
    """
    Project a fitted lane center onto the exact generated cap plane.
    """
    plane = adsk.core.Plane.cast(face.geometry)
    if plane is None:
        raise RuntimeError("The ribbon exit cap is not planar.")
    normal = plane.normal
    squared = normal.x**2 + normal.y**2 + normal.z**2
    if squared <= 1e-20:
        raise RuntimeError("The ribbon exit cap has no usable normal.")
    origin = plane.origin
    scale = (
        (point.x - origin.x) * normal.x
        + (point.y - origin.y) * normal.y
        + (point.z - origin.z) * normal.z
    ) / squared
    return adsk.core.Point3D.create(
        point.x - scale * normal.x,
        point.y - scale * normal.y,
        point.z - scale * normal.z,
    )


def _section_sketch(
    component: adsk.fusion.Component,
    origin: adsk.core.Point3D,
    normal: adsk.core.Vector3D,
) -> adsk.fusion.Sketch:
    """
    Add a hidden in-place section plane and sketch to the ribbon component.
    """
    plane_input = component.constructionPlanes.createInput()
    if not plane_input.setByPlane(adsk.core.Plane.create(origin, normal)):
        raise RuntimeError("Fusion rejected a ribbon exit section plane.")
    construction = component.constructionPlanes.add(plane_input)
    if construction is None:
        raise RuntimeError("Fusion could not create a ribbon exit section plane.")
    construction.name = "Ribbon exit section plane"
    construction.isLightBulbOn = False
    sketch = component.sketches.add(construction)
    if sketch is None:
        raise RuntimeError("Fusion could not sketch a ribbon exit section.")
    sketch.name = "Ribbon exit section"
    sketch.isLightBulbOn = False
    return sketch


def _lobe_profile(
    component: adsk.fusion.Component,
    origin: adsk.core.Point3D,
    normal: adsk.core.Vector3D,
    end: RibbonExitEnd,
    line_index: int,
    diameter_mm: float,
    transform: adsk.core.Matrix3D,
) -> adsk.fusion.Profile:
    """
    Partition the joined cap with one lane's exact fitted top and bottom arcs.
    """
    if not 0 <= line_index < len(end.lane_centers):
        raise ValueError("A ribbon exit line is outside its fitted cap.")
    sketch = _section_sketch(component, origin, normal)
    radius = diameter_mm / 2.0
    valley = radius * 0.60
    half_width = len(end.lane_centers) * diameter_mm / 2.0
    left = -half_width + line_index * diameter_mm
    right = left + diameter_mm
    middle = (left + right) / 2.0

    def point(across_mm: float, height_mm: float) -> adsk.core.Point3D:
        """
        Project the ribbon loft's fitted lane coordinates into this sketch.
        """
        projected = _lane_section_point(
            sketch,
            end.frame,
            end.lane_centers,
            end.fit.normals,
            end.fit,
            across_mm,
            height_mm,
            diameter_mm,
            transform,
        )
        return adsk.core.Point3D.create(projected.x, projected.y, 0.0)

    top_left = point(left, valley)
    top_mid = point(middle, radius)
    top_right = point(right, valley)
    bottom_right = point(right, -valley)
    bottom_mid = point(middle, -radius)
    bottom_left = point(left, -valley)
    arcs = sketch.sketchCurves.sketchArcs
    lines = sketch.sketchCurves.sketchLines
    if arcs.addByThreePoints(top_left, top_mid, top_right) is None:
        raise RuntimeError("Fusion could not draw the ribbon exit top arc.")
    if lines.addByTwoPoints(top_right, bottom_right) is None:
        raise RuntimeError("Fusion could not draw the ribbon exit right seam.")
    if arcs.addByThreePoints(bottom_right, bottom_mid, bottom_left) is None:
        raise RuntimeError("Fusion could not draw the ribbon exit bottom arc.")
    if lines.addByTwoPoints(bottom_left, top_left) is None:
        raise RuntimeError("Fusion could not close the ribbon exit lobe.")
    if sketch.profiles.count != 1:
        raise RuntimeError("The ribbon exit lobe did not form one closed profile.")
    return sketch.profiles.item(0)


def _circular_profile(
    component: adsk.fusion.Component,
    center: adsk.core.Point3D,
    normal: adsk.core.Vector3D,
    diameter_mm: float,
) -> adsk.fusion.Profile:
    """
    Draw a target-side round section normal to the sampled route.
    """
    sketch = _section_sketch(component, center, normal)
    circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
        sketch.modelToSketchSpace(center), diameter_mm / 20.0
    )
    if circle is None or sketch.profiles.count != 1:
        raise RuntimeError("Fusion could not create a round ribbon exit section.")
    return sketch.profiles.item(0)


def _reverse_samples(route: RoutePreview) -> tuple[tuple[Vector3, Vector3], ...]:
    """
    Sample each cubic from the ribbon cap back toward its target without joins.
    """
    if not route.curves or all(
        magnitude(difference(curve.end, curve.start)) < 1e-6 for curve in route.curves
    ):
        raise ValueError("A ribbon exit requires at least two distinct route samples.")
    samples: list[tuple[Vector3, Vector3]] = []
    for curve in reversed(route.curves):
        for parameter in _SAMPLE_PARAMETERS:
            point = curve.point(parameter)
            if (
                samples
                and magnitude(
                    Vector3(
                        point.x - samples[-1][0].x,
                        point.y - samples[-1][0].y,
                        point.z - samples[-1][0].z,
                    )
                )
                < 1e-6
            ):
                continue
            samples.append((point, _sample_tangent(curve, parameter)))
    if len(samples) < 2:
        raise ValueError("A ribbon exit requires at least two distinct route samples.")
    return tuple(samples)


def _sample_tangent(curve: CubicBezier, parameter: float) -> Vector3:
    """
    Keep a stable section normal when a cubic has a zero endpoint handle.
    """
    derivative = curve.derivative(parameter)
    if magnitude(derivative) <= 1e-9:
        derivative = difference(curve.end, curve.start)
    return unit(derivative)


def build_ribbon_exit_loft(
    component: adsk.fusion.Component,
    ribbon: adsk.fusion.BRepBody,
    route: RoutePreview,
    end: RibbonExitEnd,
    line_index: int,
    ribbon_diameter_mm: float,
    cap_diameter_mm: float,
    transform: adsk.core.Matrix3D,
) -> adsk.fusion.BRepBody:
    """
    Create one solid branch in place, rooted in its fitted ribbon-end lobe.

    The result remains separate from the joined ribbon body. Its first section
    sits just inside the cap to provide a real solid overlap without a union.
    """
    face = _cap_face(ribbon, end, transform)
    cap_plane = adsk.core.Plane.cast(face.geometry)
    if cap_plane is None:
        raise RuntimeError("The ribbon exit has no planar cap geometry.")
    samples = _reverse_samples(route)
    axis = route_tail_axis(route)
    local_end = fusion_point(route.curves[-1].end, transform)
    local_tip = fusion_point(route.curves[-1].end.translated(axis, 10.0), transform)
    inward = adsk.core.Vector3D.create(
        local_tip.x - local_end.x,
        local_tip.y - local_end.y,
        local_tip.z - local_end.z,
    )
    if not inward.normalize():
        raise ValueError("The ribbon exit has no inward route direction.")
    origin = _project_to_cap(fusion_point(end.fit.centers[line_index], transform), face)
    origin.translateBy(
        adsk.core.Vector3D.create(
            inward.x * _INWARD_OVERLAP_MM / 10.0,
            inward.y * _INWARD_OVERLAP_MM / 10.0,
            inward.z * _INWARD_OVERLAP_MM / 10.0,
        )
    )
    sections = [
        _lobe_profile(
            component,
            origin,
            cap_plane.normal,
            end,
            line_index,
            ribbon_diameter_mm,
            transform,
        )
    ]
    for point, tangent in samples[1:]:
        center = fusion_point(point, transform)
        tip = fusion_point(point.translated(tangent, 10.0), transform)
        normal = adsk.core.Vector3D.create(tip.x - center.x, tip.y - center.y, tip.z - center.z)
        if not normal.normalize():
            raise ValueError("A ribbon exit section has no route tangent.")
        sections.append(_circular_profile(component, center, normal, cap_diameter_mm))
    loft_input = component.features.loftFeatures.createInput(
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    if loft_input is None:
        raise RuntimeError("Fusion could not define an in-place ribbon exit loft.")
    for section in sections:
        loft_input.loftSections.add(section)
    loft_input.isSolid = True
    loft = component.features.loftFeatures.add(loft_input)
    candidates = (
        []
        if loft is None
        else [body for body in loft.bodies if body.entityToken != ribbon.entityToken]
    )
    if len(candidates) != 1:
        raise RuntimeError("The ribbon exit loft did not produce one separate solid.")
    branch = candidates[0]
    if not branch.isValid or not branch.isSolid or branch.volume <= 0.0:
        raise RuntimeError("The ribbon exit loft did not retain a valid solid.")
    return branch
