"""
Verify exact circular-extrusion supports preserve the supplied material profile and flat regions.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.material_cylinder import circle, cylinder
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc, material_profile
from experiments.experiment_ribbon_fold_route.material_surfaces import material_patches
from experiments.experiment_ribbon_fold_route.primitives import fold


@pytest.mark.parametrize("lines,diameter", [(1, 0.01), (3, 0.75), (16, 10.0)])
def test_profile_circles_reconstruct_all_original_arcs(lines: int, diameter: float) -> None:
    """
    Recover the unchanged circle independently at points outside the reconstruction samples.
    """
    for arc in material_profile(lines, diameter):
        q, height, radius = circle(arc)
        for parameter in (0.03, 0.19, 0.41, 0.71, 0.97):
            point = arc.point(parameter)
            assert math.hypot(point[0] - q, point[1] - height) == pytest.approx(radius, rel=1e-11)


@pytest.mark.parametrize("region", ["straight", "before", "after"])
@pytest.mark.parametrize("bank", [-0.4, 0.0, 0.3])
def test_flat_support_contains_actual_material_surfaces(region: str, bank: float) -> None:
    """
    Match translated/rotated, stagger-trimmed circular extrusion without moving material points.
    """
    profile = material_profile(3, 0.75)
    pose = Pose(Vector3(3, -4, 2), Vector3(0, 1, 0), Vector3(0, 0, 1))
    geometry = Straight(3) if region == "straight" else fold(2, 2.4, 1.1, bank, 0.4)
    piece = PlacedPiece(pose, geometry, "analytical cylinder fixture")
    for patch in material_patches((piece,), profile):
        if patch.region != region:
            continue
        support = cylinder(piece, patch)
        for fraction in (0.013, 0.33, 0.987):
            for v in (0.03, 0.5, 0.97):
                q, height = patch.profile.point(v)
                if isinstance(geometry, Straight):
                    u = fraction
                else:
                    low, high = geometry.bend_interval(q)
                    u = fraction * low if region == "before" else high + fraction * (1 - high)
                point, velocity, across, _ = piece.surface(u, q)
                actual = point.translated(unit(cross(velocity, across)), height)
                delta = difference(actual, support.origin)
                radial = delta.translated(support.axis, -dot(delta, support.axis))
                assert magnitude(radial) == pytest.approx(support.radius_mm, abs=1e-11)


@pytest.mark.parametrize(
    "arc",
    [
        MaterialArc(((0, 0), (1, 0), (2, 0)), (1, 1, 1), "collinear"),
        MaterialArc(((0, 0), (0, 0), (0, 0)), (1, 1, 1), "collapsed"),
        MaterialArc(((0, 0), (1, 2), (2, 0)), (1, 1, 1), "parabola"),
    ],
)
def test_non_circular_or_degenerate_profiles_reject(arc: MaterialArc) -> None:
    """
    Do not replace an unsupported future custom contour by a fitted circle.
    """
    with pytest.raises(ValueError):
        circle(arc)


def test_curved_bend_region_cannot_be_replaced_by_a_cylinder() -> None:
    """
    Preserve the prescribed NURBS material map in every actual bend region.
    """
    piece = PlacedPiece(
        Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)),
        fold(2, 2.4, 1.1, 0.3, 0.4),
        "analytical bent fixture",
    )
    patch = next(
        p for p in material_patches((piece,), material_profile(3, 0.75)) if p.region == "bend"
    )
    with pytest.raises(ValueError, match="Only flat"):
        cylinder(piece, patch)
