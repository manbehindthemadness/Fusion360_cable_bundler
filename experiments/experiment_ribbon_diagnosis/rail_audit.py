"""
Match native longitudinal seam chains through observed cap landmarks in 3D.
"""

from __future__ import annotations

import math

# noinspection PyUnresolvedReferences
import adsk.fusion

from .observations import SectionRecord
from .rail_topology import RailEdge, measure_chain


def audit_rails(
    body: adsk.fusion.BRepBody, records: list[SectionRecord], lines: int
) -> dict[str, object]:
    """
    Compare uniquely identified side seam chains independent of plane and segmentation.

    Cap landmarks locate native vertices; connectivity and a fixed adjacent-face
    pair identify each seam. Ambiguous topology cannot pass. This measures
    boundaries, not full material strain or developability.
    """
    if len(records) < 2 or any(
        len(record.points_mm) != 3 * (2 * lines + 2) for record in (records[0], records[-1])
    ):
        return {"status": "unmeasured", "reason": "Missing complete cap observations."}
    vertices: dict[int, tuple[float, float, float]] = {}
    edges = []
    for index, edge in enumerate(body.edges):
        if edge.startVertex is None or edge.endVertex is None:
            continue
        for vertex in (edge.startVertex, edge.endVertex):
            point = vertex.geometry
            vertices[vertex.tempId] = (point.x * 10, point.y * 10, point.z * 10)
        edges.append(
            RailEdge(
                index,
                edge.startVertex.tempId,
                edge.endVertex.tempId,
                tuple(sorted(face.tempId for face in edge.faces)),
                edge.length * 10,
            )
        )
    rails: list[dict[str, object]] = []
    for landmark in (-4, -6, -3, -1):
        endpoints = []
        for record in (records[0], records[-1]):
            matches = [
                identity
                for identity, point in vertices.items()
                if math.dist(point, record.points_mm[landmark]) <= 0.001
            ]
            if len(matches) != 1:
                return {
                    "status": "unmeasured",
                    "reason": "Cap landmark has no unique native vertex.",
                    "candidate_count": len(matches),
                }
            endpoints.append(matches[0])
        result = measure_chain(tuple(edges), endpoints[0], endpoints[1])
        rails.append(result)
        if result["status"] != "measured":
            return {"status": "unmeasured", "rail_chains": rails}
    edge_ids = [identity for rail in rails for identity in rail["edge_ids"]]
    if len(edge_ids) != len(set(edge_ids)):
        return {"status": "unmeasured", "reason": "Native seams share edges."}
    lengths = [rail["length_mm"] for rail in rails]
    spreads = [abs(lengths[i] - lengths[i + 2]) / max(lengths[i], lengths[i + 2]) for i in (0, 1)]
    return {
        "status": "passed" if max(spreads) <= 0.01 else "failed",
        "limit": 0.01,
        "maximum_relative_spread": max(spreads),
        "rail_chains": rails,
        "rail_lengths_mm": dict(
            zip(("left_top", "left_bottom", "right_top", "right_bottom"), lengths)
        ),
        "scope": "Native face-pair seam chains between corresponding cap landmarks; no full cloth-metric certificate.",
    }
