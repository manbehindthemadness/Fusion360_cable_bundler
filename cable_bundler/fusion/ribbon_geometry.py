"""
Resolve open end guides into a banked frame shared by ribbon preview and output.
"""

from __future__ import annotations

from dataclasses import dataclass

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..application import CableGroupRouteLeg
from ..domain import HarnessDefinition, OpenGuideAlignment
from ..routing import (
    RibbonEndFit,
    RibbonFrame,
    RibbonShape,
    RoutePreview,
    Vector3,
    ribbon_frames,
    solve_ribbon_shape,
)
from ..routing.geometry import cross, difference, dot, magnitude, unit
from .route_preview_parts.frames import ProfileFrame, connection_profile_frames


@dataclass(frozen=True)
class RibbonGuidePlane:
    """
    Retain a guide's world plane when its sketch has no parametric reference.
    """

    origin: Vector3
    normal: Vector3
    reference_plane: adsk.core.Base | None = None


@dataclass(frozen=True)
class RibbonRouteShape:
    """
    Pair the common sampled shape with the Fusion guide planes needed by lofting.
    """

    shape: RibbonShape
    guide_planes: tuple[RibbonGuidePlane | None, RibbonGuidePlane | None]
    fit_warnings: tuple[str, ...]


def _guide_fit(
    design: adsk.fusion.Design,
    token: str,
    alignment: OpenGuideAlignment,
    frame: RibbonFrame,
    line_count: int,
    diameter_mm: float,
) -> tuple[RibbonEndFit, RibbonGuidePlane]:
    """
    Sample line centers at true arc lengths on a planar open-end sketch curve.
    """
    curve = next(
        (
            candidate
            for entity in design.findEntityByToken(token) or ()
            if (candidate := adsk.fusion.SketchCurve.cast(entity)) is not None and candidate.isValid
        ),
        None,
    )
    if curve is None:
        raise ValueError("the open guide is unavailable")
    sketch = curve.parentSketch
    evaluator = curve.worldGeometry.evaluator
    success, start_parameter, end_parameter = evaluator.getParameterExtents()
    if not success:
        raise ValueError("Fusion could not measure the open guide")
    success, guide_length = evaluator.getLengthAtParameter(start_parameter, end_parameter)
    if not success or guide_length <= 0.0:
        raise ValueError("the open guide has no measurable length")
    anchor = (
        0.0
        if alignment is OpenGuideAlignment.LEFT
        else guide_length
        if alignment is OpenGuideAlignment.RIGHT
        else guide_length / 2.0
    )
    x_direction = sketch.xDirection
    y_direction = sketch.yDirection
    plane_normal = unit(
        cross(
            Vector3(x_direction.x, x_direction.y, x_direction.z),
            Vector3(y_direction.x, y_direction.y, y_direction.z),
        )
    )

    def sample(offset: float) -> tuple[Vector3, Vector3]:
        """
        Resolve one signed ribbon-width offset onto the finite guide curve.
        """
        distance = anchor + offset
        if distance < -1e-8 or distance > guide_length + 1e-8:
            raise ValueError("the guide is too short for all lines at this alignment")
        success, parameter = evaluator.getParameterAtLength(
            start_parameter, max(0.0, min(guide_length, distance))
        )
        if not success:
            raise ValueError("Fusion could not sample the open guide")
        point_ok, point = evaluator.getPointAtParameter(parameter)
        tangent_ok, derivative = evaluator.getFirstDerivative(parameter)
        if not point_ok or not tangent_ok:
            raise ValueError("Fusion could not orient the open guide")
        tangent = unit(Vector3(derivative.x, derivative.y, derivative.z))
        normal = unit(cross(plane_normal, tangent))
        if dot(normal, frame.thickness) < 0.0:
            normal = Vector3(-normal.x, -normal.y, -normal.z)
        return Vector3(point.x * 10.0, point.y * 10.0, point.z * 10.0), normal

    center_samples = tuple(
        sample((index - (line_count - 1) / 2.0) * diameter_mm / 10.0) for index in range(line_count)
    )
    edge_samples = tuple(
        sample((index - line_count / 2.0) * diameter_mm / 10.0) for index in range(line_count + 1)
    )
    centers = tuple(point for point, _normal in center_samples)
    normals = tuple(normal for _point, normal in center_samples)
    for left, right in zip(centers, centers[1:]):
        pitch = magnitude(difference(right, left)) / diameter_mm
        if pitch < 0.8 or pitch > 1.1:
            raise ValueError("the guide bends too tightly for joined ribbon lobes")
    reference_plane = sketch.referencePlane if sketch.isParametric else None
    if sketch.isParametric and reference_plane is None:
        raise ValueError("the parametric guide sketch has no reference plane")
    origin = sketch.origin
    guide_plane = RibbonGuidePlane(
        Vector3(origin.x * 10.0, origin.y * 10.0, origin.z * 10.0),
        plane_normal,
        reference_plane,
    )
    return (
        RibbonEndFit(
            centers,
            normals,
            tuple(point for point, _normal in edge_samples),
            tuple(normal for _point, normal in edge_samples),
        ),
        guide_plane,
    )


