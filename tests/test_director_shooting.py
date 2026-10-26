"""
Check endpoint-first director routing contracts without touching reserved witnesses.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_ribbon_cap_transition.director_fields import rejection_controls
from experiments.experiment_ribbon_cap_transition.director_rotation_transport import (
    integrate_rotation,
)
from experiments.experiment_ribbon_cap_transition.director_route_objective import (
    free_penalties,
    regular_penalties,
)
from experiments.experiment_ribbon_cap_transition.director_seed_bank import NoAdmissibleSeed
from experiments.experiment_ribbon_cap_transition.director_shooting import (
    BANK,
    BANK_PERSISTENT,
    BANK_WIDTH,
    BASELINE,
    CORKSCREW,
    FREE,
    REGULAR,
    ROTATION,
    ShootingPolicy,
    bounded,
    field_for,
    maximum_length_ratio,
    seed,
    solve,
)
from experiments.experiment_ribbon_cap_transition.director_transport import DirectorPath
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase


def _checkpoint() -> None:
    """
    Leave live resource sampling to the registered experiment runner.
    """


def _case(z: float = 0.0) -> EndpointCase:
    """
    Freeze a planar control whose endpoints are independent of a generated path.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    return EndpointCase(
        "synthetic_endpoint", Vector3(-40, 0, -z / 2), Vector3(40, 0, z / 2), x, x, y, y
    )


@pytest.mark.parametrize("z", [0.0, 12.0, -18.0])
@pytest.mark.parametrize(
    "policy", [BASELINE, ROTATION, REGULAR, CORKSCREW, FREE, BANK, BANK_PERSISTENT, BANK_WIDTH]
)
def test_cold_start_reaches_fixed_planar_targets_without_snapping(
    z: float, policy: ShootingPolicy
) -> None:
    """
    Require strict actual A-edge closure and monotone stages on unrelated offsets.
    """
    case = _case(z)
    path, metrics = solve(case, _checkpoint, policy=policy)
    assert metrics["endpoint_gate_passed"]
    assert metrics["evaluations"] <= 2 + 12 * (policy.coarse_rounds + policy.final_rounds)
    assert magnitude(difference(path.lane(1, 0)[0], case.end)) < 1e-8
    for stage in metrics["stages"]:
        assert all(b <= a for a, b in zip(stage["history"], stage["history"][1:]))


def test_seed_depends_on_geometry_not_case_identity() -> None:
    """
    Prevent hidden per-fixture lookup paths from supplying a routing solution.
    """
    original = _case(12)
    renamed = replace(original, name="unseen_label")
    assert seed(original) == seed(renamed)


def test_extra_harmonic_preserves_caps_and_analytic_ruling_derivative() -> None:
    """
    Verify the new independent coefficient before any solver outcome is examined.
    """
    field = field_for(_case(), (1.0, -0.3, 0.4, 0.2, -0.2, 0.4, -0.3, 0.2, 0.5, 1.3))
    assert abs(field.sample(0)[1]) < 1e-12 and abs(field.sample(1)[1]) < 1e-12
    u, step = 0.371, 1e-6
    numerical = (field.sample(u + step)[1] - field.sample(u - step)[1]) / (
        2 * step * field.length_mm
    )
    assert field.sample(u)[2] == pytest.approx(numerical, rel=1e-8)


def test_search_bounds_reject_nonfinite_and_do_not_move_endpoint_inputs() -> None:
    """
    Keep bounds on solver freedom,not on user geometry or acceptance tolerances.
    """
    values = bounded((100.0,) * 10)
    assert values[:5] == (4 * math.pi,) * 5
    assert values[5:9] == (3.0,) * 4 and values[9] == 5
    with pytest.raises(ValueError):
        bounded((float("nan"),) * 10)


def test_width_domain_does_not_exclude_turn_length_because_chord_is_short() -> None:
    """
    Preserve historical caps while allowing a distinct width-aware search domain.
    """
    case = replace(_case(), end=Vector3(-34, 0, 0))
    bound = maximum_length_ratio(case, BANK_WIDTH)
    assert bound > 5
    assert maximum_length_ratio(case, BANK) == 5
    values = (1.0,) + (0.0,) * 8 + (6.0,)
    with pytest.raises(ValueError, match="search bounds"):
        field_for(case, values, policy=BANK)
    assert field_for(case, values, policy=BANK_WIDTH).length_mm == 36
    assert bounded(values)[-1] == 5
    assert bounded(values, maximum_ratio=bound)[-1] == 6
    scaled = replace(case, start=Vector3(-80, 0, 0), end=Vector3(-68, 0, 0), diameter_mm=3)
    assert maximum_length_ratio(scaled, BANK_WIDTH) == pytest.approx(bound)


def test_regular_chart_bounds_full_width_jacobian_before_integration() -> None:
    """
    Check extreme raw ruling coordinates without accepting a clipped bad shape.
    """
    for scale in (1.0, 2.0, 5.0):
        field = field_for(
            _case(), (2.0, 1.0, -1.0, 0.5, 0.0, 3.0, -3.0, 3.0, -3.0, scale), policy=REGULAR
        )
        for i in range(1025):
            assert 1 - field.half_width_mm * abs(field.sample(i / 1024)[2]) > 0.1


