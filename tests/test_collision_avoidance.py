"""
Regressions for deterministic transactional separation of routed members.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from cable_bundler.routing import (
    RoutePreview,
    TransitionLengths,
    Vector3,
    avoidance,
    fair_route,
    route_collisions,
    separate_route_collisions,
)


def _straight_route(identity: int, label: str, start: Vector3, end: Vector3) -> RoutePreview:
    """
    Build one exactly straight faired route for collision tests.
    """
    direction = Vector3(end.x - start.x, end.y - start.y, end.z - start.z)
    route = RoutePreview(UUID(int=identity), label, (start, end))
    return fair_route(route, (direction, direction), minimum_bend_radius_mm=1.05)


def _separate_horizontal_routes(
    routes: tuple[RoutePreview, ...],
    group_ids: tuple[UUID, ...],
    diameters_mm: tuple[float, ...],
) -> tuple[tuple[RoutePreview, ...], tuple[avoidance.RouteCollision, ...]]:
    """
    Run collision repair for straight horizontal regression routes.
    """
    route_count = len(routes)
    normals = tuple((Vector3(1, 0, 0),) * 2 for _route in routes)
    transitions = tuple((TransitionLengths(),) * 2 for _route in routes)
    return separate_route_collisions(
        routes,
        group_ids,
        diameters_mm,
        normals,
        transitions,
        (1.05,) * route_count,
        0.0,
    )


def test_repairs_crossing_members_with_a_broad_offset_corridor() -> None:
    """
    Separate a crossing with two aligned supports and fixed guide endpoints.
    """
    horizontal = _straight_route(1, "Horizontal", Vector3(-10, 0, 0), Vector3(10, 0, 0))
    vertical = _straight_route(2, "Vertical", Vector3(0, -10, 0), Vector3(0, 10, 0))
    groups = (UUID(int=101), UUID(int=102))
    normals = (
        (Vector3(1, 0, 0), Vector3(1, 0, 0)),
        (Vector3(0, 1, 0), Vector3(0, 1, 0)),
    )
    transitions = ((TransitionLengths(),) * 2,) * 2

    inputs = (
        (horizontal, vertical),
        groups,
        (2.0, 2.0),
        normals,
        transitions,
        (1.05, 1.05),
        0.0,
    )
    routes, collisions = separate_route_collisions(*inputs)

    assert routes[0].points[0] == horizontal.points[0]
    assert routes[0].points[-1] == horizontal.points[-1]
    assert routes[1].points[0] == vertical.points[0]
    assert routes[1].points[-1] == vertical.points[-1]
    changed_route = routes[0] if len(routes[0].points) > 2 else routes[1]
    assert len(changed_route.points) == 4
    first_support, second_support = changed_route.points[1:3]
    chord = Vector3(
        changed_route.points[-1].x - changed_route.points[0].x,
        changed_route.points[-1].y - changed_route.points[0].y,
        changed_route.points[-1].z - changed_route.points[0].z,
    )
    support_delta = Vector3(
        second_support.x - first_support.x,
        second_support.y - first_support.y,
        second_support.z - first_support.z,
    )
    assert support_delta.x * chord.y == pytest.approx(support_delta.y * chord.x)
    assert not collisions
    assert separate_route_collisions(*inputs) == (routes, collisions)


def test_repair_resamples_only_the_candidate_route(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep unchanged route samples cached while evaluating a detour.
    """
    horizontal = _straight_route(1, "Horizontal", Vector3(-10, 0, 0), Vector3(10, 0, 0))
    vertical = _straight_route(2, "Vertical", Vector3(0, -10, 0), Vector3(0, 10, 0))
    sample_counts = {horizontal.cable_id: 0, vertical.cable_id: 0}
    original_sample_route = avoidance._sample_route
    original_fair_route = avoidance.fair_route
    auto_fractions: list[float] = []

    def counting_sample_route(route: RoutePreview) -> tuple[Vector3, ...]:
        """
        Count collision samples while delegating to the production sampler.
        """
        sample_counts[route.cable_id] += 1
        return original_sample_route(route)

    def recording_fair_route(*args: object, **kwargs: object) -> RoutePreview:
        """
        Record the harness Auto policy used to refair collision detours.
        """
        fraction = kwargs["auto_transition_fraction"]
        assert not isinstance(fraction, bool) and isinstance(fraction, (int, float))
        auto_fractions.append(float(fraction))
        return original_fair_route(*args, **kwargs)

    monkeypatch.setattr(avoidance, "_sample_route", counting_sample_route)
    monkeypatch.setattr(
        "cable_bundler.routing.avoidance.fair_route",
        recording_fair_route,
    )
    routes, collisions = separate_route_collisions(
        (horizontal, vertical),
        (UUID(int=101), UUID(int=102)),
        (2.0, 2.0),
        (
            (Vector3(1, 0, 0), Vector3(1, 0, 0)),
            (Vector3(0, 1, 0), Vector3(0, 1, 0)),
        ),
        ((TransitionLengths(),) * 2,) * 2,
        (1.05, 1.05),
        0.0,
        auto_transition_fraction=0.5,
    )

    assert not collisions
    assert routes[0] == horizontal
    assert sample_counts[horizontal.cable_id] == 1
    assert sample_counts[vertical.cable_id] > 1
    assert auto_fractions
    assert set(auto_fractions) == {0.5}


