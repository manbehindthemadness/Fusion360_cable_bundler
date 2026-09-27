"""
Tests for deterministic parallel-cable route previews.
"""

from __future__ import annotations

import math
from uuid import UUID

import pytest

from cable_bundler.routing import (
    CableRouteInput,
    GateCapacityError,
    GateCapacityPolicy,
    GateFrame,
    RefineFrame,
    Vector3,
    place_route_crossings,
    solve_parallel_routes,
)
from cable_bundler.routing.aperture import contains_disk, interior_center


def _cable(index: int, diameter_mm: float = 1.5) -> CableRouteInput:
    """
    Create one deterministic routing input.
    """
    return CableRouteInput(
        cable_id=UUID(f"10000000-0000-0000-0000-{index:012d}"),
        cable_number=f"{index:03d}",
        start=Vector3(float(index), 0.0, 0.0),
        end=Vector3(float(index), 0.0, 30.0),
        diameter_mm=diameter_mm,
    )


def _gate(index: int, radius_mm: float = 8.0) -> GateFrame:
    """
    Create one XY-plane routing gate.
    """
    return GateFrame(
        gate_id=UUID(f"20000000-0000-0000-0000-{index:012d}"),
        name=f"Gate {index}",
        origin=Vector3(0.0, 0.0, float(index * 10)),
        u_direction=Vector3(1.0, 0.0, 0.0),
        v_direction=Vector3(0.0, 1.0, 0.0),
        usable_radius_mm=radius_mm,
    )


def test_preserves_cable_and_gate_order_in_preview() -> None:
    """
    Keep endpoint pairing and corresponding packed slots stable through every gate.
    """
    cables = tuple(_cable(index) for index in range(1, 4))
    gates = (_gate(1), _gate(2))

    routes = solve_parallel_routes(cables, gates)

    assert [route.cable_id for route in routes] == [cable.cable_id for cable in cables]
    assert all(len(route.points) == 4 for route in routes)
    assert [route.points[0] for route in routes] == [cable.start for cable in cables]
    assert [route.points[-1] for route in routes] == [cable.end for cable in cables]
    for cable_index in range(len(cables)):
        first_offset = routes[cable_index].points[1]
        second_offset = routes[cable_index].points[2]
        assert first_offset.x == pytest.approx(second_offset.x)
        assert first_offset.y == pytest.approx(second_offset.y)


def test_places_network_crossings_without_synthesizing_complete_routes() -> None:
    """
    Expose the same deterministic packing for junction-centered network legs.
    """
    cables = tuple(_cable(index) for index in range(1, 4))
    gate = _gate(1)

    crossings = place_route_crossings(cables, gate)
    routes = solve_parallel_routes(cables, (gate,))

    assert crossings == tuple(route.points[1] for route in routes)


def test_assigns_lanes_toward_prior_world_space_crossings() -> None:
    """
    Transport bundle layout between differently oriented guide frames without swaps.
    """
    cables = tuple(_cable(index) for index in range(1, 4))
    first = _gate(1)
    second = GateFrame(
        _gate(2).gate_id,
        "Rotated Gate",
        _gate(2).origin,
        Vector3(0.0, 1.0, 0.0),
        Vector3(-1.0, 0.0, 0.0),
        8.0,
    )
    prior = place_route_crossings(cables, first)

    transported = place_route_crossings(cables, second, preferred_points=prior)
    unassigned = place_route_crossings(cables, second)

    transported_cost = sum(
        (left.x - right.x) ** 2 + (left.y - right.y) ** 2 for left, right in zip(prior, transported)
    )
    unassigned_cost = sum(
        (left.x - right.x) ** 2 + (left.y - right.y) ** 2 for left, right in zip(prior, unassigned)
    )
    assert transported_cost <= unassigned_cost


def test_refine_preserves_bundle_spacing_without_aperture_constraint() -> None:
    """
    Route every conductor through an oriented refine without capacity rejection.
    """
    cables = tuple(_cable(index, 3.0) for index in range(1, 4))
    refine = RefineFrame(
        UUID("30000000-0000-0000-0000-000000000001"),
        "Refine Point 01",
        Vector3(20.0, 5.0, 15.0),
        Vector3(0.0, 1.0, 0.0),
        Vector3(0.0, 0.0, 1.0),
    )

    routes = solve_parallel_routes(cables, (refine,), clearance_mm=0.5)

    crossings = [route.points[1] for route in routes]
    assert all(point.x == pytest.approx(20.0) for point in crossings)
    for left_index, left in enumerate(crossings):
        for right in crossings[left_index + 1 :]:
            distance = math.sqrt(
                (left.x - right.x) ** 2 + (left.y - right.y) ** 2 + (left.z - right.z) ** 2
            )
            assert distance >= 3.5 - 1e-9


def test_maintains_required_cable_clearance_at_gate() -> None:
    """
    Keep every pair of swept circular envelopes separated at a gate.
    """
    cables = tuple(_cable(index, 2.0) for index in range(1, 8))
    clearance_mm = 0.5

    routes = solve_parallel_routes(cables, (_gate(1, 6.0),), clearance_mm)

    crossings = [route.points[1] for route in routes]
    for left_index, left in enumerate(crossings):
        for right in crossings[left_index + 1 :]:
            distance = math.hypot(left.x - right.x, left.y - right.y)
            assert distance >= 2.0 + clearance_mm - 1e-9


def test_reports_gate_that_cannot_fit_bundle() -> None:
    """
    Stop before generating a preview when a gate aperture is undersized.
    """
    gate = _gate(4, 1.0)

    with pytest.raises(GateCapacityError, match="Gate 4 cannot fit 3 cables") as error_info:
        solve_parallel_routes(tuple(_cable(index, 1.5) for index in range(1, 4)), (gate,))

    assert error_info.value.gate_id == gate.gate_id


