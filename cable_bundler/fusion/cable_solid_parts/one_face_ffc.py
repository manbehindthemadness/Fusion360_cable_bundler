"""
Construct a single-side-face FFC sweep from ordered contact and route stations.
"""

from __future__ import annotations

import math

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...domain.ffc import FfcDimensions
from ...routing import Vector3
from ...routing.geometry import cross, difference, dot
from ..solid_ribbon import SOLID_RIBBON_LEAD_FRACTIONS, SolidRibbonPlan, SolidRibbonSection
from .metadata import fusion_point

END_TANGENT_HANDLE_MM = 3.0
CAP_PLANE_TOLERANCE_MM = 0.02
CAP_NORMAL_DOT_MINIMUM = 0.99999


def _midpoint(station: SolidRibbonSection) -> Vector3:
    """
    Return the middle of an ordered ribbon bank.
    """
    first, last = station.centers[0], station.centers[-1]
    return Vector3(
        (first.x + last.x) / 2.0,
        (first.y + last.y) / 2.0,
        (first.z + last.z) / 2.0,
    )


def sweep_station_indices(plan: SolidRibbonPlan) -> tuple[int, ...]:
    """
    Remove the two first destination-lead samples only for a reversed lead.

    The final two lead stations and exact contact station remain in order.
    This conditions sampled branch geometry, never persistent routing controls.
    """
    count = len(plan.sections)
    if count < 2:
        raise ValueError("FFC sweep needs two distinct stations.")
    lead_count = len(SOLID_RIBBON_LEAD_FRACTIONS)
    if count < lead_count * 2 + 2:
        return tuple(range(count))
    first_end_lead = count - lead_count
    previous = _midpoint(plan.sections[first_end_lead - 1])
    lead = _midpoint(plan.sections[first_end_lead])
    end_normal = plan.sections[-1].normal
    backward_mm = dot(difference(lead, previous), end_normal)
    if backward_mm >= -1e-6:
        return tuple(range(count))
    return (*range(first_end_lead), *range(first_end_lead + 2, count))


def _validate_contact_centers(plan: SolidRibbonPlan, dimensions: FfcDimensions) -> None:
    """
    Require each numbered generated lane to meet its actual Interface target.
    """
    line_count = len(plan.sections[0].centers)
    tolerance_mm = min(dimensions.pitch_mm * 0.05, dimensions.trace_width_mm * 0.10)
    for side, station in enumerate((plan.sections[0], plan.sections[-1])):
        targets = plan.contact_centers[side]
        ids = plan.contact_ids[side]
        if len(targets) != line_count or len(ids) != line_count or len(set(ids)) != line_count:
            raise RuntimeError("FFC contact identities or target centers are incomplete.")
        for line, (center, target) in enumerate(zip(station.centers, targets), start=1):
            error_mm = math.dist(
                (center.x, center.y, center.z),
                (target.x, target.y, target.z),
            )
            if error_mm > tolerance_mm:
                raise RuntimeError(
                    f"FFC line {line} misses its {('start', 'end')[side]} contact "
                    f"by {error_mm:.3f} mm (limit {tolerance_mm:.3f} mm)."
                )