def test_repeated_span_repair_enlarges_one_existing_corridor() -> None:
    """
    Reuse two supports instead of accumulating independent mid-span waves.
    """
    route = _straight_route(20, "Reusable", Vector3(-10, 0, 0), Vector3(10, 0, 0))
    normals = (Vector3(1, 0, 0), Vector3(1, 0, 0))
    transitions = (TransitionLengths(), TransitionLengths())
    first = next(
        avoidance._detour_candidates(
            route,
            normals,
            transitions,
            (0,),
            1.05,
            Vector3(0, 0, 0),
            Vector3(0, 1, 0),
            2.0,
            0.25,
        )
    )
    second = next(
        avoidance._detour_candidates(
            first[0],
            first[1],
            first[2],
            first[3],
            1.05,
            Vector3(0, -2, 0),
            Vector3(0, 1, 0),
            1.0,
            0.25,
        )
    )

    assert len(first[0].points) == 4
    assert len(second[0].points) == 4
    assert second[3] == (0, 0, 0)


def test_ignores_intentional_same_group_junction_contact() -> None:
    """
    Permit route legs from one multi-ended conductor to meet at their shared hub.
    """
    first = _straight_route(1, "Leg 1", Vector3(-10, 0, 0), Vector3(0, 0, 0))
    second = _straight_route(2, "Leg 2", Vector3(0, 0, 0), Vector3(0, 10, 0))
    group_id = UUID(int=100)

    collisions = route_collisions((first, second), (group_id, group_id), (2.0, 2.0))

    assert collisions == ()


def test_minimum_gap_is_surface_separation_not_an_avoidance_toggle() -> None:
    """
    Detect a requested positive gap even when the physical tubes do not overlap.
    """
    first = _straight_route(1, "First", Vector3(0, 0, 0), Vector3(10, 0, 0))
    second = _straight_route(2, "Second", Vector3(0, 2.2, 0), Vector3(10, 2.2, 0))
    groups = (UUID(int=101), UUID(int=102))

    touching = route_collisions((first, second), groups, (2.0, 2.0), 0.0)
    spaced = route_collisions((first, second), groups, (2.0, 2.0), 0.3)

    assert touching == ()
    assert len(spaced) == 1
    assert spaced[0].clearance_shortfall_mm > 0.0


def test_equal_diameter_routes_at_planned_spacing_do_not_diverge() -> None:
    """
    Keep equal-size parallel routes stable when their surfaces exactly touch.
    """
    first = _straight_route(1, "First", Vector3(0, 0, 0), Vector3(10, 0, 0))
    second = _straight_route(2, "Second", Vector3(0, 2.0, 0), Vector3(10, 2.0, 0))
    groups = (UUID(int=111), UUID(int=112))

    routes, collisions = _separate_horizontal_routes(
        (first, second),
        groups,
        (2.0, 2.0),
    )

    assert routes == (first, second)
    assert collisions == ()