def test_can_preserve_spacing_outside_an_undersized_gate() -> None:
    """
    Produce deterministic crossings when a caller explicitly permits overflow.
    """
    cables = tuple(_cable(index, 3.0) for index in range(1, 4))
    gate = _gate(5, 2.98176)

    crossings = place_route_crossings(
        cables,
        gate,
        capacity_policy=GateCapacityPolicy.ALLOW_OVERFLOW,
    )

    assert len(crossings) == 3
    assert any(math.hypot(point.x, point.y) + 1.5 > gate.usable_radius_mm for point in crossings)
    for left_index, left in enumerate(crossings):
        for right in crossings[left_index + 1 :]:
            assert math.hypot(left.x - right.x, left.y - right.y) >= 3.0 - 1e-9


def test_centers_partial_hex_ring_for_exact_two_cable_fit() -> None:
    """
    Fit two equal cables across the full aperture diameter without wasting a center slot.
    """
    cables = (_cable(1, 3.0), _cable(2, 3.0))

    routes = solve_parallel_routes(cables, (_gate(1, 3.0),))

    crossings = [route.points[1] for route in routes]
    assert math.hypot(crossings[0].x, crossings[0].y) == pytest.approx(1.5)
    assert math.hypot(crossings[1].x, crossings[1].y) == pytest.approx(1.5)
    assert math.hypot(
        crossings[0].x - crossings[1].x,
        crossings[0].y - crossings[1].y,
    ) == pytest.approx(3.0)

    with pytest.raises(GateCapacityError):
        solve_parallel_routes(cables, (_gate(1, 2.99),))


def test_square_gate_uses_its_planar_boundary_and_preserves_spacing() -> None:
    """
    Place a bundle in a square profile without requiring a circular sketch edge.
    """
    outline = (((-4.0, -4.0), (4.0, -4.0), (4.0, 4.0), (-4.0, 4.0)),)
    gate = GateFrame(
        _gate(1).gate_id,
        "Square Gate",
        _gate(1).origin,
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
        None,
        outline,
    )
    cables = tuple(_cable(index, 2.0) for index in range(1, 5))

    crossings = place_route_crossings(cables, gate, clearance_mm=0.5)

    assert all(contains_disk((point.x, point.y), 1.0, outline) for point in crossings)
    for index, first in enumerate(crossings):
        for second in crossings[index + 1 :]:
            assert math.hypot(first.x - second.x, first.y - second.y) >= 2.5 - 1e-9


def test_nonconvex_gate_and_hole_use_filled_profile_interior() -> None:
    """
    Keep a gate origin and cable center out of both the exterior and a hole.
    """
    outline = (
        ((-6.0, -6.0), (6.0, -6.0), (6.0, 6.0), (-6.0, 6.0)),
        ((-2.0, -2.0), (2.0, -2.0), (2.0, 2.0), (-2.0, 2.0)),
    )
    center_u, center_v = interior_center(outline)
    assert contains_disk((center_u, center_v), 0.5, outline)
    assert not contains_disk((0.0, 0.0), 0.5, outline)


def test_small_square_gate_rejects_or_warns_under_the_existing_capacity_policy() -> None:
    """
    Apply strict capacity to the actual square while retaining overflow preview.
    """
    outline = (((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)),)
    gate = GateFrame(
        _gate(1).gate_id,
        "Small Square",
        _gate(1).origin,
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
        None,
        outline,
    )
    cables = (_cable(1, 3.0),)

    with pytest.raises(GateCapacityError, match="planar profile"):
        place_route_crossings(cables, gate)
    assert (
        len(
            place_route_crossings(
                cables,
                gate,
                capacity_policy=GateCapacityPolicy.ALLOW_OVERFLOW,
            )
        )
        == 1
    )


@pytest.mark.parametrize(
    ("gates", "clearance", "message"),
    [
        ((), 0.0, "routing gate"),
        ((_gate(1),), -0.1, "non-negative"),
    ],
)
def test_rejects_invalid_solver_inputs(
    gates: tuple[GateFrame, ...],
    clearance: float,
    message: str,
) -> None:
    """
    Reject incomplete or physically invalid routing inputs.
    """
    with pytest.raises(ValueError, match=message):
        solve_parallel_routes((_cable(1),), gates, clearance)


def test_end_stacks_guide_path_between_terminals_and_pathway() -> None:
    """
    Follow both local end stacks outward from their terminals, reversing B in traversal.
    """
    cable = CableRouteInput(
        UUID(int=1),
        "001",
        Vector3(0, 0, 0),
        Vector3(0, 0, 40),
        1.5,
        start_guides=(Vector3(1, 0, 2), Vector3(2, 0, 4)),
        end_guides=(Vector3(1, 0, 38), Vector3(2, 0, 36)),
    )
    route = solve_parallel_routes((cable,), (_gate(1), _gate(2)))[0]
    assert route.points == (
        cable.start,
        *cable.start_guides,
        _gate(1).origin,
        _gate(2).origin,
        *reversed(cable.end_guides),
        cable.end,
    )


def test_end_order_is_not_inferred_from_distance_to_pathway() -> None:
    """
    Keep deliberately non-monotonic stack order even when the terminal is nearest the gate.
    """
    cable = CableRouteInput(
        UUID(int=1),
        "001",
        Vector3(0, 0, 9),
        Vector3(0, 0, 11),
        1.5,
        start_guides=(Vector3(0, 0, 1), Vector3(0, 0, 5)),
        end_guides=(Vector3(0, 0, 19), Vector3(0, 0, 15)),
    )
    route = solve_parallel_routes((cable,), (_gate(1),))[0]
    assert [point.z for point in route.points] == [9, 1, 5, 10, 15, 19, 11]
