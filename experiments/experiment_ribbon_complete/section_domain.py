"""
Certify a single star-shaped transverse disk without inventing interior material transport.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

from .profile_transition import TransitionEdge
from .transition_certificate import certify

Pair = tuple[Fraction, Fraction]


def cross(a: Pair, b: Pair) -> Fraction:
    """
    Retain exact orientation signs without angle evaluation or dimensional snapping.
    """
    return a[0] * b[1] - a[1] * b[0]


def separator(points: tuple[Pair, ...], checkpoint: Callable[[], None]) -> Pair | None:
    """
    Find a strict origin-separating halfplane from convex-hull vertex/edge features.

    The closest point of a finite planar convex hull lies at a vertex or edge.
    Testing those finite candidates is exact and bounded, not iterative fitting.
    A positive dot product on every homogeneous control encloses the whole arc
    and its endpoint chord in one open halfplane, proving an origin-free homotopy.
    """
    candidates = list(points)
    for a, b in combinations(points, 2):
        checkpoint()
        d = (b[0] - a[0], b[1] - a[1])
        squared = d[0] ** 2 + d[1] ** 2
        if squared == Fraction(0):
            continue
        parameter = max(Fraction(0), min(Fraction(1), -(a[0] * d[0] + a[1] * d[1]) / squared))
        candidates.append((a[0] + parameter * d[0], a[1] + parameter * d[1]))
    for normal in candidates:
        checkpoint()
        if all(normal[0] * p[0] + normal[1] * p[1] > Fraction(0) for p in points):
            return normal
    return None


@dataclass(frozen=True)
class SectionDomain:
    """
    Record winding and local angular proofs separately from any three-dimensional map.
    """

    sections: tuple[TransitionEdge, ...]
    status: str
    winding_number: int | None
    separators: tuple[Pair, ...]


def certify_domain(
    sections: tuple[TransitionEdge, ...], checkpoint: Callable[[], None]
) -> SectionDomain:
    """
    Prove every original morph slice is one strictly star-shaped boundary around its center.

    Root arcs deform to their endpoint polygon inside strict separating halfplanes,
    so exact polygon winding is authoritative. Positive denominators and strict
    clockwise angular derivatives prevent crossing the origin over the full morph;
    winding is therefore invariant. Winding-1 plus strictly decreasing angle gives
    exactly one boundary point on every ray, and a uniquely defined filled disk.
    Duplicate traversals cannot inherit this conclusion. No polar-center chart,
    persistent interior labels, strain or world-space self-contact proof is implied.
    """
    checkpoint()
    if not sections:
        raise ValueError("A complete closed transverse boundary is required")
    for first, second in zip(sections, sections[1:] + sections[:1]):
        if any(a[-1] != b[0] for a, b in zip(first.rows, second.rows)):
            raise ValueError("Transverse domain contains an open homogeneous seam")
    normals = []
    for section in sections:
        checkpoint()
        if certify(section, checkpoint).status != "certified":
            return SectionDomain(sections, "unresolved", None, tuple(normals))
        normal = separator(tuple((p[0], p[1]) for p in section.rows[0]), checkpoint)
        if normal is None:
            return SectionDomain(sections, "unresolved", None, tuple(normals))
        normals.append(normal)
    vertices = tuple(
        (s.rows[0][0][0] / s.rows[0][0][2], s.rows[0][0][1] / s.rows[0][0][2]) for s in sections
    )
    winding = 0
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        checkpoint()
        if a[1] <= Fraction(0) < b[1] and cross(a, b) > Fraction(0):
            winding += 1
        elif b[1] <= Fraction(0) < a[1] and cross(a, b) < Fraction(0):
            winding -= 1
    return SectionDomain(
        sections, "certified" if winding == -1 else "unresolved", winding, tuple(normals)
    )