def test_collision_capsules_report_physical_overlap() -> None:
    """
    Report penetration from physical radii rather than sampling inflation.
    """
    first = _straight_route(1, "First", Vector3(0, 0, 0), Vector3(10, 0, 0))
    second = _straight_route(2, "Second", Vector3(0, 1.96, 0), Vector3(10, 1.96, 0))

    collisions = route_collisions(
        (first, second),
        (UUID(int=111), UUID(int=112)),
        (2.0, 2.0),
        0.0,
    )

    assert len(collisions) == 1
    assert collisions[0].clearance_shortfall_mm == pytest.approx(0.04)


def test_returns_residual_diagnostics_when_fixed_endpoints_make_contact_unavoidable() -> None:
    """
    Roll back partial repair when distinct groups share immovable endpoints.
    """
    first = _straight_route(1, "First", Vector3(0, 0, 0), Vector3(10, 0, 0))
    second = _straight_route(2, "Second", Vector3(0, 0, 0), Vector3(10, 0, 0))
    groups = (UUID(int=101), UUID(int=102))

    routes, collisions = _separate_horizontal_routes(
        (first, second),
        groups,
        (2.0, 2.0),
    )

    assert routes == (first, second)
    assert collisions
    assert collisions[0].clearance_shortfall_mm > 0.0


def test_rolls_back_partial_repair_from_live_equal_diameter_tangle() -> None:
    """
    Keep a failed repair from adding divergent supports to captured live routes.
    """
    route_points = (
        (
            Vector3(-11.219261591181533, 35.204291839389924, -12.000000000000002),
            Vector3(-11.219261591181533, 35.204291839389924, -6.000000000000001),
            Vector3(-13.536555236518895, 30.396546798692402, 0.0),
            Vector3(-10.428977052707834, 30.396546798692402, 14.533921942997779),
            Vector3(2.465576701782069, 34.144085526251715, 19.659714013670197),
        ),
        (
            Vector3(-8.655174950136866, 28.96593558740924, -6.000000000000001),
            Vector3(-12.036555236518895, 30.396546798692402, 0.0),
            Vector3(-9.200248986274348, 30.396546798692402, 13.673557288471208),
            Vector3(2.465576701782069, 34.144085526251715, 18.159714013670197),
        ),
    )
    normals = (
        (
            Vector3(0.0, -0.0, 1.0),
            Vector3(-0.1345273974583756, -0.2791072375612931, 0.9507899501330356),
            Vector3(0.028228643654086498, -0.1717307057476598, 0.9847394114083489),
            Vector3(0.6132934910743355, 0.10996141795282702, 0.7821633974865211),
            Vector3(0.7071067811865475, 0.7071067811865476, 1.1775693440128314e-16),
        ),
        (
            Vector3(0.0, -0.0, 1.0),
            Vector3(-0.020728528784056156, 0.054404472981348914, 0.9983038021634848),
            Vector3(0.60711901083829, 0.11972987384831728, 0.785538836714648),
            Vector3(0.7071067811865475, 0.7071067811865476, 1.1775693440128314e-16),
        ),
    )
    raw_routes = (
        RoutePreview(
            UUID("92ae97f0-7bae-5905-afe2-06063dd2404e"),
            "Group 2 Leg 1",
            route_points[0],
        ),
        RoutePreview(
            UUID("f0592a26-ba7e-55a3-baed-4da1a3d7aa19"),
            "Group 3 Leg 2",
            route_points[1],
        ),
    )
    routes = tuple(
        fair_route(
            route,
            route_normals,
            minimum_bend_radius_mm=0.7875,
            auto_transition_fraction=0.4375,
        )
        for route, route_normals in zip(raw_routes, normals)
    )

    separated, collisions = separate_route_collisions(
        routes,
        (
            UUID("b057e50a-3fdb-4798-b9b0-cb3f18607e1f"),
            UUID("c61d15ea-a627-4903-abbc-8df72dd0f423"),
        ),
        (1.5, 1.5),
        normals,
        tuple(tuple(TransitionLengths() for _point in points) for points in route_points),
        (0.7875, 0.7875),
        0.0,
        0.4375,
    )

    assert separated == routes
    assert len(collisions) == 1
    assert collisions == route_collisions(
        routes,
        (
            UUID("b057e50a-3fdb-4798-b9b0-cb3f18607e1f"),
            UUID("c61d15ea-a627-4903-abbc-8df72dd0f423"),
        ),
        (1.5, 1.5),
    )
    assert collisions[0].clearance_shortfall_mm == pytest.approx(0.27064295794047255)
