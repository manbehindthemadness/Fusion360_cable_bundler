"""
Check contour extrema and helix parallel transport against independent constructions.
"""

import math

import pytest

from cable_bundler.routing.geometry import Vector3, cross, dot, magnitude, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact_inverse import profile_height
from experiments.experiment_ribbon_fold_route.solver import construct_candidate
from experiments.experiment_ribbon_fold_route.sweep_profile import joined_profile_arcs
from experiments.experiment_ribbon_fold_route.sweep_transport import (
    ProfileArc,
    inspect_sweep,
    maximum_support,
    rotate,
)
from tests.test_fold_route import CASES


@pytest.mark.parametrize("phase", [-8.0, -1.2, 0.0, 1.4, 8.0])
def test_full_profile_circle_support_uses_actual_direction(phase: float) -> None:
    """
    Recover translated-circle support without an enclosing profile disk.
    """
    arc = ProfileArc((2, -0.3), 0.75, -math.pi, math.pi)
    value, direction, point = maximum_support((arc,), phase, phase)
    assert value == pytest.approx(2 * math.cos(phase) - 0.3 * math.sin(phase) + 0.75)
    assert point[0] * math.cos(direction) + point[1] * math.sin(direction) == pytest.approx(value)


@pytest.mark.parametrize("low,high", [(-0.1, 0.2), (1.1, 2.7), (5.0, 7.2), (-5.0, 5.0)])
def test_continuous_support_bounds_dense_independent_point_sampling(
    low: float, high: float
) -> None:
    """
    Include interior extrema and wrapped intervals, not just contour vertices.
    """
    arc = ProfileArc((1.65, 0.0), 0.75, -0.6435011087932844, 0.6435011087932844)
    value, _, _ = maximum_support((arc,), low, high)
    sampled = max(
        point[0] * math.cos(direction) + point[1] * math.sin(direction)
        for i in range(201)
        for point in (arc.point(arc.low + (arc.high - arc.low) * i / 200),)
        for j in range(201)
        for direction in (low + (high - low) * j / 200,)
    )
    assert value >= sampled - 1e-12
    assert value - sampled < 0.001


@pytest.mark.parametrize("reverse", [False, True])
def test_exact_helix_transport_matches_incremental_minimum_rotations(reverse: bool) -> None:
    """
    Verify the spin cancellation sign in both directions across a spatial route.
    """
    route = construct_candidate(CASES[0])
    arc = ProfileArc((0, 0), 0.75, -math.pi, math.pi)
    _, exact = inspect_sweep(route, (arc,), reverse=reverse)
    width = route.targets.end_width if reverse else route.targets.start_width
    pieces = list(route.pieces)
    if reverse:
        pieces.reverse()
    for placed in pieces:
        if not isinstance(placed.geometry, CylindricalFold):
            continue
        low, high = placed.geometry.bend_interval(0)
        begin, end = (high, low) if reverse else (low, high)
        sign = -1 if reverse else 1
        previous = unit(placed.surface(begin, 0)[1])
        previous = Vector3(sign * previous.x, sign * previous.y, sign * previous.z)
        for index in range(1, 2049):
            tangent = unit(placed.surface(begin + (end - begin) * index / 2048, 0)[1])
            tangent = Vector3(sign * tangent.x, sign * tangent.y, sign * tangent.z)
            axis = cross(previous, tangent)
            if magnitude(axis) > 1e-14:
                width = rotate(
                    width, unit(axis), math.atan2(magnitude(axis), dot(previous, tangent))
                )
            previous = tangent
    assert magnitude(Vector3(exact.x - width.x, exact.y - width.y, exact.z - width.z)) < 2e-6


@pytest.mark.parametrize("lines", [1, 3, 6])
@pytest.mark.parametrize("diameter", [0.75, 1.5, 3.0])
def test_profile_arcs_match_the_independent_joined_contour_height(
    lines: int, diameter: float
) -> None:
    """
    Vary thickness/count while preserving the contour already used for contact.
    """
    arcs = joined_profile_arcs(lines, diameter)
    assert len(arcs) == 2 * lines + 2
    for arc in arcs:
        for index in range(17):
            q, height = arc.point(arc.low + (arc.high - arc.low) * index / 16)
            assert abs(height) == pytest.approx(
                profile_height(q, lines, diameter), abs=2e-7 * diameter
            )
