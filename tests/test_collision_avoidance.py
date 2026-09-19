"""
Regressions for deterministic best-effort separation of routed members.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from wire_bundler.routing import (
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
    sample_counts = {horizontal.wire_id: 0, vertical.wire_id: 0}
    original_sample_route = avoidance._sample_route
    original_fair_route = avoidance.fair_route
    auto_fractions: list[float] = []

    def counting_sample_route(route: RoutePreview) -> tuple[Vector3, ...]:
        """
        Count collision samples while delegating to the production sampler.
        """
        sample_counts[route.wire_id] += 1
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
        "wire_bundler.routing.avoidance.fair_route",
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
    assert sample_counts[horizontal.wire_id] == 1
    assert sample_counts[vertical.wire_id] > 1
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


def test_returns_residual_diagnostics_when_fixed_endpoints_make_contact_unavoidable() -> None:
    """
    Preserve best-effort output when two distinct groups share immovable endpoints.
    """
    first = _straight_route(1, "First", Vector3(0, 0, 0), Vector3(10, 0, 0))
    second = _straight_route(2, "Second", Vector3(0, 0, 0), Vector3(10, 0, 0))
    groups = (UUID(int=101), UUID(int=102))
    normals = ((Vector3(1, 0, 0),) * 2,) * 2
    transitions = ((TransitionLengths(),) * 2,) * 2

    routes, collisions = separate_route_collisions(
        (first, second),
        groups,
        (2.0, 2.0),
        normals,
        transitions,
        (1.05, 1.05),
        0.0,
    )

    assert len(routes) == 2
    assert collisions
    assert collisions[0].clearance_shortfall_mm > 0.0
