"""Probe conforming and spherical welds inside an isolated live Fusion design."""

from __future__ import annotations

import math
from typing import Callable, Optional
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import CableWeldSettings
from cable_bundler.fusion.cable_solid_parts.welds import WeldEndpoint, build_weld_body
from cable_bundler.routing import CubicBezier, RoutePreview, Vector3


def _point_coordinate(point: object, name: str) -> float:
    """Read one finite numeric coordinate from host-owned point geometry."""
    value = getattr(point, name, None)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RuntimeError(f"Fusion returned an invalid target-point {name}-coordinate.")
    return float(value)


def _straight_route(start: Vector3, end: Vector3) -> RoutePreview:
    """Create one exact straight cubic route between millimeter points."""
    first = Vector3(
        start.x + (end.x - start.x) / 3.0,
        start.y + (end.y - start.y) / 3.0,
        start.z + (end.z - start.z) / 3.0,
    )
    second = Vector3(
        start.x + (end.x - start.x) * 2.0 / 3.0,
        start.y + (end.y - start.y) * 2.0 / 3.0,
        start.z + (end.z - start.z) * 2.0 / 3.0,
    )
    curve = CubicBezier(start, first, second, end)
    return RoutePreview(uuid4(), "Weld projection probe", (start, end), (curve,))


def _rectangle_profile(
    component: adsk.fusion.Component,
    half_size_cm: float,
) -> adsk.fusion.Profile:
    """Create a centered rectangle on the component YZ plane."""
    sketch = component.sketches.add(component.yZConstructionPlane)
    lines = sketch.sketchCurves.sketchLines
    lines.addTwoPointRectangle(
        adsk.core.Point3D.create(-half_size_cm, -half_size_cm, 0.0),
        adsk.core.Point3D.create(half_size_cm, half_size_cm, 0.0),
    )
    profile = sketch.profiles.item(0)
    if profile is None:
        raise RuntimeError("Fusion did not create the planar probe profile.")
    return profile


