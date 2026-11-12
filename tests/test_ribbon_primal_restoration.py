"""
Verify explicit feasible-primal restoration through unchanged geometric and descent gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_terminal_hardware import redistributed_projection as projection
from experiments.experiment_ribbon_terminal_hardware.native_slots import NativeSlots
from experiments.experiment_ribbon_terminal_hardware.primal_projection import Result, Stop


@dataclass(frozen=True)
class _Box(projection.CoordinateBounds):
    """
    Bound the independent analytical geometry coordinate independently of numerical residual variables.
    """

    high: float = 1.0

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Keep the geometry in its original unit interval.
        """
        if index != 0:
            raise IndexError("The analytical box has one geometry coordinate")
        return 0.0, self.high


def _terms(x: float) -> tuple[float, ...]:
    """
    Define a nonlinear cap/guidance problem whose fully compliant solution is x1.
    """
    return (1.0 - x,) + (0.0,) * 5 + (0.1 + x - 2 * x * x,)


def _merit(terms: tuple[float, ...]) -> float:
    """
    Measure cap magnitudes and positive guidance violations with the original maximum norm.
    """
    return max(abs(t) if i < 6 else max(0.0, t) for i, t in enumerate(terms))


def test_one_primal_policy_reaches_known_nonlinear_solution_without_dual_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Every accepted update must decrease actual nonlinear merit within the unchanged four-trial rule.
    """
    dual = Mock(side_effect=AssertionError("No second projection"))
    monkeypatch.setitem(vars(projection), "active_step", dual)
    x = 0.0
    evidence = projection.ProjectionEvidence()
    for _ in range(24):
        residual = _terms(x)
        if _merit(residual) < 1e-13:
            break
        rows = [[-1.0]] + [[0.0] for _ in range(5)] + [[1 - 4 * x]]
        step = projection.redistributed_step(
            _Box(),
            (x,),
            rows,
            residual,
            lambda: None,
            evidence=evidence,
            guidance_policy=projection.GuidancePolicy.RESTORATION_MERIT,
            linear_policy=projection.LinearPolicy.FEASIBLE_PRIMAL,
        )
        assert step is not None
        for halving in range(4):
            candidate = x + step[0] * 0.5**halving
            if _merit(_terms(candidate)) < _merit(residual):
                assert 0 <= candidate <= 1
                x = candidate
                break
        else:
            raise AssertionError("No actual nonlinear descent")
    assert x == 1.0 and _terms(x)[-1] < 0
    assert evidence.primal_attempts == evidence.primal_completed == evidence.primal_proposals
    assert evidence.primal_updates <= 16 * evidence.primal_completed
    dual.assert_not_called()


@pytest.mark.parametrize("touching", (False, True))
def test_incomplete_prefix_still_obeys_original_predicted_gates(
    monkeypatch: pytest.MonkeyPatch, touching: bool
) -> None:
    """
    A retained linear prefix gets no exemption for a satisfied physical inequality.
    """
    result = Result((0.5,) + (0.0,) * 7, Stop.UPDATE_LIMIT, 16)
    offered = Mock(return_value=result)
    dual = Mock(side_effect=AssertionError("No fallback"))
    monkeypatch.setitem(vars(projection), "primal_project", offered)
    monkeypatch.setitem(vars(projection), "active_step", dual)
    rows = [[-1.0]] + [[0.0] for _ in range(5)] + [[1.0]]
    residual = (1.0,) + (0.0,) * 5 + (0.1,)
    if touching:
        rows.append([1.0])
        residual += (0.0,)
    evidence = projection.ProjectionEvidence()
    step = projection.redistributed_step(
        _Box(),
        (0.0,),
        rows,
        residual,
        lambda: None,
        evidence=evidence,
        guidance_policy=projection.GuidancePolicy.RESTORATION_MERIT,
        linear_policy=projection.LinearPolicy.FEASIBLE_PRIMAL,
    )
    assert (step is None) is touching
    assert evidence.primal_prefixes == evidence.primal_attempts == evidence.primal_completed == 1
    assert evidence.primal_updates == 16 and evidence.primal_proposals == int(not touching)
    offered.assert_called_once()
    dual.assert_not_called()


def test_invalid_policy_and_cancellation_cannot_launch_another_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Require restoration semantics and propagate interrupted work instead of offering a stale incumbent.
    """
    rows = [[-1.0]] + [[0.0] for _ in range(6)]
    residual = (1.0,) + (0.0,) * 5 + (-1.0,)
    with pytest.raises(ValueError, match="restoration guidance"):
        projection.redistributed_step(
            _Box(),
            (0.0,),
            rows,
            residual,
            lambda: None,
            linear_policy=projection.LinearPolicy.FEASIBLE_PRIMAL,
        )
    cancelled = Mock(side_effect=TimeoutError("caller clock"))
    dual = Mock(side_effect=AssertionError("No fallback"))
    monkeypatch.setitem(vars(projection), "primal_project", cancelled)
    monkeypatch.setitem(vars(projection), "active_step", dual)
    evidence = projection.ProjectionEvidence()
    with pytest.raises(TimeoutError, match="caller clock"):
        projection.redistributed_step(
            _Box(),
            (0.0,),
            rows,
            residual,
            lambda: None,
            evidence=evidence,
            guidance_policy=projection.GuidancePolicy.RESTORATION_MERIT,
            linear_policy=projection.LinearPolicy.FEASIBLE_PRIMAL,
        )
    assert (
        evidence.primal_attempts == 1
        and evidence.primal_completed == evidence.primal_updates == evidence.primal_proposals == 0
    )
    dual.assert_not_called()


