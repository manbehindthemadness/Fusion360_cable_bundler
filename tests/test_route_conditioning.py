"""
Tests for bounded end-guide and shared-junction route conditioning.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

import pytest

from wire_bundler.routing import RoutePreview, TransitionLengths, Vector3
from wire_bundler.routing.conditioning import (
    CircularGuideConstraint,
    condition_connection_points,
    condition_control_points,
    condition_junction_points,
    condition_route_normals,
    junction_tangent_targets,
)
from wire_bundler.routing.geometry import difference, dot, magnitude


def _guide(origin: Vector3, radius_mm: Optional[float]) -> CircularGuideConstraint:
    """
    Build one horizontal circular guide for deterministic conditioning tests.
    """
    return CircularGuideConstraint(
        origin,
        Vector3(0.0, 0.0, 1.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
        radius_mm,
    )


def test_end_guide_relocation_scales_with_auto_transition_share() -> None:
    """
    Move only an intermediate guide toward the natural bounded crossing as Auto relaxes.
    """
    constraints = (
        _guide(Vector3(0.0, 0.0, 0.0), None),
        _guide(Vector3(0.0, 0.0, 10.0), 10.0),
    )
    transitions = (TransitionLengths(), TransitionLengths())
    target = Vector3(10.0, 0.0, 20.0)

    tight = condition_connection_points(constraints, target, 2.0, transitions, 0.25)
    loose = condition_connection_points(constraints, target, 2.0, transitions, 0.5)

    assert tight[0] == loose[0] == constraints[0].origin
    assert tight[1] == Vector3(9.0, 0.0, 10.0)
    assert loose[1] == Vector3(5.0, 0.0, 10.0)
    assert loose[1].x <= constraints[1].usable_radius_mm - 1.0


def test_soft_guide_tangent_relaxes_without_changing_terminal_normal() -> None:
    """
    Preserve the terminal tangent while a Loose intermediate guide follows the through-path.
    """
    route = RoutePreview(
        UUID(int=1),
        "End guide",
        (
            Vector3(0.0, 0.0, 0.0),
            Vector3(5.0, 0.0, 10.0),
            Vector3(10.0, 0.0, 20.0),
        ),
    )
    normals = (Vector3(0.0, 0.0, 1.0),) * 3
    transitions = (TransitionLengths(),) * 3

    conditioned = condition_route_normals(
        route,
        normals,
        transitions,
        frozenset({1}),
        {},
        0.5,
    )

    assert conditioned[0] == normals[0]
    assert conditioned[2] == normals[2]
    assert conditioned[1].x == pytest.approx(1.0 / 5.0**0.5)
    assert conditioned[1].z == pytest.approx(2.0 / 5.0**0.5)


def test_three_way_junction_keeps_each_leg_on_its_own_guide_facing_side() -> None:
    """
    Aim every split leg at its immediate ordered neighbor without a shared trunk axis.
    """
    junction_id = UUID(int=100)
    group_id = UUID(int=200)
    routes = (
        RoutePreview(UUID(int=1), "Right", (Vector3(0, 0, 0), Vector3(10, 0, 10))),
        RoutePreview(UUID(int=2), "Left", (Vector3(0, 0, 0), Vector3(-10, 0, 10))),
        RoutePreview(UUID(int=3), "Branch", (Vector3(0, 0, 0), Vector3(0, 10, 10))),
    )
    control_ids = ((junction_id, None),) * 3
    targets = junction_tangent_targets(
        routes,
        (group_id,) * 3,
        control_ids,
        frozenset({junction_id}),
    )

    expected_targets = (
        Vector3(10, 0, 10),
        Vector3(-10, 0, 10),
        Vector3(0, 10, 10),
    )
    assert targets == tuple({0: target} for target in expected_targets)
    for route, route_targets, expected_target in zip(routes, targets, expected_targets):
        conditioned = condition_route_normals(
            route,
            (Vector3(0, 0, 1), Vector3(0, 0, 1)),
            (TransitionLengths(), TransitionLengths()),
            frozenset(),
            route_targets,
            0.5,
        )
        assert dot(conditioned[0], expected_target) > 0.0


def test_junction_leg_at_route_end_targets_its_previous_ordered_guide() -> None:
    """
    Preserve guide-facing direction when traversal reaches rather than leaves a junction.
    """
    junction_id = UUID(int=110)
    route = RoutePreview(
        UUID(int=111),
        "Arriving",
        (Vector3(12, -4, 8), Vector3(0, 0, 0)),
    )

    targets = junction_tangent_targets(
        (route,),
        (UUID(int=112),),
        ((None, junction_id),),
        frozenset({junction_id}),
    )

    assert targets == ({1: Vector3(12, -4, 8)},)


def test_junction_cluster_translation_preserves_packing_inside_aperture() -> None:
    """
    Move all packed crossings together toward their incident route geometry.
    """
    junction_id = UUID(int=500)
    left_group = UUID(int=501)
    right_group = UUID(int=502)
    routes = (
        RoutePreview(UUID(int=11), "Left", (Vector3(-2, 0, 0), Vector3(-2, 8, 8))),
        RoutePreview(UUID(int=12), "Right", (Vector3(2, 0, 0), Vector3(2, 8, 8))),
    )
    constraint = _guide(Vector3(0, 0, 0), 10.0)

    conditioned = condition_junction_points(
        routes,
        (left_group, right_group),
        (2.0, 2.0),
        ((junction_id, None), (junction_id, None)),
        ((TransitionLengths(), TransitionLengths()),) * 2,
        {junction_id: constraint},
        0.5,
    )

    assert conditioned[0].points[0] == Vector3(-2.0, 8.0, 0.0)
    assert conditioned[1].points[0] == Vector3(2.0, 8.0, 0.0)
    original_spacing = magnitude(difference(routes[1].points[0], routes[0].points[0]))
    conditioned_spacing = magnitude(difference(conditioned[1].points[0], conditioned[0].points[0]))
    assert conditioned_spacing == pytest.approx(original_spacing)
    for route in conditioned:
        assert magnitude(difference(route.points[0], constraint.origin)) <= 9.0


def test_tight_junction_cluster_does_not_move() -> None:
    """
    Preserve packed crossings when the automatic interpolation preset is Tight.
    """
    junction_id = UUID(int=600)
    route = RoutePreview(
        UUID(int=13),
        "Tight",
        (Vector3(0, 0, 0), Vector3(5, 5, 10)),
    )

    conditioned = condition_junction_points(
        (route,),
        (UUID(int=601),),
        (2.0,),
        ((junction_id, None),),
        ((TransitionLengths(), TransitionLengths()),),
        {junction_id: _guide(Vector3(0, 0, 0), 10.0)},
        0.25,
    )

    assert conditioned == (route,)


def test_internal_junction_point_moves_to_and_follows_its_through_route() -> None:
    """
    Condition a degree-two junction retained inside one unsplit topology leg.
    """
    junction_id = UUID(int=700)
    group_id = UUID(int=701)
    route = RoutePreview(
        UUID(int=14),
        "Through junction",
        (
            Vector3(-10, 5, 0),
            Vector3(0, 0, 0),
            Vector3(10, 5, 0),
        ),
    )
    control_ids = ((None, junction_id, None),)
    transitions = ((TransitionLengths(),) * 3,)

    conditioned = condition_junction_points(
        (route,),
        (group_id,),
        (2.0,),
        control_ids,
        transitions,
        {junction_id: _guide(Vector3(0, 0, 0), 10.0)},
        0.5,
    )
    targets = junction_tangent_targets(
        conditioned,
        (group_id,),
        control_ids,
        frozenset({junction_id}),
    )

    assert conditioned[0].points[1] == Vector3(0.0, 5.0, 0.0)
    assert targets == ({1: Vector3(20.0, 0.0, 0.0)},)


def test_multiple_end_guides_relax_toward_one_feasible_passage() -> None:
    """
    Improve an ordered guide stack with bounded forward and backward sweeps.
    """
    constraints = (
        _guide(Vector3(0, 0, 0), None),
        _guide(Vector3(0, 0, 10), 20.0),
        _guide(Vector3(0, 0, 20), 20.0),
    )
    target = Vector3(12, 0, 30)
    points = condition_connection_points(
        constraints,
        target,
        2.0,
        (TransitionLengths(),) * 3,
        0.5,
    )

    assert points[0] == constraints[0].origin
    assert 3.5 < points[1].x < 4.5
    assert 7.5 < points[2].x < 8.5
    assert all(abs(point.y) <= 1e-12 for point in points)


def test_pathway_controls_relax_toward_one_direct_passage() -> None:
    """
    Remove repeated center attraction with two simultaneous control passes.
    """
    first_control = UUID(int=801)
    second_control = UUID(int=802)
    route = RoutePreview(
        UUID(int=803),
        "Pathway",
        (
            Vector3(0, 0, 0),
            Vector3(0, 0, 10),
            Vector3(0, 0, 20),
            Vector3(12, 0, 30),
        ),
    )

    conditioned = condition_control_points(
        (route,),
        (UUID(int=804),),
        (2.0,),
        ((None, first_control, second_control, None),),
        ((TransitionLengths(),) * 4,),
        {
            first_control: _guide(Vector3(0, 0, 10), 20.0),
            second_control: _guide(Vector3(0, 0, 20), 20.0),
        },
        0.5,
    )

    assert conditioned[0].points[1] == Vector3(3.0, 0.0, 10.0)
    assert conditioned[0].points[2] == Vector3(6.0, 0.0, 20.0)


def test_pathway_control_cluster_preserves_member_spacing() -> None:
    """
    Translate a packed pathway crossing without changing its member layout.
    """
    control_id = UUID(int=811)
    routes = (
        RoutePreview(
            UUID(int=812),
            "Left",
            (Vector3(-2, 0, 0), Vector3(-2, 0, 10), Vector3(8, 0, 20)),
        ),
        RoutePreview(
            UUID(int=813),
            "Right",
            (Vector3(2, 0, 0), Vector3(2, 0, 10), Vector3(12, 0, 20)),
        ),
    )

    conditioned = condition_control_points(
        routes,
        (UUID(int=814), UUID(int=815)),
        (2.0, 2.0),
        ((None, control_id, None),) * 2,
        ((TransitionLengths(),) * 3,) * 2,
        {control_id: _guide(Vector3(0, 0, 10), 10.0)},
        0.5,
    )

    before = magnitude(difference(routes[1].points[1], routes[0].points[1]))
    after = magnitude(difference(conditioned[1].points[1], conditioned[0].points[1]))
    assert after == pytest.approx(before)
    assert conditioned[0].points[1].x == pytest.approx(3.0)
    assert conditioned[1].points[1].x == pytest.approx(7.0)
    assert all(
        magnitude(difference(route.points[1], Vector3(0, 0, 10))) <= 9.0 for route in conditioned
    )


def test_parallel_same_side_junction_retains_each_incident_span() -> None:
    """
    Preserve each leg's own magnitude and guide-facing direction on the same side.
    """
    junction_id = UUID(int=300)
    routes = (
        RoutePreview(UUID(int=4), "First", (Vector3(0, 0, 0), Vector3(10, 0, 0))),
        RoutePreview(UUID(int=5), "Second", (Vector3(0, 0, 0), Vector3(20, 0, 0))),
    )

    targets = junction_tangent_targets(
        routes,
        (UUID(int=400),) * 2,
        ((junction_id, None),) * 2,
        frozenset({junction_id}),
    )

    assert targets == ({0: Vector3(10, 0, 0)}, {0: Vector3(20, 0, 0)})


def test_coincident_neighbor_defers_to_route_validation() -> None:
    """
    Avoid introducing a division failure before fairing reports a coincident span.
    """
    route = RoutePreview(
        UUID(int=6),
        "Coincident",
        (Vector3(0, 0, 0), Vector3(0, 0, 0), Vector3(0, 0, 10)),
    )
    normals = (Vector3(0, 0, 1),) * 3

    conditioned = condition_route_normals(
        route,
        normals,
        (TransitionLengths(),) * 3,
        frozenset({1}),
        {},
        0.5,
    )

    assert conditioned == normals
