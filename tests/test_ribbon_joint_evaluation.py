"""
Keep exact constrained-joint reuse model-owned, bounded and explicitly invalidated.
"""

from __future__ import annotations

import math

import pytest

from experiments.experiment_ribbon_terminal_hardware.joint_evaluation import JointEvaluation


def test_constraint_changes_replace_equations_without_forgetting_the_fixed_domain() -> None:
    """
    A newly measured bound changes row count at identical coordinates while domain evidence remains valid.
    """
    state: list[float] = [2.0]
    equation_calls: list[tuple[float, ...]] = []
    domain_calls: list[tuple[float, ...]] = []

    def equations(values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Model raw equations whose explicit constraint state can change.
        """
        equation_calls.append(values)
        return values + tuple(state)

    def admissible(values: tuple[float, ...]) -> bool:
        """
        Retain a fixed material-domain decision independent of active constraints.
        """
        domain_calls.append(values)
        return values[0] >= 0

    evaluation = JointEvaluation(equations, admissible)
    point = (1.0,)
    assert evaluation.equations(point) == evaluation.equations(point) == (1.0, 2.0)
    assert evaluation.admissible(point) and evaluation.admissible(point)
    state.append(3.0)
    evaluation.constraints_changed()
    assert evaluation.equations(point) == (1.0, 2.0, 3.0)
    assert evaluation.admissible(point)
    assert equation_calls == [point, point] and domain_calls == [point]


def test_nearby_coordinates_and_distinct_models_never_share_a_cached_decision() -> None:
    """
    Do not round finite-difference probes or transfer another model's feasibility result.
    """
    first = JointEvaluation(lambda v: v, lambda v: v[0] <= 1.0)
    second = JointEvaluation(lambda v: tuple(-x for x in v), lambda v: v[0] > 1.0)
    a, b = (1.0,), (math.nextafter(1.0, math.inf),)
    assert first.equations(a) == a and first.equations(b) == b
    assert first.admissible(a) and not first.admissible(b)
    assert second.equations(a) == (-1.0,) and not second.admissible(a)
    for i in range(70):
        assert first.equations((float(i),)) == (float(i),)
    assert first.equations(a) == a and first.admissible(a)


def test_joint_callback_errors_propagate_without_becoming_reusable_evidence() -> None:
    """
    A failed measurement is never converted into cached numerical or domain success.
    """
    attempts = 0

    def equations(values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Demonstrate an external hard failure followed by actual successful evidence.
        """
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("source failure")
        return values

    evaluation = JointEvaluation(equations, lambda v: True)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="source failure"):
            evaluation.equations((1.0,))
    assert evaluation.equations((1.0,)) == evaluation.equations((1.0,)) == (1.0,)
    assert attempts == 3
