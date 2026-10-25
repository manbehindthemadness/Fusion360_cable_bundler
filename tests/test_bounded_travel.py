"""
Check bounded travel feasibility, numerical evidence and explicitly unclosed guides.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude, unit
from experiments.experiment_ribbon_cap_transition.bounded_travel import AllocationStatus, allocate
from experiments.experiment_ribbon_cap_transition.chord_coupled import travel_lengths
from experiments.experiment_ribbon_cap_transition.coupled_motion import ZERO, CoupledMotion
from experiments.experiment_ribbon_cap_transition.coupled_route import CoupledRejection
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase, endpoint_cases
from experiments.experiment_ribbon_cap_transition.endpoint_reference import reference_cases
from experiments.experiment_ribbon_cap_transition.radius_allocation import construct, minimum_travel

X, Y, Z = Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)


def test_positive_allocation_exists_despite_negative_unconstrained_projection() -> None:
    """
    Enforcing bounds inside the allocation recovers a previously false-negative type.
    """
    columns = (X, Y, Z, unit(Vector3(1, 1, 1)))
    chord = Vector3(10, 1, 1)
    with pytest.raises(CoupledRejection, match="nonpositive"):
        travel_lengths(columns, chord)
    result = allocate(columns, (0.1,) * 4, chord)
    assert result.status is AllocationStatus.FEASIBLE
    assert result.lengths is not None and min(result.lengths) >= 0.1
    endpoint = ZERO
    for column, length in zip(columns, result.lengths):
        endpoint = endpoint.translated(column, length)
    assert magnitude(difference(endpoint, chord)) < 1e-8
    assert result.checked_bases == 14


def test_lower_bounds_can_separate_a_fixed_family_from_the_target() -> None:
    """
    Required forward projection exceeding the target has an explicit numerical witness.
    """
    result = allocate((X, Y, Z), (2, 3, 4), Vector3(1, 1, 1))
    assert result.status is AllocationStatus.SEPARATED
    assert result.lengths is None
    assert result.separation_margin_mm == pytest.approx(6 / math.sqrt(3))
    assert result.minimum_column_projection == pytest.approx(1 / math.sqrt(3))
    assert result.checked_bases == 0


@pytest.mark.parametrize("columns", ((X,), (X, Y), (X, Y, Z)))
def test_lower_dimensional_supports_are_not_falsely_singular(columns: tuple[Vector3, ...]) -> None:
    """
    Feasible lines and planes need no artificial full-rank three-vector basis.
    """
    chord = ZERO
    for column in columns:
        chord = chord.translated(column, 3)
    result = allocate(columns, (1,) * len(columns), chord)
    assert result.status is AllocationStatus.FEASIBLE
    assert result.lengths == pytest.approx((3,) * len(columns))


def test_exhaustion_is_unresolved_and_work_is_bounded() -> None:
    """
    A missing lateral generator cannot be called certified infeasible by rank skips.
    """
    result = allocate((X,) * 7, (0,) * 7, Y)
    assert result.status is AllocationStatus.UNRESOLVED
    assert result.checked_bases == 63
    assert result.lengths is None


def test_radius_floors_follow_the_analytic_motion_curvature() -> None:
    """
    Required length preserves the existing 0.8 contract with a conservative guard.
    """
    case = endpoint_cases()[0]
    motion = CoupledMotion(ZERO, X, Y, unit(Vector3(1, 1, 0)), 1.2, 1)
    lower = minimum_travel(case, (motion,))[0]
    reach = math.hypot(14.4, 0.75)
    assert motion.maximum_curvature() * reach / lower < 0.8
    assert motion.maximum_curvature() * reach / lower == pytest.approx(0.8)


@pytest.mark.parametrize("case", (endpoint_cases()[0], reference_cases()[0]))
def test_controls_remain_connected(case: EndpointCase) -> None:
    """
    Exact straight and circular controls retain their fixed target closure.
    """
    plan = construct(case)
    assert plan.connected
    assert plan.endpoint_gap_mm < 1e-8
    assert plan.allocation.checked_bases == 0


def test_failed_allocation_retains_an_unclosed_visible_trace_and_fixed_target() -> None:
    """
    A diagnostic path may be displayed but cannot be mistaken for endpoint closure.
    """
    target = Vector3(0.02, 0.03, 0.01)
    case = EndpointCase("synthetic-unclosed-contract", ZERO, target, X, Y, Y, Z)
    plan = construct(case)
    assert not plan.connected
    assert plan.allocation.lengths is None
    assert plan.motions and all(m.length > 0 for m in plan.motions)
    assert plan.endpoint_gap_mm > 1
    assert magnitude(difference(plan.motions[0].start, ZERO)) < 1e-8
    assert case.end == target
