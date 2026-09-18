"""
Regressions for deterministic best-effort separation of routed members.
"""

from __future__ import annotations

from uuid import UUID

from wire_bundler.routing import (
    RoutePreview,
    TransitionLengths,
    Vector3,
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


def test_repairs_crossing_members_with_a_bounded_free_detour() -> None:
    """
    Separate a common between-guide crossing without moving either guide endpoint.
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
    assert not collisions
    assert separate_route_collisions(*inputs) == (routes, collisions)


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
