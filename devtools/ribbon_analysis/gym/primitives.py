"""
Supply planar faces for virtual boxes and regular dodecahedra without Fusion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations, product

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit

AXES = (Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1))
PHI = (1 + math.sqrt(5)) / 2


def _mean(points: tuple[Vector3, ...]) -> Vector3:
    """
    Return the centroid of a nonempty geometric vertex tuple.
    """
    return Vector3(
        *(sum(getattr(p, axis) for p in points) / len(points) for axis in ("x", "y", "z"))
    )


@dataclass(frozen=True)
class Box:
    """
    Describe an axis-aligned zone or void using its center and three side lengths.
    """

    center: Vector3
    size: tuple[float, float, float]

    def face(self, index: int) -> tuple[Vector3, Vector3, Vector3, tuple[Vector3, ...]]:
        """
        Return face center, outward normal, ordered across axis and four corners.
        """
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < 6:
            raise ValueError("Box face index must be0..5.")
        axis, sign = index // 2, 1 if index % 2 == 0 else -1
        normal = Vector3(0, 0, 0).translated(AXES[axis], sign)
        across = AXES[(axis + 1) % 3]
        up = cross(normal, across)
        origin = self.center.translated(normal, self.size[axis] / 2)
        corners = tuple(
            origin.translated(across, a * self.size[(axis + 1) % 3] / 2).translated(
                up, b * self.size[(axis + 2) % 3] / 2
            )
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))
        )
        return origin, normal, across, corners


@lru_cache(maxsize=1)
def topology() -> tuple[tuple[Vector3, ...], tuple[tuple[int, ...], ...]]:
    """
    Derive twelve consistently wound pentagons from the twenty regular vertices.

    Supporting-plane enumeration runs once and does not depend on a gym layout,
    selected face, route or solver. Stable vertex-index ordering fixes face IDs.
    """
    vertices = [Vector3(*point) for point in product((-1, 1), repeat=3)]
    for a, b in product((-1, 1), repeat=2):
        vertices.extend(
            (
                Vector3(0, a / PHI, b * PHI),
                Vector3(a / PHI, b * PHI, 0),
                Vector3(b * PHI, 0, a / PHI),
            )
        )
    points = tuple(vertices)
    faces: set[tuple[int, ...]] = set()
    for i, j, k in combinations(range(20), 3):
        raw = cross(difference(points[j], points[i]), difference(points[k], points[i]))
        if magnitude(raw) < 1e-9:
            continue
        normal = unit(raw)
        distances = tuple(dot(difference(point, points[i]), normal) for point in points)
        if min(distances) < -1e-9 and max(distances) > 1e-9:
            continue
        face = tuple(index for index, value in enumerate(distances) if abs(value) < 1e-9)
        if len(face) == 5:
            faces.add(face)
    polygons = []
    for face in sorted(faces):
        center = _mean(tuple(points[index] for index in face))
        normal = unit(center)
        across = unit(difference(points[face[0]], center))
        up = cross(normal, across)
        polygons.append(
            tuple(
                sorted(
                    face,
                    key=lambda index: math.atan2(
                        dot(difference(points[index], center), up),
                        dot(difference(points[index], center), across),
                    ),
                )
            )
        )
    if len(polygons) != 12:
        raise RuntimeError("Regular dodecahedron topology needs twelve pentagons.")
    return points, tuple(polygons)


@dataclass(frozen=True)
class Dodecahedron:
    """
    Represent a uniformly scaled regular dodecahedron with twelve target faces.
    """

    center: Vector3
    scale: float

    @property
    def vertices(self) -> tuple[Vector3, ...]:
        """
        Return all twenty vertices in scene millimeters.
        """
        return tuple(self.center.translated(point, self.scale) for point in topology()[0])

    def face(self, index: int) -> tuple[Vector3, Vector3, Vector3, tuple[Vector3, ...]]:
        """
        Return pentagon center, outward normal, in-face width and ordered corners.
        """
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < 12:
            raise ValueError("Dodecahedron face index must be0..11.")
        corners = tuple(self.vertices[number] for number in topology()[1][index])
        center = _mean(corners)
        return (
            center,
            unit(difference(center, self.center)),
            unit(difference(corners[0], center)),
            corners,
        )
