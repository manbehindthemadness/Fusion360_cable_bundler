"""
Regression tests for reusable procedural stripe geometry.
"""

from uuid import UUID

import pytest

from wire_bundler.domain import StripePattern, WireColor, WireStripe
from wire_bundler.routing import (
    CubicBezier,
    RoutePreview,
    Vector3,
    build_continuous_stripe_mesh,
    build_stripe_mesh,
)


def _straight_route() -> RoutePreview:
    curve = CubicBezier(
        Vector3(0.0, 0.0, 0.0),
        Vector3(3.0, 0.0, 0.0),
        Vector3(7.0, 0.0, 0.0),
        Vector3(10.0, 0.0, 0.0),
    )
    return RoutePreview(
        UUID("50000000-0000-0000-0000-000000000001"),
        "001",
        (curve.start, curve.end),
        (curve,),
    )


def _straight_segment(identity: int, start: Vector3, end: Vector3) -> RoutePreview:
    """
    Build one exact straight segment between arbitrary endpoints.
    """
    delta = Vector3(
        (end.x - start.x) / 3.0,
        (end.y - start.y) / 3.0,
        (end.z - start.z) / 3.0,
    )
    curve = CubicBezier(
        start,
        start.translated(delta, 1.0),
        end.translated(delta, -1.0),
        end,
    )
    return RoutePreview(UUID(int=identity), str(identity), (start, end), (curve,))


def _components(vector: Vector3) -> tuple[float, float, float]:
    """
    Return vector components for approximate comparisons.
    """
    return vector.x, vector.y, vector.z


def test_builds_longitudinal_surface_band() -> None:
    """
    Produce stable vertices and triangle indices around a circular body.
    """
    stripe = WireStripe(WireColor("Red", 255, 0, 0), 0.25)

    vertices, indices = build_stripe_mesh(_straight_route(), stripe, 0.5)

    assert len(vertices) > 2
    assert len(indices) > 0
    assert len(indices) % 3 == 0


def test_dashed_pattern_omits_repeat_segments() -> None:
    """
    Keep dashed stripe gaps in the host-independent mesh.
    """
    continuous = WireStripe(
        WireColor("White", 255, 255, 255),
        0.2,
        repeat_mm=2.0,
    )
    dashed = WireStripe(
        continuous.color,
        continuous.width_mm,
        StripePattern.DASHED,
        repeat_mm=2.0,
    )

    _, continuous_indices = build_stripe_mesh(_straight_route(), continuous, 0.5)
    _, dashed_indices = build_stripe_mesh(_straight_route(), dashed, 0.5)

    assert 0 < len(dashed_indices) < len(continuous_indices)


def test_continues_radial_position_across_opposed_segment_tangents() -> None:
    """
    Reuse the same physical face position when a child traversal reverses direction.
    """
    junction = Vector3(0.0, 0.0, 0.0)
    parent = _straight_segment(1, Vector3(-3.0, 0.0, 0.0), junction)
    child = _straight_segment(2, junction, Vector3(-3.0, 0.0, 0.0))
    stripe = WireStripe(WireColor("Red", 255, 0, 0), 0.25, angle_deg=37.0)

    parent_mesh = build_continuous_stripe_mesh(parent, stripe, 0.5)
    assert parent_mesh.end is not None
    child_mesh = build_continuous_stripe_mesh(child, stripe, 0.5, parent_mesh.end)
    assert child_mesh.start is not None
    assert _components(child_mesh.start.radial) == pytest.approx(
        _components(parent_mesh.end.radial)
    )


def test_continues_helical_position_and_repeat_phase() -> None:
    """
    Carry both the helical surface position and repeat distance into a child.
    """
    junction = Vector3(2.5, 0.0, 0.0)
    parent = _straight_segment(3, Vector3(0.0, 0.0, 0.0), junction)
    child = _straight_segment(4, junction, Vector3(5.0, 0.0, 0.0))
    stripe = WireStripe(
        WireColor("White", 255, 255, 255),
        0.2,
        StripePattern.HELICAL,
        angle_deg=15.0,
        repeat_mm=4.0,
    )

    parent_mesh = build_continuous_stripe_mesh(parent, stripe, 0.5)
    assert parent_mesh.end is not None
    child_mesh = build_continuous_stripe_mesh(child, stripe, 0.5, parent_mesh.end)

    assert child_mesh.start is not None
    assert child_mesh.end is not None
    assert _components(child_mesh.start.radial) == pytest.approx(
        _components(parent_mesh.end.radial)
    )
    assert child_mesh.start.repeat_phase_mm == pytest.approx(2.5)
    assert child_mesh.end.repeat_phase_mm == pytest.approx(1.0)


def test_continues_dashed_gap_instead_of_restarting_repeat() -> None:
    """
    Keep a child inside its inherited gap when an independent mesh would restart solid.
    """
    junction = Vector3(3.0, 0.0, 0.0)
    parent = _straight_segment(5, Vector3(0.0, 0.0, 0.0), junction)
    child = _straight_segment(6, junction, Vector3(4.0, 0.0, 0.0))
    stripe = WireStripe(
        WireColor("White", 255, 255, 255),
        0.2,
        StripePattern.DASHED,
        repeat_mm=4.0,
    )

    parent_mesh = build_continuous_stripe_mesh(parent, stripe, 0.5)
    assert parent_mesh.end is not None
    continued = build_continuous_stripe_mesh(child, stripe, 0.5, parent_mesh.end)
    restarted = build_continuous_stripe_mesh(child, stripe, 0.5)

    assert continued.triangle_indices == ()
    assert restarted.triangle_indices
