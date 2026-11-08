"""
Compose isometric material pieces without rescaling individual ribbon paths.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field
from functools import cached_property

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold

ZERO = Vector3(0, 0, 0)


@dataclass(frozen=True)
class Pose:
    """
    Place local material X/Y along forward/across and Z along their normal.
    """

    origin: Vector3
    tangent: Vector3
    width: Vector3

    def direction(self, local: Vector3) -> Vector3:
        """
        Rotate without translation or temporary vectors, retaining the zero-first addition order.
        """
        forward, across, normal = self.tangent, self.width, self._normal
        return Vector3(
            0 + forward.x * local.x + across.x * local.y + normal.x * local.z,
            0 + forward.y * local.x + across.y * local.y + normal.y * local.z,
            0 + forward.z * local.x + across.z * local.y + normal.z * local.z,
        )

    @cached_property
    def _normal(self) -> Vector3:
        """
        Reuse the exact cross product for this immutable frame without retaining other frames.
        """
        return cross(self.tangent, self.width)

    def point(self, local: Vector3) -> Vector3:
        """
        Transform a point into the owned route's millimeter frame.
        """
        return self.origin.translated(self.direction(local), 1)


@dataclass(frozen=True)
class Straight:
    """
    Carry a flat material strip forward by a positive common length.
    """

    material_length_mm: float

    def __post_init__(self) -> None:
        """
        Refuse a stationary or reversed material parameter.
        """
        if not math.isfinite(self.material_length_mm) or self.material_length_mm <= 0:
            raise ValueError("A straight material piece needs positive finite length.")

    def surface(self, u: float, q: float) -> tuple[Vector3, Vector3, Vector3, Vector3]:
        """
        Return point, parameter velocity, width derivative and acceleration.
        """
        return (
            Vector3(u * self.material_length_mm, q, 0),
            Vector3(self.material_length_mm, 0, 0),
            Vector3(0, 1, 0),
            ZERO,
        )


@dataclass(frozen=True)
class PlacedPiece:
    """
    Retain one original local piece and its rigid placement, with no guide fitting.
    """

    pose: Pose
    geometry: Straight | CylindricalFold
    label: str

    def surface(self, u: float, q: float) -> tuple[Vector3, Vector3, Vector3, Vector3]:
        """
        Evaluate the same material map in world coordinates.
        """
        point, velocity, across, acceleration = self.geometry.surface(u, q)
        return (
            self.pose.point(point),
            self.pose.direction(velocity),
            self.pose.direction(across),
            self.pose.direction(acceleration),
        )

    def end_pose(self) -> Pose:
        """
        Reuse the immutable terminal frame within this placed piece's lifetime.

        Placement and material geometry are frozen. Regenerated or replaced pieces
        own separate frames; no global cache retains routes or derivative probes.
        """
        return self._end_pose

    @cached_property
    def _end_pose(self) -> Pose:
        """
        Carry a flat terminal frame forward, removing accumulated floating roundoff.
        """
        point, velocity, across, _ = self.surface(1, 0)
        tangent = unit(velocity)
        width = unit(across.translated(tangent, -dot(across, tangent)))
        return Pose(point, tangent, width)


@dataclass(frozen=True)
class FoldRoute:
    """
    Retain all pieces under one common arc-length material coordinate.

    Each local piece is an isometry and each join has a flat, matching material
    cap. This gives equal longitudinal material increments throughout the strip.
    Native interpolation, global contact and minimum total length are separate.
    """

    targets: Targets
    pieces: tuple[PlacedPiece, ...]
    radius_mm: float
    material_length_mm: float = field(init=False)
    boundaries: tuple[float, ...] = field(init=False)
    starts_mm: tuple[float, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """
        Freeze positive piece lengths and their shared material intervals once.
        """
        if not self.pieces:
            raise ValueError("A material route needs at least one piece.")
        lengths = [piece.geometry.material_length_mm for piece in self.pieces]
        total = math.fsum(lengths)
        boundaries = (
            (0.0,) + tuple(math.fsum(lengths[:i]) / total for i in range(1, len(lengths))) + (1.0,)
        )
        object.__setattr__(self, "material_length_mm", total)
        object.__setattr__(self, "boundaries", boundaries)
        object.__setattr__(
            self, "starts_mm", tuple(math.fsum(lengths[:i]) for i in range(len(lengths)))
        )

    @property
    def half_width_mm(self) -> float:
        """
        Preserve the joined profile's nominal width and outer side-cap extension.
        """
        return self.targets.lines * self.targets.diameter_mm / 2 + self.targets.diameter_mm * 0.1

    def surface(self, u: float, q: float) -> tuple[Vector3, Vector3, Vector3, Vector3]:
        """
        Evaluate a material lane and derivatives, with +u always advancing material.
        """
        if (
            isinstance(u, bool)
            or isinstance(q, bool)
            or not math.isfinite(u)
            or not math.isfinite(q)
            or not 0 <= u <= 1
            or abs(q) > self.half_width_mm
        ):
            raise ValueError("Coordinates must lie within the routed material strip.")
        boundaries = self.boundaries
        index = min(bisect_right(boundaries, u) - 1, len(self.pieces) - 1)
        piece = self.pieces[index]
        length = piece.geometry.material_length_mm
        local = min(1.0, max(0.0, (u * self.material_length_mm - self.starts_mm[index]) / length))
        point, velocity, across, acceleration = piece.surface(local, q)
        scale = self.material_length_mm / length
        return (
            point,
            ZERO.translated(velocity, scale),
            across,
            ZERO.translated(acceleration, scale**2),
        )

    def lane(self, u: float, offset_mm: float) -> tuple[Vector3, Vector3]:
        """
        Return an actual material path, including curved transverse fold sections.
        """
        point, velocity, _, _ = self.surface(u, offset_mm)
        return point, velocity

    def physical(self, u: float, q: float, height_mm: float) -> Vector3:
        """
        Place the unchanged material profile along the local surface normal.
        """
        point, velocity, across, _ = self.surface(u, q)
        return point.translated(unit(cross(velocity, across)), height_mm)


def extend(pose: Pose, geometries: tuple[Straight | CylindricalFold, ...]) -> Pose:
    """
    Evaluate a piece sequence's final pose without generating an alternate route.
    """
    for geometry in geometries:
        pose = PlacedPiece(pose, geometry, "pose composition").end_pose()
    return pose


def relative(pose: Pose, vector: Vector3) -> Vector3:
    """
    Express a world vector in the frame of a fixed endpoint.
    """
    return Vector3(
        dot(vector, pose.tangent),
        dot(vector, pose.width),
        dot(vector, cross(pose.tangent, pose.width)),
    )


def pose_error(actual: Pose, expected: Pose) -> tuple[float, float]:
    """
    Return position and ordered-frame vector residuals, without changing either pose.
    """
    return magnitude(difference(actual.origin, expected.origin)), max(
        magnitude(difference(actual.tangent, expected.tangent)),
        magnitude(difference(actual.width, expected.width)),
    )
