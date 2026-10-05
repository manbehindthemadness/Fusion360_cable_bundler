"""
Distinguish a legitimate shared BRep edge from a multi-face landmark ambiguity.
"""

from __future__ import annotations

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion


def inspect_landmark(
    body: adsk.fusion.BRepBody, section: adsk.fusion.Sketch, lobe_index: int
) -> dict[str, object]:
    """
    Measure whether the auditor's midpoint lies on an edge shared by its hit faces.

    A split skin face need not invalidate the body. This records correspondence
    evidence without changing the existing audit verdict or claiming skin injectivity.
    """
    evaluator = section.sketchCurves.sketchArcs.item(lobe_index).worldGeometry.evaluator
    success, start, end = evaluator.getParameterExtents()
    if not success:
        raise RuntimeError("Could not measure the audited lobe.")
    success, point = evaluator.getPointAtParameter((start + end) / 2)
    if not success:
        raise RuntimeError("Could not evaluate the audited lobe.")
    faces = [face for face in body.faces if face.isPointOnFace(point, 0.001)]
    record: dict[str, object] = {
        "point_mm": (point.x * 10, point.y * 10, point.z * 10),
        "face_hits": len(faces),
        "shared_edge_distances_mm": [],
    }
    if len(faces) < 2:
        return record
    shared_tokens = set.intersection(*({edge.entityToken for edge in face.edges} for face in faces))
    distances: list[float] = []
    errors: list[str] = []
    for edge in faces[0].edges:
        if edge.entityToken not in shared_tokens:
            continue
        try:
            success, parameter = edge.evaluator.getParameterAtPoint(point)
            if success:
                success, candidate = edge.evaluator.getPointAtParameter(parameter)
                if success:
                    distances.append(candidate.distanceTo(point) * 10)
        except (RuntimeError, ValueError) as error:
            errors.append(str(error))
    record.update(
        shared_edge_count=len(shared_tokens),
        shared_edge_distances_mm=distances,
        query_errors=errors,
    )
    return record
