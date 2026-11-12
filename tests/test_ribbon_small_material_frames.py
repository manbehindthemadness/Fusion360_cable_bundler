"""
Verify endpoint orientation does not depend on a positive material segment's length scale.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3, magnitude
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold


class _StationaryPiece(PlacedPiece):
    """
    Supply an actually degenerate derivative through the supported subclass surface boundary.
    """

    def surface(self, u: float, q: float) -> tuple[Vector3, Vector3, Vector3, Vector3]:
        """
        Preserve position and width while returning no longitudinal direction.
        """
        return self.pose.origin, Vector3(0, 0, 0), self.pose.width, Vector3(0, 0, 0)


@pytest.mark.parametrize("size", (1e-16, 1e-14, 1e-12, 1e-10))
@pytest.mark.parametrize("curved", (False, True))
def test_positive_short_material_retains_finite_orthonormal_end_frame(
    size: float, curved: bool
) -> None:
    """
    Preserve a nonzero short turn or straight without imposing a minimum physical length.
    """
    pose = Pose(Vector3(1, 2, 3), Vector3(0, 1, 0), Vector3(1, 0, 0))
    geometry = fold(2, 1.2, size, 0.0, 0.0) if curved else Straight(size)
    piece = PlacedPiece(pose, geometry, "analytical short material")
    end = piece.end_pose()
    assert all(
        math.isfinite(value)
        for vector in (end.origin, end.tangent, end.width)
        for value in (vector.x, vector.y, vector.z)
    )
    assert magnitude(end.tangent) == pytest.approx(1.0)
    assert magnitude(end.width) == pytest.approx(1.0)
    assert end.tangent.y == pytest.approx(1.0)
    assert end.width.x == pytest.approx(1.0)
    assert piece.geometry.material_length_mm > 0.0


def test_zero_material_velocity_remains_an_error() -> None:
    """
    Rescaling cannot manufacture an orientation for an actually collapsed segment.
    """
    pose = Pose(Vector3(0, 0, 0), Vector3(0, 1, 0), Vector3(1, 0, 0))
    with pytest.raises(ValueError, match="nonzero"):
        _StationaryPiece(pose, Straight(1e-16), "collapsed").end_pose()
