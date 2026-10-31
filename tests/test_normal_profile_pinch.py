"""
Verify normal-profile pinch against independent geometric swept-coordinate determinants.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude
from devtools.ribbon_analysis.normal_profile import inspect_normal_profile
from devtools.ribbon_analysis.pinch import PinchLimit


def _helix(
    theta: float, radius: float, pitch: float
) -> tuple[Vector3, Vector3, Vector3, Vector3, Vector3]:
    """
    Author geometric circle/helix positions and its actual perpendicular profile frame.
    """
    scale = math.hypot(radius, pitch)
    c, s = math.cos(theta), math.sin(theta)
    return (
        Vector3(radius * c, radius * s, pitch * theta),
        Vector3(-radius * s, radius * c, pitch),
        Vector3(-radius * c, -radius * s, 0),
        Vector3(pitch * s / scale, -pitch * c / scale, radius / scale),
        Vector3(-c, -s, 0),
    )


def _surface(theta: float, q: float, v: float, radius: float, pitch: float) -> Vector3:
    """
    Place a fixed profile point directly in world coordinates without using the pinch rule.
    """
    p, _, _, width, height = _helix(theta, radius, pitch)
    return p.translated(width, q).translated(height, v)


@pytest.mark.parametrize(
    "radius,pitch,thickness",
    ((25.0, 0.0, 49.8), (1.0, 0.0, 1.5), (0.74, 0.0, 1.5), (1.0, 3.0, 1.5), (0.75, 2.7, 1.5)),
)
def test_local_pinch_matches_independent_world_geometry(
    radius: float,
    pitch: float,
    thickness: float,
) -> None:
    """
    Finite differences of swept points establish the actual local volume contraction.
    """
    theta, step = 0.71, 1e-5
    _, velocity, acceleration, width, height = _helix(theta, radius, pitch)
    measured = inspect_normal_profile(velocity, acceleration, width, thickness, PinchLimit())
    baseline = dot(velocity, cross(width, height))
    determinants = []
    for q in (-1.5, 0.0, 1.5):
        for v in (-thickness / 2, 0.0, thickness / 2):
            change = difference(
                _surface(theta + step, q, v, radius, pitch),
                _surface(theta - step, q, v, radius, pitch),
            )
            derivative = Vector3(
                change.x / (2 * step), change.y / (2 * step), change.z / (2 * step)
            )
            determinants.append(dot(derivative, cross(width, height)) / baseline)
    assert measured.minimum_jacobian == pytest.approx(min(determinants), abs=1e-8)
    assert measured.utilization == pytest.approx(1 - min(determinants), abs=1e-8)


def test_user_demo_reproduces_measured_inner_and_outer_radii() -> None:
    """
    Recover R25/h24.9 directly from radial distances of actual offset points.
    """
    _, velocity, acceleration, width, _ = _helix(0.0, 25.0, 0.0)
    measured = inspect_normal_profile(velocity, acceleration, width, 49.8, PinchLimit())
    inner = magnitude(_surface(0.0, 0.0, 24.9, 25.0, 0.0))
    outer = magnitude(_surface(0.0, 0.0, -24.9, 25.0, 0.0))
    assert inner == pytest.approx(0.1) and outer == pytest.approx(49.9)
    assert measured.inside_radius_mm == pytest.approx(inner)
    assert measured.minimum_radius_mm == pytest.approx(25.0)
    assert measured.within_limit


def test_circular_macaroni_limit_rejects_a_collapsed_or_negative_inside() -> None:
    """
    A100percent or reversed inner tube mapping cannot pass local regularity.
    """
    for radius in (0.75, 0.74):
        _, velocity, acceleration, width, _ = _helix(0.0, radius, 0.0)
        observed = inspect_normal_profile(velocity, acceleration, width, 1.5, PinchLimit())
        assert not observed.within_limit
        assert observed.minimum_jacobian <= 0


def test_straight_profile_has_no_invented_bend_radius() -> None:
    """
    A regular straight sweep has zero pinch without requiring a Frenet normal.
    """
    observed = inspect_normal_profile(
        Vector3(10, 0, 0), Vector3(2, 0, 0), Vector3(0, 1, 0), 1.5, PinchLimit()
    )
    assert observed.within_limit and observed.utilization == 0
    assert observed.actual_radius_mm is None and observed.inside_radius_mm is None


def test_lateral_bending_cannot_be_silently_evaluated_as_thickness_only() -> None:
    """
    Reject a curve bending along its profile width before returning a passing result.
    """
    with pytest.raises(ValueError, match="no lateral bending"):
        inspect_normal_profile(
            Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 1, 0), 1.5, PinchLimit()
        )


@pytest.mark.parametrize("thickness", (0.0, -1.0, True, float("nan")))
def test_malformed_thickness_rejects(thickness: float) -> None:
    """
    Refuse invalid physical dimensions rather than repairing the profile.
    """
    with pytest.raises(ValueError):
        inspect_normal_profile(
            Vector3(1, 0, 0), Vector3(0, 0, 0), Vector3(0, 1, 0), thickness, PinchLimit()
        )
