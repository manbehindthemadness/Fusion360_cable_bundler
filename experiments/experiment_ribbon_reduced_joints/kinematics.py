"""
Eliminate terminal rotation constraints through a continuously movable internal joint frame.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, cross, dot
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import Pose
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology, rotation_choices

RotationChoices = tuple[tuple[CylindricalFold, ...], ...]


def rotate(vector: Vector3, axis: Vector3, angle: float) -> Vector3:
    """
    Rotate a vector about an explicitly unit-length world axis.
    """
    cosine, sine = math.cos(angle), math.sin(angle)
    return (
        Vector3(0, 0, 0)
        .translated(vector, cosine)
        .translated(cross(axis, vector), sine)
        .translated(axis, dot(axis, vector) * (1 - cosine))
    )


def moved(frame: Pose, direction: tuple[float, float, float], angle: float) -> Pose:
    """
    Apply a unit reduced-coordinate rotation in the current tangent/width/normal basis.
    """
    if (
        not math.isfinite(angle)
        or any(not math.isfinite(v) for v in direction)
        or abs(math.fsum(v * v for v in direction) - 1.0) > 1e-8
    ):
        raise ValueError("Joint motion requires a finite angle and unit direction")
    axis = (
        Vector3(0, 0, 0)
        .translated(frame.tangent, direction[0])
        .translated(frame.width, direction[1])
        .translated(cross(frame.tangent, frame.width), direction[2])
    )
    return Pose(frame.origin, rotate(frame.tangent, axis, angle), rotate(frame.width, axis, angle))


@dataclass(frozen=True)
class Joint:
    """
    Retain one algebraic branch and fold-group sizes while the internal frame moves.
    """

    boundary: Boundary
    roots: tuple[int, int]
    branch_counts: tuple[int, int]
    fold_counts: tuple[int, int]
    identifier: str

    @classmethod
    def capture(cls, boundary: Boundary, frame: Pose, identifier: str) -> Joint:
        """
        Bind an existing guided branch without introducing alternate orientation guesses.
        """
        parts = identifier.split("-")
        if len(parts) != 3 or parts[0] != "guide":
            raise ValueError("Reduced joints require an existing guided coarse construction")
        roots = (int(parts[1]), int(parts[2]))
        first, last = cls._choices(boundary, frame)
        if not 0 <= roots[0] < len(first) or not 0 <= roots[1] < len(last):
            raise ValueError("Selected guided rotation roots are unavailable")
        return cls(
            boundary,
            roots,
            (len(first), len(last)),
            (len(first[roots[0]]), len(last[roots[1]])),
            identifier,
        )

    @staticmethod
    def _choices(boundary: Boundary, frame: Pose) -> tuple[RotationChoices, RotationChoices]:
        """
        Derive both exact endpoint-to-joint rotation groups at the declared physical radius.
        """
        target = boundary.targets
        start = Pose(target.start, target.start_tangent, target.start_width)
        end = Pose(target.end, target.end_tangent, target.end_width)
        radius, width = boundary.radius_mm, boundary.half_width_mm * 2
        return rotation_choices(start, frame, radius, width), rotation_choices(
            frame, end, radius, width
        )

    def model(self, frame: Pose) -> Model | None:
        """
        Return affine placement on the retained regular branch; branch changes remain unresolved.
        """
        try:
            first, last = self._choices(self.boundary, frame)
        except ValueError:
            return None
        if (len(first), len(last)) != self.branch_counts:
            return None
        a, b = first[self.roots[0]], last[self.roots[1]]
        if (len(a), len(b)) != self.fold_counts:
            return None
        return Model(self.boundary, Topology(self.identifier, a + b, len(a)))