def _path(
    component: adsk.fusion.Component,
    stations: tuple[SolidRibbonSection, ...],
    transform: adsk.core.Matrix3D,
    edge_offset_mm: float,
) -> adsk.fusion.Path:
    """
    Fit the center or edge spine, constrain its end, then create its Path.
    """
    sketch = component.sketches.add(component.xYConstructionPlane)
    if sketch is None:
        raise RuntimeError("Fusion could not create the FFC spine sketch.")
    sketch.is3D = True
    sketch.name = "FFC sweep centerline" if not edge_offset_mm else "FFC sweep bank rail"
    points = adsk.core.ObjectCollection.create()
    previous: Vector3 | None = None
    for station in stations:
        point = _midpoint(station).translated(station.width, edge_offset_mm)
        if (
            previous is not None
            and math.dist(
                (point.x, point.y, point.z),
                (previous.x, previous.y, previous.z),
            )
            < 0.001
        ):
            continue
        points.add(sketch.modelToSketchSpace(fusion_point(point, transform)))
        previous = point
    if points.count < 2:
        raise RuntimeError("The FFC spine has fewer than two distinct points.")
    spline = sketch.sketchCurves.sketchFittedSplines.add(points)
    if spline is None:
        raise RuntimeError("Fusion could not fit the FFC spine.")
    endpoint = spline.fitPoints.item(spline.fitPoints.count - 1)
    handle = spline.activateTangentHandle(endpoint)
    if handle is None or handle.startSketchPoint is None or handle.endSketchPoint is None:
        raise RuntimeError("Fusion could not activate the FFC end tangent.")
    target = _midpoint(stations[-1]).translated(stations[-1].width, edge_offset_mm)
    target = target.translated(stations[-1].normal, -END_TANGENT_HANDLE_MM)
    target_point = fusion_point(target, transform)
    fit_point = endpoint.worldGeometry
    moving = (
        handle.endSketchPoint
        if handle.startSketchPoint.worldGeometry.distanceTo(fit_point) < 1e-6
        else handle.startSketchPoint
    )
    current = moving.worldGeometry
    displacement = adsk.core.Vector3D.create(
        target_point.x - current.x,
        target_point.y - current.y,
        target_point.z - current.z,
    )
    if not moving.move(displacement) or moving.worldGeometry.distanceTo(target_point) > 1e-4:
        raise RuntimeError("Fusion could not aim the FFC end tangent at the contact.")
    path = component.features.createPath(spline, False)
    if path is None:
        raise RuntimeError("Fusion could not create the constrained FFC sweep path.")
    sketch.isLightBulbOn = False
    return path


def _outline(
    lines: int, dimensions: FfcDimensions, thickness_mm: float
) -> tuple[tuple[float, float], ...]:
    """
    Give every trace a flat land and every inter-trace web a shallow groove.
    """
    half_width = lines * dimensions.pitch_mm / 2.0
    half_height = thickness_mm / 2.0
    top: list[tuple[float, float]] = [(-half_width, half_height)]
    for index in range(lines):
        center = (index - (lines - 1) / 2.0) * dimensions.pitch_mm
        half_trace = dimensions.trace_width_mm / 2.0
        top.extend(
            (center + fraction * half_trace, half_height)
            for fraction in (-1.0, -0.5, 0.0, 0.5, 1.0)
        )
        if index < lines - 1:
            right = center + half_trace
            top.extend(
                (
                    right + dimensions.spacing_mm * fraction,
                    half_height - thickness_mm * 0.05 * depth_fraction,
                )
                for fraction, depth_fraction in ((0.25, 0.5), (0.5, 1.0), (0.75, 0.5))
            )
    top.append((half_width, half_height))
    bottom = [(across, -height) for across, height in reversed(top)]
    return ((-half_width, 0.0), *top, (half_width, 0.0), *bottom)


def _profile(
    component: adsk.fusion.Component,
    station: SolidRibbonSection,
    dimensions: FfcDimensions,
    thickness_mm: float,
    transform: adsk.core.Matrix3D,
) -> adsk.fusion.Profile:
    """
    Fit one closed profile curve with a designated left-edge seam.
    """
    origin = _midpoint(station)
    plane_input = component.constructionPlanes.createInput()
    point = fusion_point(origin, transform)
    normal_tip = fusion_point(origin.translated(station.normal, 10.0), transform)
    normal = adsk.core.Vector3D.create(
        normal_tip.x - point.x, normal_tip.y - point.y, normal_tip.z - point.z
    )
    if not normal.normalize() or not plane_input.setByPlane(adsk.core.Plane.create(point, normal)):
        raise RuntimeError("Fusion could not orient the FFC contact profile.")
    plane = component.constructionPlanes.add(plane_input)
    if plane is None:
        raise RuntimeError("Fusion could not create the FFC contact profile plane.")
    plane.isLightBulbOn = False
    sketch = component.sketches.add(plane)
    if sketch is None:
        raise RuntimeError("Fusion could not create the FFC profile sketch.")
    sketch.name = "One-face FFC contact profile"
    points = adsk.core.ObjectCollection.create()
    height_axis = cross(station.normal, station.width)
    for across, height in _outline(len(station.centers), dimensions, thickness_mm):
        world = origin.translated(station.width, across).translated(height_axis, height)
        points.add(sketch.modelToSketchSpace(fusion_point(world, transform)))
    spline = sketch.sketchCurves.sketchFittedSplines.add(points)
    if spline is None:
        raise RuntimeError("Fusion could not fit the FFC one-face outline.")
    spline.isClosed = True
    if sketch.profiles.count != 1:
        raise RuntimeError("The FFC outline did not make one closed profile.")
    profile = sketch.profiles.item(0)
    if profile.profileLoops.count != 1 or profile.profileLoops.item(0).profileCurves.count != 1:
        raise RuntimeError("Fusion split the FFC one-face profile into multiple curves.")
    sketch.isLightBulbOn = False
    return profile


