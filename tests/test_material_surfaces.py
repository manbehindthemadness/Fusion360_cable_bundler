"""
Compare direct native surface controls against the independent material evaluator.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, magnitude, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from experiments.experiment_ribbon_fold_route.material_surfaces import (
    MaterialPatch,
    material_patches,
)
from experiments.experiment_ribbon_fold_route.sweep_profile import joined_profile_arcs


def patch_point(patch: MaterialPatch, u: float, v: float) -> Vector3:
    """
    Evaluate one Hermite span as rational Bernstein polynomials for verification.
    """
    if patch.degree_u == 1:
        rows = patch.rows
        basis_u = (1 - u, u)
    else:
        breaks = sorted(set(patch.knots_u))
        segment = min(
            next((i for i, hi in enumerate(breaks[1:]) if u <= hi), len(breaks) - 2),
            len(breaks) - 2,
        )
        t = (u - breaks[segment]) / (breaks[segment + 1] - breaks[segment])
        rows = patch.rows[3 * segment : 3 * segment + 4]
        basis_u = ((1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t**3)
    basis_v = ((1 - v) ** 2, 2 * v * (1 - v), v * v)
    denominator = math.fsum(a * b for a, b in zip(basis_v, patch.profile.weights))
    return Vector3(
        *(
            math.fsum(
                bu * bv * weight * getattr(point, axis)
                for bu, row in zip(basis_u, rows)
                for bv, weight, point in zip(basis_v, patch.profile.weights, row)
            )
            / denominator
            for axis in ("x", "y", "z")
        )
    )


@pytest.mark.parametrize("lines", [1, 3, 6])
@pytest.mark.parametrize("diameter", [0.75, 1.5, 3.0])
def test_ordered_profile_retains_exact_joined_arcs(lines: int, diameter: float) -> None:
    """
    Preserve original circles, clockwise ordering and explicit outer material tips.
    """
    profile = material_profile(lines, diameter)
    originals = joined_profile_arcs(lines, diameter)
    for arc, following in zip(profile, profile[1:] + profile[:1]):
        assert arc.controls[-1] == following.controls[0]
        for t in (0, 0.17, 0.5, 0.89, 1):
            q, b = arc.point(t)
            residual = min(
                abs(math.hypot(q - circle.center[0], b - circle.center[1]) - circle.radius)
                for circle in originals
            )
            assert residual < 1e-12
    vertices = [arc.controls[0] for arc in profile]
    half_width = (lines * diameter + 0.2 * diameter) / 2
    assert (half_width, 0.0) in vertices
    assert (-half_width, 0.0) in vertices
    assert sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(vertices, vertices[1:] + vertices[:1])) < 0


@pytest.mark.parametrize("bank,angle", [(0, 1.7), (0.63, 2.1), (-0.47, -2.3), (0.9, -0.4)])
@pytest.mark.parametrize("lines", [1, 3, 6])
@pytest.mark.parametrize("diameter", [0.75, 1.5, 3.0])
def test_surface_controls_follow_material_map(
    bank: float, angle: float, lines: int, diameter: float
) -> None:
    """
    Match all perimeter points through staggered entry/exit and both fold senses.
    """
    profile = material_profile(lines, diameter)
    half_width = lines * diameter / 2 + 0.1 * diameter
    lead = half_width * abs(math.tan(bank))
    fold = CylindricalFold(diameter / (2 * 0.996), angle, bank, 2 * half_width, lead, lead)
    pose = Pose(Vector3(17, -3, 8), unit(Vector3(1, 2, 0)), unit(Vector3(-2, 1, 0)))
    piece = PlacedPiece(pose, fold, "test")
    patches = material_patches((piece,), profile)
    for patch in patches:
        for fraction in (0, 0.123, 0.51, 0.94, 1):
            for v in (0, 0.19, 0.5, 0.83, 1):
                q, b = patch.profile.point(v)
                low, high = fold.bend_interval(q)
                if patch.region == "bend":
                    u = fraction * abs(angle)
                    material_u = low + fraction * (high - low)
                elif patch.region == "before":
                    u, material_u = fraction, fraction * low
                else:
                    u, material_u = fraction, high + fraction * (1 - high)
                p, velocity, across, _ = piece.surface(min(1, max(0, material_u)), q)
                expected = p.translated(unit(cross(velocity, across)), b)
                error = magnitude(difference(patch_point(patch, u, v), expected))
                assert error <= patch.error_bound_mm + 2e-13


def test_straight_surface_is_exact_and_has_no_bend_patches() -> None:
    """
    Translate the complete contour without a fitted centreline or phantom fold.
    """
    piece = PlacedPiece(
        Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), Straight(3), "flat"
    )
    patches = material_patches((piece,), material_profile(1, 1))
    assert len(patches) == 6
    for patch in patches:
        q, b = patch.profile.point(0.37)
        assert patch.region == "straight"
        assert patch.error_bound_mm == 0
        assert magnitude(difference(patch_point(patch, 0.21, 0.37), Vector3(0.63, q, b))) < 1e-14