def ribbon_route_shape(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    leg: CableGroupRouteLeg,
    route: RoutePreview,
    line_count: int,
    diameter_mm: float,
) -> RibbonRouteShape:
    """
    Build one terminal-aware shape for both preview and generated geometry.
    """
    frames = ribbon_route_frames(design, definition, leg, route)
    connections = {connection.connection_id: connection for connection in definition.connections}
    fits: list[RibbonEndFit | None] = []
    planes: list[RibbonGuidePlane | None] = []
    warnings = []
    for connection_id, frame, label in (
        (leg.start_connection_id, frames[0], "start"),
        (leg.end_connection_id, frames[-1], "end"),
    ):
        if connection_id is None:
            raise ValueError("A discrete ribbon requires two physical open ends.")
        connection = connections[connection_id]
        try:
            fit, plane = _guide_fit(
                design,
                connection.member_tokens[0],
                connection.resolved_member_alignments[0],
                frame,
                line_count,
                diameter_mm,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            fits.append(None)
            planes.append(None)
            warnings.append(f"{label} ribbon end did not fit its guide ({error})")
        else:
            fits.append(fit)
            planes.append(plane)
    shape = solve_ribbon_shape(frames, line_count, diameter_mm, start_fit=fits[0], end_fit=fits[1])
    if shape.maximum_pitch_ratio > 1.10 + 1e-6 and any(fit is not None for fit in fits):
        warnings.append(
            "guide-fitted ends would exceed the 10% adjacent-line pitch allowance; "
            "using unfitted ends"
        )
        shape = solve_ribbon_shape(frames, line_count, diameter_mm)
        planes = [None, None]
    return RibbonRouteShape(shape, (planes[0], planes[1]), tuple(warnings))


def ribbon_route_frames(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    leg: CableGroupRouteLeg,
    route: RoutePreview,
    *,
    maximum_sections: int = 32,
) -> tuple[RibbonFrame, ...]:
    """
    Carry each end's curve direction through one two-ended discrete ribbon leg.
    """
    if leg.start_connection_id is None or leg.end_connection_id is None:
        raise ValueError("A discrete ribbon requires two physical open ends.")
    connections = {connection.connection_id: connection for connection in definition.connections}
    start = connections[leg.start_connection_id]
    end = connections[leg.end_connection_id]
    cache: dict[str, ProfileFrame] = {}
    start_width = connection_profile_frames(design, start, cache)[0].u_direction
    end_width = connection_profile_frames(design, end, cache)[0].u_direction
    return ribbon_frames(route, start_width, end_width, maximum_sections=maximum_sections)