def _audit_cap(
    cap: adsk.fusion.BRepFace,
    station: SolidRibbonSection,
    transform: adsk.core.Matrix3D,
) -> None:
    """
    Require every rendered cap node to meet its exact Interface contact plane.
    """
    plane = adsk.core.Plane.cast(cap.geometry)
    if plane is None:
        raise RuntimeError("The FFC contact cap is not planar.")
    origin = fusion_point(_midpoint(station), transform)
    normal_tip = fusion_point(_midpoint(station).translated(station.normal, 10.0), transform)
    contact_normal = adsk.core.Vector3D.create(
        normal_tip.x - origin.x,
        normal_tip.y - origin.y,
        normal_tip.z - origin.z,
    )
    if not contact_normal.normalize():
        raise RuntimeError("The FFC contact plane has no usable normal.")
    alignment = abs(
        plane.normal.x * contact_normal.x
        + plane.normal.y * contact_normal.y
        + plane.normal.z * contact_normal.z
    )
    if alignment < CAP_NORMAL_DOT_MINIMUM:
        raise RuntimeError("The FFC sweep cap is tilted away from its contact plane.")
    mesh = cap.meshManager.createMeshCalculator().calculate()
    if mesh is None or len(mesh.nodeCoordinates) == 0:
        raise RuntimeError("Fusion could not mesh the FFC contact cap for validation.")
    maximum_gap = max(
        abs(
            (node.x - origin.x) * contact_normal.x
            + (node.y - origin.y) * contact_normal.y
            + (node.z - origin.z) * contact_normal.z
        )
        * 10.0
        for node in mesh.nodeCoordinates
    )
    if maximum_gap > CAP_PLANE_TOLERANCE_MM:
        raise RuntimeError(f"The FFC cap misses its contact plane by {maximum_gap:.3f} mm.")


def build_one_face_ffc_sweep(
    component: adsk.fusion.Component,
    plan: SolidRibbonPlan,
    dimensions: FfcDimensions,
    thickness_mm: float,
    transform: adsk.core.Matrix3D,
) -> adsk.fusion.SweepFeature:
    """
    Build and validate one closed-profile sweep and its two contact caps.
    """
    _validate_contact_centers(plan, dimensions)
    stations = tuple(plan.sections[index] for index in sweep_station_indices(plan))
    edge_offset_mm = -len(stations[0].centers) * dimensions.pitch_mm / 2.0
    center_path = _path(component, stations, transform, 0.0)
    rail_path = _path(component, stations, transform, edge_offset_mm)
    profile = _profile(component, stations[0], dimensions, thickness_mm, transform)
    sweep_input = component.features.sweepFeatures.createInput(
        profile, center_path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    if sweep_input is None:
        raise RuntimeError("Fusion could not define the one-face FFC sweep.")
    sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    sweep_input.guideRail = rail_path
    sweep_input.profileScaling = adsk.fusion.SweepProfileScalingOptions.SweepProfileNoScalingOption
    feature = component.features.sweepFeatures.add(sweep_input)
    if feature is None or feature.bodies.count != 1:
        code, detail = adsk.core.Application.get().getLastError()
        raise RuntimeError(f"Fusion rejected the one-face FFC sweep ({code}: {detail}).")
    body = feature.bodies.item(0)
    if (
        body is None
        or not body.isSolid
        or not math.isfinite(body.volume)
        or body.volume <= 0.0
        or body.faces.count != 3
        or feature.sideFaces.count != 1
    ):
        raise RuntimeError("The FFC sweep lacks one solid and one continuous side face.")
    if feature.startFaces.count != 1 or feature.endFaces.count != 1:
        raise RuntimeError("The FFC sweep does not have exactly two contact caps.")
    _audit_cap(feature.startFaces.item(0), stations[0], transform)
    _audit_cap(feature.endFaces.item(0), stations[-1], transform)
    return feature
