"""
Measure unique open native edge chains separating one fixed pair of skin faces.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RailEdge:
    """
    Preserve body-local topology identifiers and native arc length in millimeters.
    """

    identity: int
    start: int
    end: int
    faces: tuple[int, ...]
    length_mm: float


def measure_chain(edges: tuple[RailEdge, ...], start: int, end: int) -> dict[str, object]:
    """
    Require a single face-pair chain without branches, cycles, or disconnected pieces.

    Never select a shortest path or use geometric proximity to join native vertices.
    """
    if start == end:
        return {"status": "unmeasured", "reason": "Rail endpoints are identical."}
    candidates = {
        edge.faces for edge in edges if start in (edge.start, edge.end) and len(edge.faces) == 2
    }
    candidates &= {
        edge.faces for edge in edges if end in (edge.start, edge.end) and len(edge.faces) == 2
    }
    if len(candidates) != 1:
        return {"status": "unmeasured", "reason": "Rail face-pair identity is not unique."}
    members = tuple(edge for edge in edges if edge.faces == next(iter(candidates)))
    adjacency: dict[int, list[RailEdge]] = {}
    for edge in members:
        if not math.isfinite(edge.length_mm) or edge.length_mm <= 0 or edge.start == edge.end:
            return {"status": "unmeasured", "reason": "Invalid or closed rail segment."}
        for vertex in (edge.start, edge.end):
            adjacency.setdefault(vertex, []).append(edge)
    if any(
        len(incident) != (1 if vertex in (start, end) else 2)
        for vertex, incident in adjacency.items()
    ):
        return {"status": "unmeasured", "reason": "Rail chain branches or has a gap."}
    current = start
    used: list[int] = []
    length = 0.0
    while current != end:
        remaining = [edge for edge in adjacency.get(current, ()) if edge.identity not in used]
        if len(remaining) != 1:
            return {"status": "unmeasured", "reason": "Rail traversal is ambiguous or cyclic."}
        edge = remaining[0]
        used.append(edge.identity)
        length += edge.length_mm
        current = edge.end if edge.start == current else edge.start
    if len(used) != len(members):
        return {"status": "unmeasured", "reason": "Rail face-pair contains disconnected edges."}
    return {
        "status": "measured",
        "length_mm": length,
        "edge_ids": used,
        "face_ids": next(iter(candidates)),
    }
