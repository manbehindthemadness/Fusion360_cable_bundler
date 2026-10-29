"""
Build a shared nominal-thickness display envelope without changing frozen routes.
"""

from __future__ import annotations

from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3

from .geometry import PathSnapshot


@dataclass(frozen=True)
class ThicknessMesh:
    """
    Retain one continuous sampled shell in millimetres for both diagnostic views.

    Circular profiles use their recorded outline. Material rulings receive a
    nominal +/-D/2 local-Y extrusion, not a reconstructed bonded outer contour.
    Inter-section triangles are visual interpolation, not collision evidence.
    """

    thickness_mm: float
    description: str
    opacity: float
    vertices: tuple[Vector3, ...]
    triangles: tuple[tuple[int, int, int], ...]
    outlines: tuple[tuple[int, ...], ...]


def build(snapshot: PathSnapshot) -> ThicknessMesh:
    """
    Close a bounded display shell across ordered frozen sections, including end faces.

    No native solids, individual conductor bodies, fitting or geometric repair
    occur. Reject mixed/mismatched profiles rather than guessing correspondence.
    """
    kinds = {section.kind for section in snapshot.sections}
    if len(kinds) != 1 or (snapshot.lines == 1) != (kinds == {"circle"}):
        raise ValueError("Thickness display requires consistent declared section profiles.")
    circular = kinds == {"circle"}
    half = snapshot.diameter_mm / 2
    rings = tuple(
        section.outline[:-1]
        if circular
        else (
            section.outline[0].translated(section.frame.y, half),
            section.outline[1].translated(section.frame.y, half),
            section.outline[1].translated(section.frame.y, -half),
            section.outline[0].translated(section.frame.y, -half),
        )
        for section in snapshot.sections
    )
    width = len(rings[0])
    if any(len(ring) != width for ring in rings):
        raise ValueError("Thickness section outlines need matching vertex correspondence.")
    vertices = tuple(point for ring in rings for point in ring)
    faces: list[tuple[int, int, int]] = []
    for station in range(len(rings) - 1):
        for side in range(width):
            a, b = station * width + side, station * width + (side + 1) % width
            c, d = a + width, b + width
            faces.extend(((a, b, c), (b, d, c)))
    last = (len(rings) - 1) * width
    for side in range(1, width - 1):
        faces.extend(((0, side + 1, side), (last, last + side, last + side + 1)))
    rails = range(0, width, max(1, width // 4))
    outlines = tuple(
        tuple(station * width + side for station in range(len(rings))) for side in rails
    )
    outlines += (tuple(range(width)) + (0,), tuple(last + side for side in range(width)) + (last,))
    return ThicknessMesh(
        snapshot.diameter_mm,
        "Recorded circular sections; sampled tube envelope."
        if circular
        else "Nominal ribbon envelope: +/-D/2 along local Y across each recorded material ruling; bonded contour unresolved.",
        0.22,
        vertices,
        tuple(faces),
        outlines,
    )