def _planar_target(component: adsk.fusion.Component) -> tuple[adsk.fusion.BRepFace, Vector3]:
    """Create a planar target whose connection point is the origin."""
    profile = _rectangle_profile(component, 0.4)
    extrude = component.features.extrudeFeatures.addSimple(
        profile,
        adsk.core.ValueInput.createByReal(-1.0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    face = None if extrude is None else extrude.startFaces.item(0)
    if face is None:
        raise RuntimeError("Fusion did not create the planar probe target.")
    return face, Vector3(0.0, 0.0, 0.0)


def _curved_target(component: adsk.fusion.Component) -> tuple[adsk.fusion.BRepFace, Vector3]:
    """Create a cylindrical target with a known outward connection point."""
    sketch = component.sketches.add(component.yZConstructionPlane)
    circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(1.5, 0.0, 0.0),
        0.4,
    )
    if circle is None or sketch.profiles.count != 1:
        raise RuntimeError("Fusion did not create the curved probe profile.")
    extrude = component.features.extrudeFeatures.addSimple(
        sketch.profiles.item(0),
        adsk.core.ValueInput.createByReal(1.0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    face = None if extrude is None else extrude.sideFaces.item(0)
    if face is None:
        raise RuntimeError("Fusion did not create the curved probe target.")
    target_point = getattr(face, "pointOnFace", None)
    if target_point is None:
        raise RuntimeError("Fusion did not retain a point on the curved target.")
    point_x = _point_coordinate(target_point, "x")
    point_y = _point_coordinate(target_point, "y")
    point_z = _point_coordinate(target_point, "z")
    return face, Vector3(
        point_x * 10.0,
        point_y * 10.0,
        point_z * 10.0,
    )


def _oblique_target(component: adsk.fusion.Component) -> tuple[adsk.fusion.BRepFace, Vector3]:
    """Create a planar target proxy in a rotated and translated occurrence."""
    transform = adsk.core.Matrix3D.create()
    axis = adsk.core.Vector3D.create(0.0, 1.0, 1.0)
    if not axis.normalize() or not transform.setToRotation(
        math.radians(37.0),
        axis,
        adsk.core.Point3D.create(0.0, 0.0, 0.0),
    ):
        raise RuntimeError("Fusion could not orient the oblique target occurrence.")
    transform.translation = adsk.core.Vector3D.create(2.0, -1.0, 0.5)
    occurrence = component.occurrences.addNewComponent(transform)
    if occurrence is None:
        raise RuntimeError("Fusion did not create the oblique target occurrence.")
    occurrence.component.name = "Oblique Weld Target"
    native_face, _ = _planar_target(occurrence.component)
    proxy_face = native_face.createForAssemblyContext(occurrence)
    if proxy_face is None:
        raise RuntimeError("Fusion did not create the oblique target face proxy.")
    target_point = proxy_face.pointOnFace
    if target_point is None:
        raise RuntimeError("Fusion did not retain an oblique target point.")
    return proxy_face, Vector3(
        _point_coordinate(target_point, "x") * 10.0,
        _point_coordinate(target_point, "y") * 10.0,
        _point_coordinate(target_point, "z") * 10.0,
    )


def _probe_case(
    root: adsk.fusion.Component,
    label: str,
    target_factory: Callable[
        [adsk.fusion.Component],
        tuple[adsk.fusion.BRepFace, Vector3],
    ],
) -> dict[str, object]:
    """Build one production weld against a generated target and report its body."""
    target_face, start = target_factory(root)
    normal_result, normal = target_face.evaluator.getNormalAtPoint(
        adsk.core.Point3D.create(start.x / 10.0, start.y / 10.0, start.z / 10.0)
    )
    if not normal_result or normal is None:
        raise RuntimeError("Fusion did not evaluate the weld target normal.")
    end = Vector3(
        start.x + normal.x * 10.0,
        start.y + normal.y * 10.0,
        start.z + normal.z * 10.0,
    )
    occurrence = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    if occurrence is None:
        raise RuntimeError("Fusion did not create the weld probe component.")
    occurrence.component.name = f"Weld Local-Frame Probe {label.title()}"
    result = build_weld_body(
        occurrence.component,
        _straight_route(start, end),
        adsk.core.Matrix3D.create(),
        WeldEndpoint(uuid4(), target_face, 2.0, CableWeldSettings()),
        f"{label.title()} Weld",
    )
    return {
        "bodyCount": occurrence.component.bRepBodies.count,
        "faceCount": result.body.faces.count,
        "isSolid": bool(result.body.isSolid),
        "lengthMm": result.length_mm,
        "targetNormal": [normal.x, normal.y, normal.z],
        "targetPointMm": [start.x, start.y, start.z],
        "volumeCm3": result.body.volume,
    }


def _probe_ball_case(
    root: adsk.fusion.Component,
    label: str,
    target_face: Optional[adsk.fusion.BRepFace],
) -> dict[str, object]:
    """Build one production spherical fallback and report its retained body."""
    start = Vector3(10.0 if target_face is not None else 0.0, 0.0, 0.0)
    end = Vector3(start.x + 10.0, start.y, start.z)
    occurrence = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    if occurrence is None:
        raise RuntimeError("Fusion did not create the weld-ball probe component.")
    occurrence.component.name = f"Weld Ball Probe {label.title()}"
    result = build_weld_body(
        occurrence.component,
        _straight_route(start, end),
        adsk.core.Matrix3D.create(),
        WeldEndpoint(uuid4(), target_face, 2.0, CableWeldSettings()),
        f"{label.title()} Weld",
    )
    if result.body.faces.count != 1:
        raise RuntimeError("Fusion did not produce a one-face spherical weld fallback.")
    return {
        "bodyCount": occurrence.component.bRepBodies.count,
        "faceCount": result.body.faces.count,
        "isSolid": bool(result.body.isSolid),
        "lengthMm": result.length_mm,
        "targetNormal": [1.0, 0.0, 0.0],
        "targetPointMm": [start.x, start.y, start.z],
        "volumeCm3": result.body.volume,
    }


def _capture_case(
    application: adsk.core.Application,
    capture_path: str,
    label: str,
    target_point_mm: list[float],
    target_normal: list[float],
) -> dict[str, object]:
    """Capture one close isometric view centered on a probe contact point."""
    stem, separator, suffix = capture_path.rpartition(".")
    case_path = f"{stem}_{label}.{suffix}" if separator else f"{capture_path}_{label}.png"
    viewport = application.activeViewport
    camera = viewport.camera
    camera.isSmoothTransition = False
    target = adsk.core.Point3D.create(
        target_point_mm[0] / 10.0,
        target_point_mm[1] / 10.0,
        target_point_mm[2] / 10.0,
    )
    camera.target = target
    camera.eye = adsk.core.Point3D.create(
        target.x + target_normal[0] * 5.0 + 2.0,
        target.y + target_normal[1] * 5.0,
        target.z + target_normal[2] * 5.0 + 2.0,
    )
    camera.upVector = adsk.core.Vector3D.create(0.0, 0.0, 1.0)
    camera.viewExtents = 2.0
    viewport.camera = camera
    viewport.refresh()
    return {
        "path": case_path,
        "saved": bool(viewport.saveAsImageFile(case_path, 1200, 900)),
    }


def run_projection_probe(capture_path: str = "") -> dict[str, object]:
    """Run all weld cases, optionally capture the viewport, and close unsaved."""
    application = adsk.core.Application.get()
    if application is None:
        raise RuntimeError("Fusion is unavailable for the weld projection probe.")
    previous_document = application.activeDocument
    initial_document_count = application.documents.count
    probe_document = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if probe_document is None:
        raise RuntimeError("Fusion did not create the isolated weld probe document.")
    results: dict[str, object] = {}
    try:
        design = adsk.fusion.Design.cast(application.activeProduct)
        if design is None:
            raise RuntimeError("Fusion did not activate the weld probe design.")
        design.designIntent = adsk.fusion.DesignIntentTypes.HybridDesignIntentType
        root = design.rootComponent
        captures: dict[str, object] = {}
        cases = (
            ("planar", _planar_target),
            ("curved", _curved_target),
            ("oblique", _oblique_target),
        )
        for label, factory in cases:
            try:
                case_result = _probe_case(root, label, factory)
                results[label] = {"status": "passed", **case_result}
                if capture_path:
                    target_point_mm = case_result["targetPointMm"]
                    target_normal = case_result["targetNormal"]
                    if not isinstance(target_point_mm, list) or not isinstance(target_normal, list):
                        raise RuntimeError("The weld probe omitted its target frame.")
                    captures[label] = _capture_case(
                        application,
                        capture_path,
                        label,
                        target_point_mm,
                        target_normal,
                    )
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                results[label] = {"status": "failed", "error": str(error)}
        failed_face, _failed_start = _planar_target(root)
        ball_cases = (
            ("unanchored", None),
            ("face_fallback", failed_face),
        )
        case_labels = tuple(label for label, _factory in cases) + tuple(
            label for label, _target in ball_cases
        )
        for label, target_face in ball_cases:
            try:
                case_result = _probe_ball_case(root, label, target_face)
                results[label] = {"status": "passed", **case_result}
                if capture_path:
                    target_point_mm = case_result["targetPointMm"]
                    target_normal = case_result["targetNormal"]
                    if not isinstance(target_point_mm, list) or not isinstance(target_normal, list):
                        raise RuntimeError("The weld-ball probe omitted its target frame.")
                    captures[label] = _capture_case(
                        application,
                        capture_path,
                        label,
                        target_point_mm,
                        target_normal,
                    )
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                results[label] = {"status": "failed", "error": str(error)}
        if capture_path:
            results["captures"] = captures
    finally:
        close_result = bool(probe_document.close(False))
    restored_document = application.activeDocument
    results["cleanup"] = {
        "closed": close_result,
        "documentCountStable": application.documents.count == initial_document_count,
        "restoredPreviousDocument": (
            previous_document is None or restored_document == previous_document
        ),
    }
    results["status"] = (
        "passed"
        if all(
            isinstance(results.get(label), dict) and results[label].get("status") == "passed"  # type: ignore[union-attr]
            for label in case_labels
        )
        and close_result
        and (
            not capture_path
            or all(
                isinstance(captures.get(label), dict) and captures[label].get("saved") is True  # type: ignore[union-attr]
                for label in case_labels
            )
        )
        else "failed"
    )
    return results