@pytest.mark.parametrize("scale", (1e-6, 1.0, 1e6))
@pytest.mark.parametrize("guidance", ((-0.1, 0.3), (0.0, 0.3), (0.2, 0.3)))
def test_coupled_policy_selects_one_optimizer_from_violated_rows_before_execution(
    monkeypatch: pytest.MonkeyPatch, scale: float, guidance: tuple[float, float]
) -> None:
    """
    Choose by actual guidance coupling, preserving the same decision under numerical scaling.
    """
    dual = Mock(return_value=None)
    primal = Mock(return_value=Result(None, Stop.INVALID_ANCHOR))
    monkeypatch.setitem(vars(projection), "active_step", dual)
    monkeypatch.setitem(vars(projection), "primal_project", primal)
    rows = [[-scale]] + [[0.0] for _ in range(5)] + [[-scale], [-2 * scale]]
    residual = (scale,) + (0.0,) * 5 + tuple(scale * value for value in guidance)
    evidence = projection.ProjectionEvidence()
    assert (
        projection.redistributed_step(
            _Box(),
            (0.0,),
            rows,
            residual,
            lambda: None,
            evidence=evidence,
            guidance_policy=projection.GuidancePolicy.RESTORATION_MERIT,
            linear_policy=projection.LinearPolicy.COUPLED_RESTORATION,
        )
        is None
    )
    coupled = guidance[0] > 0
    assert primal.call_count == evidence.primal_attempts == int(coupled)
    assert dual.call_count == int(not coupled) and primal.call_count + dual.call_count == 1


@pytest.mark.parametrize("current", (-0.01, 1.01))
def test_coupled_restoration_selects_dual_before_an_excluded_anchor(
    monkeypatch: pytest.MonkeyPatch, current: float
) -> None:
    """
    A new lower or upper face cannot supply the zero-motion anchor required by primal optimization.
    """
    dual = Mock(return_value=None)
    primal = Mock(side_effect=AssertionError("Excluded zero-motion anchor"))
    monkeypatch.setitem(vars(projection), "active_step", dual)
    monkeypatch.setitem(vars(projection), "primal_project", primal)
    evidence = projection.ProjectionEvidence()
    step = projection.redistributed_step(
        _Box(),
        (current,),
        [[-1.0]] + [[0.0] for _ in range(5)] + [[-1.0], [-2.0]],
        (1.0,) + (0.0,) * 5 + (0.2, 0.3),
        lambda: None,
        evidence=evidence,
        guidance_policy=projection.GuidancePolicy.RESTORATION_MERIT,
        linear_policy=projection.LinearPolicy.COUPLED_RESTORATION,
    )
    assert step is None and evidence.primal_attempts == 0
    dual.assert_called_once()
    primal.assert_not_called()


@pytest.mark.parametrize("floor", (1e-5, 0.1, 0.8))
def test_new_native_positive_floor_can_restore_without_an_invalid_primal_anchor(
    monkeypatch: pytest.MonkeyPatch, floor: float
) -> None:
    """
    Newly required positive material stays representable while one actual dual projection reduces merit.
    """
    bounds = NativeSlots(_Box(), frozenset({0}), frozenset(), floor)
    rows = [[-1.0]] + [[0.0] for _ in range(5)] + [[-1.0], [-2.0]]
    residual = (1.0,) + (0.0,) * 5 + (0.2, 0.3)
    explicit_evidence = projection.ProjectionEvidence()
    assert (
        projection.redistributed_step(
            bounds,
            (0.0,),
            rows,
            residual,
            lambda: None,
            evidence=explicit_evidence,
            guidance_policy=projection.GuidancePolicy.RESTORATION_MERIT,
            linear_policy=projection.LinearPolicy.FEASIBLE_PRIMAL,
        )
        is None
    )
    assert explicit_evidence.primal_stops == {"invalid_anchor": 1}
    primal = Mock(side_effect=AssertionError("No primal attempt or fallback"))
    monkeypatch.setitem(vars(projection), "primal_project", primal)
    evidence = projection.ProjectionEvidence()
    step = projection.redistributed_step(
        bounds,
        (0.0,),
        rows,
        residual,
        lambda: None,
        evidence=evidence,
        guidance_policy=projection.GuidancePolicy.RESTORATION_MERIT,
        linear_policy=projection.LinearPolicy.COUPLED_RESTORATION,
    )
    assert step is not None and floor <= step[0] <= 1.0
    predicted = tuple(term + row[0] * step[0] for row, term in zip(rows, residual))
    assert projection.strict_descent(
        residual, predicted, projection.GuidancePolicy.RESTORATION_MERIT
    )
    assert evidence.primal_attempts == 0
    primal.assert_not_called()


def test_coupled_domain_check_propagates_cancellation_before_optimizer_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Interrupted eligibility work cannot launch either optimizer or become an ordinary decline.
    """
    primal = Mock(side_effect=AssertionError("No optimizer after cancellation"))
    dual = Mock(side_effect=AssertionError("No optimizer after cancellation"))
    monkeypatch.setitem(vars(projection), "primal_project", primal)
    monkeypatch.setitem(vars(projection), "active_step", dual)
    checkpoint = Mock(side_effect=TimeoutError("domain review cancelled"))
    with pytest.raises(TimeoutError, match="domain review cancelled"):
        projection.redistributed_step(
            _Box(),
            (0.0,),
            [[-1.0]] + [[0.0] for _ in range(5)] + [[-1.0], [-2.0]],
            (1.0,) + (0.0,) * 5 + (0.2, 0.3),
            checkpoint,
            guidance_policy=projection.GuidancePolicy.RESTORATION_MERIT,
            linear_policy=projection.LinearPolicy.COUPLED_RESTORATION,
        )
    checkpoint.assert_called_once()
    primal.assert_not_called()
    dual.assert_not_called()
