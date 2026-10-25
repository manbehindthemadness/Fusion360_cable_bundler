"""
Check displacement-guided frame choice and the direct travel projection.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from experiments.experiment_ribbon_cap_transition.chord_coupled import (
    construct,
    schedule,
    travel_lengths,
)
from experiments.experiment_ribbon_cap_transition.coupled_motion import ZERO
from experiments.experiment_ribbon_cap_transition.coupled_route import CoupledRejection
from experiments.experiment_ribbon_cap_transition.coupled_route import (
    construct as original_construct,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase, endpoint_cases
from experiments.experiment_ribbon_cap_transition.endpoint_reference import reference_cases

X, Y, Z = Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)


def test_direct_projection_closes_position_with_redundant_travel_freedoms() -> None:
    """
    Identical coordinate columns share travel equally under the minimum-change rule.
    """
    columns = (X, X, Y, Y, Z, Z)
    lengths = travel_lengths(columns, Vector3(10, 12, 14))
    assert lengths == pytest.approx((5, 5, 6, 6, 7, 7))
    endpoint = ZERO
    for column, length in zip(columns, lengths):
        endpoint = endpoint.translated(column, length)
    assert magnitude(difference(endpoint, Vector3(10, 12, 14))) < 1e-10


@pytest.mark.parametrize(
    ("columns", "chord", "reason"),
    (((X, X, X), Vector3(10, 1, 0), "singular"), ((X, Y, Z), Vector3(-10, 2, 3), "nonpositive")),
)
def test_projection_does_not_clip_or_retry_impossible_lengths(
    columns: tuple[Vector3, ...], chord: Vector3, reason: str
) -> None:
    """
    A deficient basis or reverse travel rejects the sole algebraic result.
    """
    with pytest.raises(CoupledRejection, match=reason):
        travel_lengths(columns, chord)


def test_middle_frame_responds_to_position_with_endpoint_orientations_unchanged() -> None:
    """
    Moving the endpoint changes the schedule before the position-length solve.
    """
    case = EndpointCase("schedule-contract", ZERO, Vector3(40, 50, 15), X, Y, Y, Z)
    moved = replace(case, end=Vector3(60, 20, -10))
    first, second = schedule(case), schedule(moved)
    assert len(first) == len(second) == 7
    assert magnitude(difference(first[3].tangent, unit(case.end))) < 1e-10
    assert magnitude(difference(second[3].tangent, unit(moved.end))) < 1e-10
    assert magnitude(difference(first[3].tangent, second[3].tangent)) > 0.1
    for motions in (first, second):
        for a, b in zip(motions, motions[1:]):
            tangent, width = a.frame(1)
            assert magnitude(difference(tangent, b.tangent)) < 1e-8
            assert magnitude(difference(width, b.width)) < 1e-8
        tangent, width = motions[-1].frame(1)
        assert magnitude(difference(tangent, Y)) < 1e-8
        assert magnitude(difference(width, Z)) < 1e-8
        for motion in motions:
            assert abs(dot(motion.axis, cross(motion.tangent, motion.width))) < 1e-10
            assert motion.angle_jet(0)[1:] == motion.angle_jet(1)[1:] == (0, 0)


@pytest.mark.parametrize("case", (endpoint_cases()[0], reference_cases()[0]))
def test_analytic_controls_are_preserved_exactly(case: EndpointCase) -> None:
    """
    Straight and compatible circular paths retain the previous complete motion data.
    """
    assert construct(case) == original_construct(case)


def test_travel_projection_is_covariant_under_rigid_rotation() -> None:
    """
    World coordinate choice cannot alter the direct segment lengths.
    """
    from experiments.experiment_ribbon_cap_transition.coupled_motion import rotate

    axis = unit(Vector3(1, -2, 3))
    columns, chord = (X, X, Y, Y, Z, Z), Vector3(10, 12, 14)
    expected = travel_lengths(columns, chord)
    rotated = travel_lengths(
        tuple(rotate(p, axis, 0.73) for p in columns), rotate(chord, axis, 0.73)
    )
    assert rotated == pytest.approx(expected, abs=1e-10)