def test_free_surrogate_penalizes_folding_while_regular_chart_rejects_it() -> None:
    """
    Separate optimizer freedom from the final geometry rejection contract.
    """
    path = integrate_rotation(rejection_controls()[0], 64, _checkpoint)
    penalties = free_penalties(_case(), path)
    assert all(math.isfinite(value) for value in penalties)
    assert max(penalties) > 0
    with pytest.raises(ValueError, match="Jacobian bound"):
        regular_penalties(_case(), path)


def test_stage_observer_preserves_solver_result() -> None:
    """
    Expose accepted coarse/fine paths without changing coordinates or evaluations.
    """
    observed: list[tuple[int, DirectorPath]] = []

    def capture(grid: int, path: DirectorPath) -> None:
        """
        Retain immutable paths for phase-by-phase geometry diagnosis.
        """
        observed.append((grid, path))

    plain, before = solve(_case(12), _checkpoint, policy=BANK)
    traced, after = solve(_case(12), _checkpoint, policy=BANK, stage_observer=capture)
    assert traced == plain == observed[-1][1]
    assert [grid for grid, _ in observed] == [64, 512]
    assert before["coordinates"] == after["coordinates"]
    assert before["evaluations"] == after["evaluations"]


def test_admissibility_failure_is_bounded_initialization_exhaustion() -> None:
    """
    Refuse an inadmissible initial state instead of refining or returning it.
    """

    def reject(path: DirectorPath) -> bool:
        """
        Reject every initial path independently of its endpoint residual.
        """
        assert len(path.states) == 65
        return False

    with pytest.raises(NoAdmissibleSeed, match="Initial stage64"):
        solve(_case(), _checkpoint, policy=BANK_PERSISTENT, admissibility=reject)


def test_admissible_control_keeps_identical_fit_and_accepted_stages() -> None:
    """
    Preserve a regular feasible control without spending additional fit evaluations.
    """
    observed: list[DirectorPath] = []

    def regular(path: DirectorPath) -> bool:
        """
        Check actual full-width intrinsic regularity independently of the objective.
        """
        return all(
            1 - path.field.half_width_mm * abs(path.field.sample(i / 128)[2]) > 0
            for i in range(129)
        )

    def capture(grid: int, path: DirectorPath) -> None:
        """
        Require every reported accepted stage to obey the filter.
        """
        assert len(path.states) == grid + 1 and regular(path)
        observed.append(path)

    plain, before = solve(_case(12), _checkpoint, policy=BANK_PERSISTENT)
    guarded, after = solve(
        _case(12),
        _checkpoint,
        policy=BANK_PERSISTENT,
        stage_observer=capture,
        admissibility=regular,
    )
    assert guarded == plain == observed[-1]
    assert before["evaluations"] == after["evaluations"]
    assert after["endpoint_gate_passed"]


def test_inadmissible_endpoint_improvements_are_not_accepted() -> None:
    """
    Keep a length-constrained initial route when unconstrained endpoint fit shortens it.
    """
    case = _case(12)
    minimum_length = field_for(case, seed(case), policy=BANK_PERSISTENT).length_mm
    rejected: list[DirectorPath] = []

    def length_domain(path: DirectorPath) -> bool:
        """
        Use a simple independent search domain to expose rejected downhill steps.
        """
        accepted = path.field.length_mm >= minimum_length
        if not accepted:
            rejected.append(path)
        return accepted

    plain, _ = solve(case, _checkpoint, policy=BANK_PERSISTENT)
    guarded, metrics = solve(case, _checkpoint, policy=BANK_PERSISTENT, admissibility=length_domain)
    assert plain.field.length_mm < minimum_length
    assert rejected
    assert guarded.field.length_mm >= minimum_length
    assert not metrics["endpoint_gate_passed"]
    assert metrics["evaluations"] <= 254


def test_persistent_policy_does_not_stop_at_closure_with_geometry_penalty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Prevent a closed endpoint from hiding a remaining fine-stage geometry residual.
    """

    def residual_penalty(case: EndpointCase, path: DirectorPath) -> tuple[float, ...]:
        """
        Keep a nonzero policy residual independent of endpoint closure.
        """
        assert case.lines == path.field.lines
        return (0.1,)

    monkeypatch.setattr(
        "experiments.experiment_ribbon_cap_transition.director_shooting.free_penalties",
        residual_penalty,
    )
    _, historical = solve(_case(), _checkpoint, policy=BANK)
    _, retained = solve(_case(), _checkpoint, policy=BANK_PERSISTENT)
    assert historical["stages"][-1]["history"] == [0.0]
    assert len(retained["stages"][-1]["history"]) == 4
    assert retained["stages"][-1]["history"] == pytest.approx([0.01] * 4)
    assert retained["evaluations"] > historical["evaluations"]
    assert retained["endpoint_gate_passed"]
