"""
Host-independent regression coverage for ribbon banking and lane order.
"""

from __future__ import annotations

import math
from uuid import UUID

from cable_bundler.routing import (
    RibbonEndFit,
    RoutePreview,
    Vector3,
    ribbon_frames,
    ribbon_has_hard_axis_bend,
    ribbon_lane_points,
    ribbon_line_lengths,
    solve_ribbon_shape,
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


def test_straight_ribbon_needs_no_length_correction() -> None:
    """
    Leave a physically equal-length straight cable free of artificial folds.
    """
    route = RoutePreview(UUID(int=6), "Straight", (Vector3(0, 0, 0), Vector3(0, 0, 100)))
    frames = ribbon_frames(route, Vector3(1, 0, 0), Vector3(1, 0, 0))

    shape = solve_ribbon_shape(frames, 40, 1.5)

    assert len(shape.frames) == 32
    assert shape.lengths_mm == (100.0,) * 40
    assert shape.meets_length_target
    assert not shape.folded
    assert shape.end_lead_mm == 0.0
    assert shape.minimum_end_radius_mm is None


def test_single_line_ribbon_keeps_its_supported_domain_shape() -> None:
    """
    Keep the existing one-line ribbon setting valid without spanwise neighbors.
    """
    route = RoutePreview(UUID(int=10), "Single", (Vector3(0, 0, 0), Vector3(0, 0, 50)))
    frames = ribbon_frames(route, Vector3(1, 0, 0), Vector3(1, 0, 0))

    shape = solve_ribbon_shape(frames, 1, 1.5)

    assert shape.lengths_mm == (50.0,)
    assert shape.meets_length_target
    assert shape.maximum_pitch_ratio == 1.0


def test_bent_ribbon_reports_lengths_and_preserves_end_anchors() -> None:
    """
    Fit limited slack while leaving every physical end at its original guide.
    """
    route = RoutePreview(
        UUID(int=7),
        "Bend",
        (Vector3(0, 0, 0), Vector3(0, 0, 40), Vector3(30, 0, 70)),
    )
    frames = ribbon_frames(route, Vector3(1, 0, 0), Vector3(1, 0, 0))
    original = ribbon_lane_points(frames, 3, 1.5)

    shape = solve_ribbon_shape(frames, 3, 1.5)

    assert shape.folded
    assert shape.lanes[0][0] == original[0][0]
    assert shape.lanes[-1][-1] == original[-1][-1]
    assert shape.spread < 0.03
    assert not shape.meets_length_target
    assert shape.maximum_pitch_ratio <= 1.030001
    assert shape == solve_ribbon_shape(frames, 3, 1.5)


def test_moderate_twist_reaches_length_target_without_separating_lines() -> None:
    """
    Use modest local folding for a practical forty-line bank change.
    """
    route = RoutePreview(UUID(int=9), "Bank", (Vector3(0, 0, 0), Vector3(0, 0, 100)))
    angle = math.radians(30.0)
    frames = ribbon_frames(
        route,
        Vector3(1, 0, 0),
        Vector3(math.cos(angle), math.sin(angle), 0),
    )

    shape = solve_ribbon_shape(frames, 40, 1.5)

    assert shape.folded
    assert shape.meets_length_target
    assert shape.maximum_pitch_ratio <= 1.030001


def test_severe_twist_warns_instead_of_stretching_joined_web() -> None:
    """
    Never claim equal line lengths by pulling a forty-line ribbon apart.
    """
    route = RoutePreview(UUID(int=8), "Twist", (Vector3(0, 0, 0), Vector3(0, 0, 100)))
    frames = ribbon_frames(route, Vector3(1, 0, 0), Vector3(-1, 0, 0))

    shape = solve_ribbon_shape(frames, 40, 1.5)

    assert shape.folded
    assert not shape.meets_length_target
    assert shape.spread > 0.20
    assert shape.maximum_pitch_ratio <= 1.030001


def test_dense_folds_reduce_length_spread_without_stretching_the_web() -> None:
    """
    Smooth conductor-to-conductor amplitudes before bounding the entire fold.
    """
    route = RoutePreview(
        UUID(int=13),
        "Wrinkle",
        (Vector3(0, 0, 0), Vector3(0, 0, 40), Vector3(30, 0, 75)),
    )
    frames = ribbon_frames(route, Vector3(1, 0, 0), Vector3(1, 0, 0), maximum_sections=49)
    base_lengths = ribbon_line_lengths(ribbon_lane_points(frames, 19, 0.75))
    base_spread = (max(base_lengths) - min(base_lengths)) / max(base_lengths)

    shape = solve_ribbon_shape(frames, 19, 0.75)

    assert shape.folded
    assert shape.spread < base_spread - 0.05
    assert shape.maximum_pitch_ratio <= 1.030001
    assert shape.lengths_mm == ribbon_line_lengths(shape.lanes)
    assert shape == solve_ribbon_shape(frames, 19, 0.75)


def test_terminal_fit_blends_exact_guide_samples_and_remeasures_lines() -> None:
    """
    Match both sampled guide ends while retaining the untouched route interior.
    """
    route = RoutePreview(UUID(int=11), "Fit", (Vector3(0, 0, 0), Vector3(0, 0, 100)))
    frames = ribbon_frames(route, Vector3(1, 0, 0), Vector3(1, 0, 0))
    start = RibbonEndFit(
        tuple(Vector3((index - 1) * 1.5, 0.03 * (index - 1) ** 2, 0) for index in range(3)),
        (Vector3(0, 1, 0),) * 3,
    )
    end = RibbonEndFit(
        tuple(Vector3((index - 1) * 1.5, 0.2 * (index - 1), 100) for index in range(3)),
        (Vector3(0, 1, 0),) * 3,
    )

    shape = solve_ribbon_shape(frames, 3, 1.5, start_fit=start, end_fit=end)

    assert tuple(lane[0] for lane in shape.lanes) == start.centers
    assert tuple(lane[-1] for lane in shape.lanes) == end.centers
    assert all(
        lane[6] == Vector3((index - 1) * 1.5, 0, frames[6].origin.z)
        for index, lane in enumerate(shape.lanes)
    )
    assert shape.end_lead_mm == 13.5
    assert shape.lengths_mm == ribbon_line_lengths(shape.lanes)
    assert shape.maximum_pitch_ratio >= 1.0


def test_guide_approach_scales_with_line_diameter() -> None:
    """
    Give larger lines a longer tangent-matched lead without moving their ends.
    """
    route = RoutePreview(UUID(int=14), "Entry", (Vector3(0, 0, 0), Vector3(0, 0, 100)))
    frames = ribbon_frames(route, Vector3(1, 0, 0), Vector3(1, 0, 0), maximum_sections=49)
    fit = RibbonEndFit(
        (Vector3(0, 0, 0),),
        (Vector3(0, 1, 0),),
        approach_normal=Vector3(0, 1, 1),
    )

    small = solve_ribbon_shape(frames, 1, 1.0, start_fit=fit)
    large = solve_ribbon_shape(frames, 1, 2.0, start_fit=fit)

    assert small.lanes[0][0] == large.lanes[0][0] == fit.centers[0]
    assert small.end_lead_mm == 9.0
    assert large.end_lead_mm == 18.0
    assert small.lanes[0][1].y > 0.0
    assert large.lanes[0][1].y > small.lanes[0][1].y
    assert small.lanes[0][12] == large.lanes[0][12] == frames[12].origin
    assert small.minimum_end_radius_mm is not None
    assert large.minimum_end_radius_mm is not None
    assert large.minimum_end_radius_mm > small.minimum_end_radius_mm


def test_terminal_fit_rejects_missing_conductors() -> None:
    """
    Never silently misalign a guide sample with conductor identity.
    """
    route = RoutePreview(UUID(int=12), "Fit", (Vector3(0, 0, 0), Vector3(0, 0, 50)))
    frames = ribbon_frames(route, Vector3(1, 0, 0), Vector3(1, 0, 0))
    incomplete = RibbonEndFit((Vector3(0, 0, 0),), (Vector3(0, 1, 0),))

    try:
        solve_ribbon_shape(frames, 3, 1.5, start_fit=incomplete)
    except ValueError as error:
        assert "every line" in str(error)
    else:
        raise AssertionError("Incomplete ribbon guide samples must not be accepted.")
