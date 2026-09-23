"""Build target-conforming solder-weld bodies at finalized cable endpoints."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...domain import CableWeldSettings
from ...routing import RoutePreview
from ...routing.geometry import difference, lerp, magnitude
from .metadata import fusion_point
from .sweep_geometry import split_route_for_pullback


@dataclass(frozen=True)
class WeldEndpoint:
    """Describe one resolved leaf weld and its optional conforming target face."""

    attachment_id: UUID
    target_face: Optional[adsk.fusion.BRepFace]
    conductor_diameter_mm: float
    settings: CableWeldSettings

    def __post_init__(self) -> None:
        """Require usable identity, sizing, and target geometry."""
        if not isinstance(self.attachment_id, UUID):
            raise ValueError("Weld attachment identity is invalid.")
        if (
            isinstance(self.conductor_diameter_mm, bool)
            or not isinstance(self.conductor_diameter_mm, (int, float))
            or not math.isfinite(self.conductor_diameter_mm)
            or self.conductor_diameter_mm <= 0.0
        ):
            raise ValueError("Weld conductor diameter must be finite and positive.")
        if not isinstance(self.settings, CableWeldSettings):
            raise ValueError("Weld material settings are invalid.")

    @property
    def diameter_mm(self) -> float:
        """Return the configured maximum weld diameter in millimeters."""
        return self.conductor_diameter_mm * self.settings.value / 100.0

    @property
    def radius_mm(self) -> float:
        """Return both the maximum weld radius and requested axial reach."""
        return self.diameter_mm / 2.0


@dataclass(frozen=True)
class WeldBuildResult:
    """Return the retained weld body and its applied axial reach."""

    body: adsk.fusion.BRepBody
    length_mm: float


def _persist_temporary_body(
    component: adsk.fusion.Component,
    temporary_body: adsk.fusion.BRepBody,
    name: str,
    *,
    hidden: bool = True,
) -> adsk.fusion.BRepBody:
    """Persist one transient body in the generated component."""
    design = component.parentDesign
    if design is not None and design.designType == adsk.fusion.DesignTypes.DirectDesignType:
        result_body = component.bRepBodies.add(temporary_body)
        if result_body is None:
            raise RuntimeError("Fusion could not persist a direct weld helper body.")
        result_body.name = name
        result_body.isLightBulbOn = not hidden
        return result_body
    base_feature = component.features.baseFeatures.add()
    if base_feature is None or not base_feature.startEdit():
        raise RuntimeError("Fusion could not start a weld helper feature.")
    try:
        source_body = component.bRepBodies.add(temporary_body, base_feature)
        if source_body is None:
            raise RuntimeError("Fusion could not persist a weld helper body.")
    finally:
        base_feature.finishEdit()
    if base_feature.bodies.count != 1:
        raise RuntimeError("Fusion did not retain one weld helper body.")
    result_body = base_feature.bodies.item(0)
    if result_body is None:
        raise RuntimeError("Fusion did not retain the weld helper result.")
    base_feature.name = name
    result_body.name = name
    result_body.isLightBulbOn = not hidden
    return result_body


def _build_weld_ball(
    component: adsk.fusion.Component,
    center: adsk.core.Point3D,
    radius_mm: float,
    name: str,
) -> adsk.fusion.BRepBody:
    """Create a separate spherical weld fallback at a local connection point."""
    manager = adsk.fusion.TemporaryBRepManager.get()
    if manager is None:
        raise RuntimeError("Fusion temporary B-Rep services are unavailable.")
    temporary_body = manager.createSphere(center, radius_mm / 10.0)
    if temporary_body is None:
        raise RuntimeError("Fusion could not create the fallback weld sphere.")
    result_body = _persist_temporary_body(
        component,
        temporary_body,
        name,
        hidden=False,
    )
    if (
        not result_body.isSolid
        or not math.isfinite(result_body.volume)
        or result_body.volume <= 0.0
    ):
        raise RuntimeError("Fusion produced an invalid fallback weld sphere.")
    return result_body


def _remove_failed_helper(body: Optional[adsk.fusion.BRepBody]) -> None:
    """Remove one retained helper before changing to spherical fallback geometry."""
    if body is not None and body.isValid and not body.deleteMe():
        raise RuntimeError("Fusion could not remove failed weld helper geometry.")


def _log_face_fallback(
    endpoint: WeldEndpoint,
    name: str,
    stage: str,
    error: Exception,
) -> None:
    """Record a recoverable face-conformance failure in Fusion's file log."""
    adsk.core.Application.log(
        (
            "Cable Bundler used spherical weld fallback: "
            f"name={name!r}, attachment_id={endpoint.attachment_id}, "
            f"stage={stage!r}, error={error}"
        ),
        adsk.core.LogLevels.InfoLogLevel,
        adsk.core.LogTypes.FileLogType,
    )


