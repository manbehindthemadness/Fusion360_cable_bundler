"""
Regression tests for reusable procedural stripe geometry.
"""

from uuid import UUID

from wire_bundler.domain import StripePattern, WireColor, WireStripe
from wire_bundler.routing import CubicBezier, RoutePreview, Vector3, build_stripe_mesh


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
