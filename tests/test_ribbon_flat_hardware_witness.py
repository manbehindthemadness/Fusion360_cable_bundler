"""
Verify affine witness discovery against actual ordered material and strict finite-box interiors.
"""

from __future__ import annotations

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact_inverse import (
    occupied_coordinates,
    profile_height,
)
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_terminal_hardware.flat_witness import find
from experiments.experiment_ribbon_terminal_hardware.model import Box, Dimensions, Terminal


@pytest.mark.parametrize("scale", [0.2, 1.0, 20.0])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("phase", ["straight", "before", "after"])
@pytest.mark.parametrize("rotated", [False, True])
def test_flat_witness_is_actual_material_inside_all_box_faces(
    scale: float, sign: int, phase: str, rotated: bool
) -> None:
    """
    Find narrow outer-width intersections across phase, handedness, scale and rigid frame changes.
    """
    forward = Vector3(0, 1, 0) if rotated else Vector3(1, 0, 0)
    across = Vector3(0, 0, 1) if rotated else Vector3(0, 1, 0)
    pose = Pose(Vector3(7 * scale, -3 * scale, 5 * scale), forward, across)
    geometry = (
        Straight(8 * scale)
        if phase == "straight"
        else CylindricalFold(2 * scale, sign * 1.2, sign * 0.3, 4.2 * scale, 3 * scale, 3 * scale)
    )
    piece = PlacedPiece(pose, geometry, "Authored affine material")
    q = sign * 1.8 * scale
    if isinstance(geometry, CylindricalFold):
        low, high = geometry.bend_interval(q)
        u = low / 2 if phase == "before" else (1 + high) / 2
    else:
        u = 0.4
    center = piece.surface(u, q)[0]
    box = Box(
        Terminal.START,
        Pose(center.translated(forward, 0.1 * scale), forward, across),
        Dimensions(0.2 * scale, 0.2 * scale, 0.2 * scale),
    )
    found = find(piece, box, 4, scale)
    assert found is not None
    u, q, height = found.material
    assert 0 <= u <= 1
    assert height == 0 and profile_height(q, 4, scale) > 1e-9 * max(1, scale)
    if isinstance(geometry, CylindricalFold):
        low, high = geometry.bend_interval(q)
        assert u <= low if phase == "before" else u >= high
    assert magnitude(difference(found.point, piece.surface(u, q)[0])) == 0
    inverse = occupied_coordinates(piece, found.point, 4, scale)
    assert inverse is not None
    assert abs(inverse[0] - u) < 1e-10 and abs(inverse[1] - q) < 1e-10 * max(1, scale)
    relative = difference(found.point, box.pose.origin)
    assert all(
        bound.low < dot(relative, axis) < bound.high for axis, bound in zip(box.axes, box.bounds)
    )


@pytest.mark.parametrize("height", [0.2, 0.21, 10.0])
def test_mid_surface_miss_or_tangency_never_claims_intrusion(height: float) -> None:
    """
    Leave thickness-only contact and absent intersections to the ordinary checker.
    """
    pose = Pose(Vector3(-1, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    piece = PlacedPiece(pose, Straight(0.5), "Mid-surface control")
    box = Box(
        Terminal.END,
        Pose(Vector3(0, 0, height), pose.tangent, pose.width),
        Dimensions(3, 0.4, 3),
    )
    assert find(piece, box, 4, 1.0) is None


@pytest.mark.parametrize("side", [-1, 1])
def test_outer_profile_tangency_cannot_become_an_occupied_point(side: int) -> None:
    """
    Outward polygon rounding must not turn the zero-height width extremity into penetration.
    """
    pose = Pose(Vector3(-1, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    piece = PlacedPiece(pose, Straight(0.5), "Profile boundary control")
    box = Box(
        Terminal.START,
        Pose(Vector3(0, side * 2.2, 0), pose.tangent, pose.width),
        Dimensions(0.2, 2, 3),
    )
    assert find(piece, box, 4, 1.0) is None