def _local_target_patch(
    component: adsk.fusion.Component,
    target_face: adsk.fusion.BRepFace,
    transform: adsk.core.Matrix3D,
    target_point: adsk.core.Point3D,
    conductor_point: adsk.core.Point3D,
    radius_cm: float,
    name: str,
) -> adsk.fusion.BRepBody:
    """Trim a target-face copy to the weld footprint in component coordinates."""
    manager = adsk.fusion.TemporaryBRepManager.get()
    if manager is None:
        raise RuntimeError("Fusion temporary B-Rep services are unavailable.")
    temporary_body = manager.copy(target_face)
    if temporary_body is None or not manager.transform(temporary_body, transform):
        raise RuntimeError("Fusion could not transform the weld target face locally.")
    direction = target_point.vectorTo(conductor_point)
    if direction.length <= 1e-9 or not direction.normalize():
        raise RuntimeError("Fusion could not normalize the local weld footprint axis.")
    extension = direction.copy()
    if not extension.scaleBy(-max(radius_cm, 0.01)):
        raise RuntimeError("Fusion could not extend the local weld footprint axis.")
    back_point = target_point.copy()
    if not back_point.translateBy(extension):
        raise RuntimeError("Fusion could not position the local weld footprint tool.")
    footprint_tool = manager.createCylinderOrCone(
        back_point,
        radius_cm,
        conductor_point,
        radius_cm,
    )
    if footprint_tool is None or not manager.booleanOperation(
        temporary_body,
        footprint_tool,
        adsk.fusion.BooleanTypes.IntersectionBooleanType,
    ):
        raise RuntimeError("Fusion could not trim the local weld target footprint.")
    return _persist_temporary_body(component, temporary_body, name)


def _local_axis_edge(
    component: adsk.fusion.Component,
    target_point: adsk.core.Point3D,
    conductor_point: adsk.core.Point3D,
    name: str,
) -> tuple[adsk.fusion.BRepBody, adsk.fusion.BRepEdge]:
    """Create a hidden local guide body whose longest edge is the true 3D weld axis."""
    manager = adsk.fusion.TemporaryBRepManager.get()
    if manager is None:
        raise RuntimeError("Fusion temporary B-Rep services are unavailable.")
    length_direction = target_point.vectorTo(conductor_point)
    length_cm = length_direction.length
    if length_cm <= 1e-9 or not length_direction.normalize():
        raise RuntimeError("Fusion could not normalize the local weld axis.")
    reference = adsk.core.Vector3D.create(0.0, 0.0, 1.0)
    if abs(length_direction.dotProduct(reference)) > 0.9:
        reference = adsk.core.Vector3D.create(1.0, 0.0, 0.0)
    width_direction = length_direction.crossProduct(reference)
    if width_direction is None or not width_direction.normalize():
        raise RuntimeError("Fusion could not orient the local weld axis guide.")
    center = adsk.core.Point3D.create(
        (target_point.x + conductor_point.x) / 2.0,
        (target_point.y + conductor_point.y) / 2.0,
        (target_point.z + conductor_point.z) / 2.0,
    )
    bounds = adsk.core.OrientedBoundingBox3D.create(
        center,
        length_direction,
        width_direction,
        length_cm,
        1e-5,
        1e-5,
    )
    temporary_body = None if bounds is None else manager.createBox(bounds)
    if temporary_body is None:
        raise RuntimeError("Fusion could not create the local weld axis guide.")
    guide_body = _persist_temporary_body(component, temporary_body, name)
    axis = max(
        (
            edge
            for index in range(guide_body.edges.count)
            if (edge := guide_body.edges.item(index)) is not None
        ),
        key=lambda edge: edge.length,
        default=None,
    )
    if axis is None:
        raise RuntimeError("Fusion did not retain the local weld axis edge.")
    return guide_body, axis


