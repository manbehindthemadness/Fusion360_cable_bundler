"""
Host-independent regression coverage for ribbon banking and lane order.
"""

from __future__ import annotations

import math
from uuid import UUID

from cable_bundler.routing import (
    RoutePreview,
    Vector3,
    ribbon_frames,
    ribbon_has_hard_axis_bend,
    ribbon_lane_points,
)
from cable_bundler.routing.geometry import dot


def test_straight_ribbon_preserves_line_order_and_width() -> None:
    """
    Keep forty lines distinct without constructing forty route features.
    """
    route = RoutePreview(UUID(int=1), "Ribbon", (Vector3(0, 0, 0), Vector3(0, 0, 100)))
    frames = ribbon_frames(route, Vector3(1, 0, 0), Vector3(1, 0, 0))
    lanes = ribbon_lane_points(frames, 40, 1.5)

    assert len(lanes) == 40
    assert math.isclose(lanes[-1][0].x - lanes[0][0].x, 58.5)
    assert math.isclose(lanes[-1][-1].x - lanes[0][-1].x, 58.5)
    assert all(math.isclose(frame.width.x, 1.0) for frame in frames)


def test_opposed_guide_directions_bank_without_swapping_lanes() -> None:
    """
    Honor both signed guide directions even when the ribbon must half-turn.
    """
    route = RoutePreview(
        UUID(int=2),
        "Ribbon",
        (Vector3(0, 0, 0), Vector3(0, 0, 50), Vector3(0, 0, 100)),
    )
    frames = ribbon_frames(route, Vector3(1, 0, 0), Vector3(-1, 0, 0))
    lanes = ribbon_lane_points(frames, 3, 1.5)

    assert dot(frames[0].width, Vector3(1, 0, 0)) > 0.99
    assert dot(frames[-1].width, Vector3(-1, 0, 0)) > 0.99
    assert lanes[0][0].x < lanes[-1][0].x
    assert lanes[0][-1].x > lanes[-1][-1].x


def test_curved_route_sections_remain_perpendicular() -> None:
    """
    Keep the lobe section orthogonal while banking through a bend.
    """
    route = RoutePreview(
        UUID(int=3),
        "Ribbon",
        (Vector3(0, 0, 0), Vector3(0, 0, 40), Vector3(0, 30, 70)),
    )
    frames = ribbon_frames(route, Vector3(1, 0, 0), Vector3(0, 0, 1))

    assert all(abs(dot(frame.tangent, frame.width)) < 1e-9 for frame in frames)
    assert all(abs(dot(frame.tangent, frame.thickness)) < 1e-9 for frame in frames)
    assert all(abs(dot(frame.width, frame.thickness)) < 1e-9 for frame in frames)


def test_stiff_direction_bend_is_distinguished_from_easy_bend() -> None:
    """
    Warn for width-plane routing turns without warning for thickness-plane turns.
    """
    hard = RoutePreview(
        UUID(int=4),
        "Hard",
        (Vector3(0, 0, 0), Vector3(0, 0, 30), Vector3(20, 0, 50)),
    )
    easy = RoutePreview(
        UUID(int=5),
        "Easy",
        (Vector3(0, 0, 0), Vector3(0, 0, 30), Vector3(0, 20, 50)),
    )

    assert ribbon_has_hard_axis_bend(ribbon_frames(hard, Vector3(1, 0, 0), Vector3(1, 0, 0)))
    assert not ribbon_has_hard_axis_bend(ribbon_frames(easy, Vector3(1, 0, 0), Vector3(1, 0, 0)))
