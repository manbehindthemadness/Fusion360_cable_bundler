"""
Independently inspect built sections, numbered lobe landmarks, and interference.

These are finite regression oracles, not continuous surface certificates.
They never change geometry to make a failing case pass.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3, difference, dot, lerp, magnitude, unit
from cable_bundler.routing.parallel import RoutePreview

from .shape import RibbonShape


class AuditFailure(RuntimeError):
    """
    Reject generated geometry that misses an independent output invariant.
    """


def collect_audits(
    checks: Mapping[str, Callable[[], Mapping[str, object]]],
) -> tuple[dict[str, object], list[dict[str, str]]]:
    """
    Run all independent output checks without hiding later findings on a failure.

    Only expected audit findings are accumulated. API/construction failures
    propagate because downstream checks may not have usable geometry.
    """
    results: dict[str, object] = {}
    failures: list[dict[str, str]] = []
    for name, check in checks.items():
        try:
            results[name] = check()
        except AuditFailure as error:
            failures.append({"audit": name, "error": str(error)})
    return results, failures


def audit_sections(
    body: adsk.fusion.BRepBody,
    route: RoutePreview,
    expected_edges: int | None,
    shape: RibbonShape | None = None,
) -> dict[str, int]:
    """
    Check the contour containing each station, retaining remote contour counts.

    A section through a hairpin may also cut its distant return leg. Such a
    contour is not itself an error. The contour at the authored station must
    remain uniquely identifiable and retain the intended discrete topology.
    """
    manager = adsk.fusion.TemporaryBRepManager.get()
    count, remote_count = 0, 0
    tolerance_cm = 1e-5
    for curve_index, curve in enumerate(route.curves, start=1):
        for index in range(1, 40):
            station = f"Cubic {curve_index}/{len(route.curves)} station {index}/40"
            point = curve.point(index / 40)
            tangent = unit(curve.derivative(index / 40))
            origin = adsk.core.Point3D.create(point.x / 10, point.y / 10, point.z / 10)
            plane = adsk.core.Plane.create(
                origin, adsk.core.Vector3D.create(tangent.x, tangent.y, tangent.z)
            )
            section = manager.planeIntersection(body, plane)
            if section is None:
                raise AuditFailure(f"{station} has no section.")
            reference = point
            if shape is not None:
                reference = _planned_lane_reference(shape, point)
                reference = reference.translated(
                    tangent, -dot(difference(reference, point), tangent)
                )
            local_origin = adsk.core.Point3D.create(
                reference.x / 10, reference.y / 10, reference.z / 10
            )
            local = []
            for wire in section.wires:
                if wire.edges.count == 0:
                    continue
                bounds = wire.edges.item(0).boundingBox.copy()
                for edge in wire.edges:
                    bounds.combine(edge.boundingBox)
                if all(
                    low - tolerance_cm <= value <= high + tolerance_cm
                    for low, value, high in (
                        (bounds.minPoint.x, local_origin.x, bounds.maxPoint.x),
                        (bounds.minPoint.y, local_origin.y, bounds.maxPoint.y),
                        (bounds.minPoint.z, local_origin.z, bounds.maxPoint.z),
                    )
                ):
                    local.append(wire)
            if len(local) != 1:
                raise AuditFailure(f"{station} has {len(local)} local contours; expected one.")
            if expected_edges is not None and local[0].edges.count != expected_edges:
                raise AuditFailure(
                    f"{station} has {local[0].edges.count} local edges; expected {expected_edges}."
                )
            remote_count += section.wires.count - 1
            count += 1
    return {"audited_sections": count, "remote_contours": remote_count}


def _planned_lane_reference(shape: RibbonShape, point: Vector3) -> Vector3:
    """
    Interpolate the median solved lane on the nearest authored frame interval.

    Folding may legitimately move the material off the unmodified route axis.
    This reference prevents mistaking that intended displacement for a missing
    contour. It is a finite station locator, not a continuous shape guarantee.
    """
    candidates: list[tuple[float, int, float]] = []
    for index, (a, b) in enumerate(zip(shape.frames, shape.frames[1:])):
        span = difference(b.origin, a.origin)
        squared = dot(span, span)
        if squared <= 1e-14:
            raise AuditFailure("Repeated planned ribbon frames.")
        fraction = max(0.0, min(1.0, dot(difference(point, a.origin), span) / squared))
        distance = magnitude(difference(point, lerp(a.origin, b.origin, fraction)))
        candidates.append((distance, index, fraction))
    _, index, fraction = min(candidates)
    lane = shape.lanes[len(shape.lanes) // 2]
    return lerp(lane[index], lane[index + 1], fraction)


def audit_lobe_landmarks(
    body: adsk.fusion.BRepBody, sections: tuple[adsk.fusion.Sketch, ...], lines: int
) -> dict[str, int]:
    """
    Require every numbered top/bottom lobe midpoint to lie on the trunk skin.

    Sketch creation order defines logical lane labels, not Fusion BRep face
    order. Record face splits separately; a split alone is not self-contact.
    """
    count, splits = 0, 0
    previous: dict[int, str] = {}
    for station, section in enumerate(sections[1:-1], start=1):
        arcs = section.sketchCurves.sketchArcs
        if arcs.count != 2 * lines + 2:
            raise AuditFailure("Input profile does not preserve every numbered lobe.")
        for label in range(2 * lines):
            evaluator = arcs.item(label).worldGeometry.evaluator
            success, start, end = evaluator.getParameterExtents()
            if not success:
                raise AuditFailure("Could not measure a numbered lobe landmark.")
            success, point = evaluator.getPointAtParameter((start + end) / 2)
            if not success:
                raise AuditFailure("Could not evaluate a numbered lobe landmark.")
            hits = [face.entityToken for face in body.faces if face.isPointOnFace(point, 0.001)]
            if len(hits) != 1:
                raise AuditFailure(
                    f"Gate {station}, lobe {label + 1}: {len(hits)} face hits; expected one."
                )
            if label in previous and previous[label] != hits[0]:
                splits += 1
            previous[label] = hits[0]
            count += 1
    return {"lobe_landmark_checks": count, "lobe_face_transitions": splits}


def _intersection_volume_mm3(a: adsk.fusion.BRepBody, b: adsk.fusion.BRepBody) -> float:
    """
    Measure solid intersection on transient copies without editing either body.
    """
    first, second = a.boundingBox, b.boundingBox
    if any(
        hi_a < lo_b or hi_b < lo_a
        for lo_a, hi_a, lo_b, hi_b in (
            (first.minPoint.x, first.maxPoint.x, second.minPoint.x, second.maxPoint.x),
            (first.minPoint.y, first.maxPoint.y, second.minPoint.y, second.maxPoint.y),
            (first.minPoint.z, first.maxPoint.z, second.minPoint.z, second.maxPoint.z),
        )
    ):
        return 0.0
    manager = adsk.fusion.TemporaryBRepManager.get()
    left, right = manager.copy(a), manager.copy(b)
    if (
        left is None
        or right is None
        or not manager.booleanOperation(
            left, right, adsk.fusion.BooleanTypes.IntersectionBooleanType
        )
    ):
        raise AuditFailure("Fusion could not evaluate transient solid interference.")
    volume = left.volume * 1000
    if not math.isfinite(volume) or volume < 0:
        raise AuditFailure("Invalid interference volume.")
    return volume


def audit_interference(
    trunk: adsk.fusion.BRepBody, branches: tuple[adsk.fusion.BRepBody, ...], diameter_mm: float
) -> dict[str, float | int]:
    """
    Reject branch-to-branch overlap and excessive overlap beyond the cap seam.

    The copied exit builder intentionally overlaps the trunk by 0.02 mm.
    A conservative volume allowance accommodates that seam, not remote contact.
    This check does not establish absence of trunk self-intersection.
    """
    maximum_seam, pairs = 0.0, 0
    tolerance = max(1e-7, diameter_mm**3 * 1e-6)
    seam_allowance = 2 * diameter_mm**2 * 0.02 + tolerance
    for index, branch in enumerate(branches):
        overlap = _intersection_volume_mm3(trunk, branch)
        maximum_seam = max(maximum_seam, overlap)
        if overlap > seam_allowance:
            raise AuditFailure(
                f"Branch {index + 1} overlaps the trunk beyond its cap seam ({overlap:g} mm3)."
            )
        for other in branches[:index]:
            pairs += 1
            overlap = _intersection_volume_mm3(branch, other)
            if overlap > tolerance:
                raise AuditFailure(f"Numbered split exits overlap ({overlap:g} mm3).")
    return {"branch_pairs_checked": pairs, "maximum_cap_seam_overlap_mm3": maximum_seam}