def build_weld_body(
    component: adsk.fusion.Component,
    route: RoutePreview,
    transform: adsk.core.Matrix3D,
    endpoint: WeldEndpoint,
    name: str,
) -> WeldBuildResult:
    """Build a conforming face weld or a spherical connection-point fallback.

    The weld reaches one configured radius along the target-facing route,
    clamped only by the available route. Face targets use a localized surface
    section when possible. Other target kinds, and face operations Fusion
    rejects, use a full sphere centered on the connection point. The sphere
    naturally intersects the conductor at its radius without joining either
    neighboring body.
    """
    if endpoint.radius_mm <= 1e-9:
        raise ValueError("Weld diameter must be positive to create geometry.")
    split = split_route_for_pullback(route, endpoint.radius_mm)
    weld_route = split.pullback
    if weld_route is None or split.pullback_length_mm <= 1e-9:
        raise ValueError("Weld route has no usable length.")
    target_point = weld_route.curves[0].start
    conductor_point = weld_route.curves[-1].end
    chord = difference(conductor_point, target_point)
    if magnitude(chord) <= 1e-9:
        raise ValueError("Weld route endpoints must be distinct.")
    top_radius_mm = min(endpoint.radius_mm, endpoint.conductor_diameter_mm / 2.0)
    sections = (
        (0.0, endpoint.radius_mm, "Target"),
        (0.55, max(top_radius_mm, endpoint.radius_mm * 0.8), "Crown"),
        (1.0, top_radius_mm, "Conductor"),
    )

    local_target_point = fusion_point(target_point, transform)
    if endpoint.target_face is None:
        try:
            ball = _build_weld_ball(component, local_target_point, endpoint.radius_mm, name)
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            raise RuntimeError(f"create fallback weld sphere: {error}") from error
        return WeldBuildResult(ball, split.pullback_length_mm)

    stage = "localize weld target face"
    local_target_surface: Optional[adsk.fusion.BRepBody] = None
    axis_body: Optional[adsk.fusion.BRepBody] = None
    conforming_body: Optional[adsk.fusion.BRepBody] = None
    try:
        local_conductor_point = fusion_point(conductor_point, transform)
        local_target_surface = _local_target_patch(
            component,
            endpoint.target_face,
            transform,
            local_target_point,
            local_conductor_point,
            endpoint.radius_mm / 10.0,
            f"{name} Local Target",
        )
        local_target_faces = tuple(
            face
            for index in range(local_target_surface.faces.count)
            if (face := local_target_surface.faces.item(index)) is not None
        )
        if not local_target_faces:
            raise RuntimeError("Fusion did not retain the localized weld target face.")
        local_target_face = min(
            local_target_faces,
            key=lambda face: face.pointOnFace.distanceTo(local_target_point),
        )
        stage = "create local weld axis"
        axis_body, axis = _local_axis_edge(
            component,
            local_target_point,
            local_conductor_point,
            f"{name} Local Axis",
        )
        axis_start_vertex = axis.startVertex
        if axis_start_vertex is None:
            raise RuntimeError("Fusion did not retain the local weld axis start point.")
        axis_start = axis_start_vertex.geometry
        axis_is_reversed = axis_start.distanceTo(local_target_point) > axis_start.distanceTo(
            local_conductor_point
        )

        target_profile: Optional[adsk.fusion.Profile] = None
        loft_profiles: list[adsk.fusion.Profile] = []
        for parameter, radius_mm, label in sections:
            stage = f"create weld {label.lower()} section"
            axis_parameter = 1.0 - parameter if axis_is_reversed else parameter
            plane_input = component.constructionPlanes.createInput()
            if not plane_input.setByDistanceOnPath(
                axis,
                adsk.core.ValueInput.createByReal(axis_parameter),
            ):
                raise RuntimeError("Fusion could not orient a weld section.")
            plane = component.constructionPlanes.add(plane_input)
            if plane is None:
                raise RuntimeError("Fusion did not create a weld section plane.")
            plane.name = f"{name} {label} Diameter"
            section = component.sketches.add(plane)
            if section is None:
                raise RuntimeError("Fusion did not create a weld section sketch.")
            section.name = f"{name} {label} Diameter"
            center_point = lerp(target_point, conductor_point, parameter)
            center = section.modelToSketchSpace(fusion_point(center_point, transform))
            circle = section.sketchCurves.sketchCircles.addByCenterRadius(
                center,
                radius_mm / 10.0,
            )
            if circle is None or section.profiles.count != 1:
                raise RuntimeError("Fusion could not create one weld section profile.")
            profile = section.profiles.item(0)
            if profile is None:
                raise RuntimeError("Fusion did not retain a weld section profile.")
            if label == "Target":
                target_profile = profile
            else:
                loft_profiles.append(profile)
            section.isLightBulbOn = False
            plane.isLightBulbOn = False

        if target_profile is None or len(loft_profiles) != 2:
            raise RuntimeError("Fusion did not retain the weld loft sections.")

        stage = "create weld loft"
        lofts = component.features.loftFeatures
        loft_input = lofts.createInput(adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        if loft_input is None:
            raise RuntimeError("Fusion could not define the weld loft.")
        target_is_planar = adsk.core.Plane.cast(local_target_face.geometry) is not None
        target_section = target_profile if target_is_planar else local_target_face
        if target_is_planar and not local_target_surface.deleteMe():
            raise RuntimeError("Fusion could not remove the planar weld target helper.")
        if target_is_planar:
            local_target_surface = None
        if loft_input.loftSections.add(target_section) is None:
            raise RuntimeError("Fusion could not add the localized weld footprint.")
        for profile in loft_profiles:
            if loft_input.loftSections.add(profile) is None:
                raise RuntimeError("Fusion could not add a weld loft section.")
        loft_input.isSolid = True
        loft_input.isClosed = False
        loft_input.isTangentEdgesMerged = True
        loft = lofts.add(loft_input)
        if loft is None or loft.bodies.count != 1:
            raise RuntimeError("Fusion did not produce one weld body.")
        conforming_body = loft.bodies.item(0)
        if conforming_body is None or not conforming_body.isSolid:
            raise RuntimeError("Fusion produced an invalid weld body.")
        loft.name = f"{name} Loft"
        if not math.isfinite(conforming_body.volume) or conforming_body.volume <= 0.0:
            raise RuntimeError("Fusion produced an invalid or empty weld body.")
        stage = "remove weld helper bodies"
        target_removed = target_is_planar or local_target_surface.deleteMe()
        axis_removed = axis_body.deleteMe()
        if not target_removed or not axis_removed:
            raise RuntimeError("Fusion could not remove the local weld helper bodies.")
        conforming_body.name = name
        return WeldBuildResult(conforming_body, split.pullback_length_mm)
    except (AttributeError, RuntimeError, TypeError, ValueError) as face_error:
        try:
            _remove_failed_helper(conforming_body)
            _remove_failed_helper(local_target_surface)
            _remove_failed_helper(axis_body)
            _log_face_fallback(endpoint, name, stage, face_error)
            ball = _build_weld_ball(component, local_target_point, endpoint.radius_mm, name)
        except (AttributeError, RuntimeError, TypeError, ValueError) as fallback_error:
            raise RuntimeError(
                f"{stage}: {face_error}; create fallback weld sphere: {fallback_error}"
            ) from fallback_error
        return WeldBuildResult(ball, split.pullback_length_mm)
