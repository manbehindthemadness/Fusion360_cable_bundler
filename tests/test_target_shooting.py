"""
Check joint endpoint residuals and bounded algebra independently of Fusion.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude
from experiments.experiment_ribbon_cap_transition import target_shooting
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_cap_transition.material_ablation import minimum_travel
from experiments.experiment_ribbon_cap_transition.material_policy import (
    minimum_travel as original_floors,
)

# noinspection PyProtectedMember
from experiments.experiment_ribbon_cap_transition.target_shooting import _bounded, _solve, evaluate


def _case() -> EndpointCase:
    """
    Supply a synthetic fixed boundary pose for residual-contract checks.
    """
    return EndpointCase(
        "synthetic_shooting",
        Vector3(0, 0, 0),
        Vector3(90, 20, 10),
        Vector3(1, 0, 0),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 0, 1),
    )


def test_position_and_ordered_frame_are_both_in_residual() -> None:
    """
    Expose position and frame misses while retaining material-compatible motion.
    """
    case = _case()
    values = (0.6, -0.8, 0.5, 0.4, -0.6, 0.3) + (0.1,) * 7
    shot = evaluate(case, values)
    tangent, width = shot.plan.motions[-1].frame(1)
    assert len(shot.residual) == 9
    assert shot.residual[3:6] == pytest.approx((tangent.x - 1, tangent.y, tangent.z))
    assert shot.residual[6:] == pytest.approx((width.x, width.y, width.z - 1))
    assert not shot.plan.connected
    assert shot.plan.endpoint_gap_mm > 0
    for span in shot.plan.strip.spans:
        assert span.minimum_jacobian(shot.plan.strip.half_width_mm) > 0
        assert (
            abs(
                dot(
                    span.motion.axis,
                    Vector3(
                        span.motion.tangent.y * span.motion.width.z
                        - span.motion.tangent.z * span.motion.width.y,
                        span.motion.tangent.z * span.motion.width.x
                        - span.motion.tangent.x * span.motion.width.z,
                        span.motion.tangent.x * span.motion.width.y
                        - span.motion.tangent.y * span.motion.width.x,
                    ),
                )
            )
            < 1e-12
        )
    altered = evaluate(case, (0.7,) + values[1:])
    assert (
        magnitude(difference(shot.plan.motions[-1].jet(1)[0], altered.plan.motions[-1].jet(1)[0]))
        > 0.1
    )


def test_damped_system_solves_coupled_coordinates() -> None:
    """
    Verify pivoting against a known coupled system and reject singular input.
    """
    assert _solve([[0, 2], [1, 3]], [4, 7]) == pytest.approx([1, 2])
    with pytest.raises(ValueError, match="singular"):
        _solve([[0, 0], [0, 0]], [1, 1])


def test_search_bounds_preserve_signed_angles_and_positive_surplus() -> None:
    """
    Enforce declared parameter bounds without altering external endpoint data.
    """
    assert (
        _bounded((9, -9, 0, 8, -8, 1) + (-1,) * 7)
        == (
            math.pi,
            -math.pi,
            0,
            4,
            -4,
            1,
        )
        + (0,) * 7
    )
    with pytest.raises(ValueError, match="thirteen finite"):
        evaluate(_case(), (0,) * 12 + (math.nan,))


@pytest.mark.parametrize("policy", [None, minimum_travel])
def test_joint_rounds_retain_improvement_and_count_every_probe(
    monkeypatch: pytest.MonkeyPatch,
    policy: target_shooting.TravelPolicy | None,
) -> None:
    """
    Exercise the update loop with an external residual contract and fixed plan.

    A constant residual component prevents false closure. Every trial/probe is
    counted and accepted error cannot increase,even after the variable settles.
    """
    case = _case()
    plan = evaluate(case, (0.6, -0.8, 0.5, 0.4, -0.6, 0.3) + (0.1,) * 7).plan
    calls = []

    def observed(
        fixture: EndpointCase,
        coordinates: tuple[float, ...],
        *,
        travel_policy: target_shooting.TravelPolicy | None = None,
    ) -> target_shooting.Shot:
        """
        Substitute a deterministic residual without running a geometry search.
        """
        assert fixture == case
        assert travel_policy is policy
        calls.append(coordinates)
        return target_shooting.Shot(plan, (coordinates[0] - 0.1, 1.0) + (0.0,) * 7)

    monkeypatch.setattr(target_shooting, "evaluate", observed)
    result, counters = target_shooting.construct(case, travel_policy=policy)
    history = counters["error_history"]
    assert isinstance(history, list)
    assert history[-1] < history[0]
    assert all(right <= left for left, right in zip(history, history[1:]))
    evaluations = counters["evaluations"]
    assert isinstance(evaluations, int)
    assert len(calls) == evaluations <= target_shooting.MAX_EVALUATIONS
    assert result.updates == target_shooting.MAX_UPDATES


def test_ablation_removes_only_added_turn_floor_and_retains_default() -> None:
    """
    Keep legacy/default equality while isolating the surface-width restriction.

    Check retained transition floors and center curvature on synthetic parameters;
    this evaluates a contract,not complete-ribbon solver performance.
    """
    case = _case()
    values = (0.6, -0.8, 0.5, 1.4, -1.6, 1.3) + (0.1,) * 7
    default = evaluate(case, values)
    explicit = evaluate(case, values, travel_policy=original_floors)
    changed = evaluate(case, values, travel_policy=minimum_travel)
    assert default == explicit
    before, after = default.plan.lower_bounds_mm, changed.plan.lower_bounds_mm
    assert all(a <= b for a, b in zip(after, before))
    assert any(a < b for a, b in zip(after, before))
    assert after[::2] == before[::2]
    reach = math.hypot(changed.plan.strip.half_width_mm, case.diameter_mm / 2)
    assert max(m.maximum_curvature() for m in changed.plan.motions) * reach <= 0.8
    assert (
        min(s.minimum_jacobian(changed.plan.strip.half_width_mm) for s in changed.plan.strip.spans)
        > 0
    )
