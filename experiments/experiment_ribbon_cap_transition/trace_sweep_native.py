"""
Construct one complete diagnostic candidate with one circular sweep per trace.

No lofts, section arrays, joining operations, fallback geometry or shape repairs.
Direct feature cap references keep the routine native audit proportional to traces.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3

from .endpoint_caps import cap_matches
from .endpoint_first import EndpointCase
from .endpoint_trace_paths import TracePath, plan_trace_sweeps
from .native_budget import NativeBudget


def _point(point: Vector3) -> adsk.core.Point3D:
    """
    Convert an experiment point in millimeters to Fusion centimeters.
    """
    return adsk.core.Point3D.create(point.x / 10, point.y / 10, point.z / 10)


def _author(
    component: adsk.fusion.Component, path: TracePath, case: EndpointCase
) -> tuple[adsk.fusion.Profile, adsk.fusion.Path]:
    """
    Author one exact cubic-chain NURBS path and its circular initial profile.
    """
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketch.name = f"Trace {path.number:02} path"
    points = [sketch.modelToSketchSpace(_point(p)) for p in path.controls]
    curve = adsk.core.NurbsCurve3D.createNonRational(points, 3, list(path.knots), False)
    if curve is None:
        raise RuntimeError("Native NURBS creation failed.")
    entity = sketch.sketchCurves.sketchFixedSplines.addByNurbsCurve(curve)
    if entity is None:
        raise RuntimeError("Native trace path sketch failed.")
    native_path = component.features.createPath(entity, False)
    if native_path is None:
        raise RuntimeError("Native sweep path creation failed.")
    plane_input = component.constructionPlanes.createInput()
    normal = adsk.core.Vector3D.create(
        case.start_tangent.x, case.start_tangent.y, case.start_tangent.z
    )
    if not plane_input.setByPlane(adsk.core.Plane.create(_point(path.controls[0]), normal)):
        raise RuntimeError("Native trace profile plane failed.")
    plane = component.constructionPlanes.add(plane_input)
    profile = component.sketches.add(plane)
    profile.name = f"Trace {path.number:02} circular profile"
    circle = profile.sketchCurves.sketchCircles.addByCenterRadius(
        profile.modelToSketchSpace(_point(path.controls[0])), case.diameter_mm / 20
    )
    if circle is None or profile.profiles.count != 1:
        raise RuntimeError("Native trace profile is not one circle.")
    sketch.isLightBulbOn = False
    plane.isLightBulbOn = False
    profile.isLightBulbOn = False
    return profile.profiles.item(0), native_path


def _check_cap(faces: adsk.fusion.BRepFaces, endpoint: Vector3, tangent: Vector3) -> bool:
    """
    Inspect exactly the feature-provided cap, with no body-wide face enumeration.
    """
    if faces is None or faces.count != 1:
        return False
    face = faces.item(0)
    plane = adsk.core.Plane.cast(face.geometry)
    if plane is None:
        return False
    box = face.boundingBox
    return cap_matches(
        endpoint,
        tangent,
        Vector3(10 * plane.origin.x, 10 * plane.origin.y, 10 * plane.origin.z),
        Vector3(plane.normal.x, plane.normal.y, plane.normal.z),
        Vector3(
            5 * (box.minPoint.x + box.maxPoint.x),
            5 * (box.minPoint.y + box.maxPoint.y),
            5 * (box.minPoint.z + box.maxPoint.z),
        ),
    )


def build_candidate(
    case: EndpointCase, row: dict[str, Any], slot: int, budget: NativeBudget
) -> None:
    """
    Plan once, then construct and lightly inspect every ordered trace once.

    Record solver, authoring, kernel and audit wall times separately, including
    partial failures. No full-volume integration, surface sampling or pairwise
    interference scan runs. Circular per-trace bodies are not the bonded outline.
    """
    started = perf_counter()
    row.update(
        evaluated=True,
        traces_attempted=0,
        traces_built=0,
        traces_cap_checked=0,
    )
    try:
        paths, numerical = plan_trace_sweeps(case)
    finally:
        row["numerical_seconds"] = perf_counter() - started
    row["numerical"] = numerical
    row.update(section_seconds=0.0, sweep_seconds=0.0, audit_seconds=0.0)
    budget.check("candidate_component")
    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    if design is None:
        raise RuntimeError("Owned design unavailable.")
    transform = adsk.core.Matrix3D.create()
    transform.translation = adsk.core.Vector3D.create(48, (slot - 8) * 16, 0)
    occurrence = design.rootComponent.occurrences.addNewComponent(transform)
    component = occurrence.component
    component.name = f"{slot + 1} - swept {case.name}"
    for path in paths:
        budget.check(f"trace_{path.number}_authoring")
        author_started = perf_counter()
        try:
            profile, native_path = _author(component, path, case)
            inputs = component.features.sweepFeatures.createInput(
                profile, native_path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )
            inputs.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
        finally:
            row["section_seconds"] += perf_counter() - author_started
        budget.check(f"trace_{path.number}_sweep")
        row["native_attempted"] = True
        row["traces_attempted"] += 1
        native_started = perf_counter()
        try:
            feature = component.features.sweepFeatures.add(inputs)
        finally:
            row["sweep_seconds"] += perf_counter() - native_started
        if feature is None or feature.bodies.count != 1 or not feature.bodies.item(0).isSolid:
            raise RuntimeError(f"Trace {path.number} sweep did not produce one solid.")
        body = feature.bodies.item(0)
        body.name = f"{case.name} - trace {path.number:02}"
        body.attributes.add("endpoint_experiment", "trace_number", str(path.number))
        row["traces_built"] += 1
        audit_started = perf_counter()
        try:
            if not _check_cap(
                feature.startFaces, path.controls[0], case.start_tangent
            ) or not _check_cap(feature.endFaces, path.controls[-1], case.end_tangent):
                raise RuntimeError(f"Trace {path.number} native cap check failed.")
            row["traces_cap_checked"] += 1
        finally:
            row["audit_seconds"] += perf_counter() - audit_started
    row.update(
        built=True,
        status="built_partial_audit",
        unmeasured=[
            "native inter-trace clearance",
            "native strain and full physical compliance",
            "continuous native banking",
        ],
    )
