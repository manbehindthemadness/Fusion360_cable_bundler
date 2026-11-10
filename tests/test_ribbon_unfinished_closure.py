"""
Retain measured unfinished progress and its physical-factor policy without renewing work.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_feature_insertion import reclosure
from experiments.experiment_ribbon_feature_insertion.allocation import Allocation
from experiments.experiment_ribbon_feature_insertion.continuation import BranchPolicy
from experiments.experiment_ribbon_feature_insertion.features import chains
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.repair import Closure, StraightMotion, nearest
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from tests.test_ribbon_feature_insertion import _targets


@pytest.fixture
def pending() -> tuple[Boundary, reclosure.Unclosed]:
    """
    Supply an analytical feature chain independent of any saved gym configuration.
    """
    frames = Frames.create(_targets())
    boundary = Boundary(frames.targets, 0.101)
    chain = chains(boundary, frames, (0.5,), lambda: None, lambda e: None)[0]
    state = reclosure.Unclosed(chain, nearest(Model(boundary, chain.topology), lambda: None))
    return boundary, state


@pytest.mark.parametrize(
    "legacy_error,continuous_error", ((1.0, 0.2), (1.0, 2.0), (1.0, 1.0), (None, 0.2))
)
def test_already_computed_unfinished_states_keep_the_lower_actual_residual(
    pending: tuple[Boundary, reclosure.Unclosed],
    legacy_error: float | None,
    continuous_error: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Retain the better progressing state, preserving legacy ties and the same two original actions.
    """
    boundary, source = pending
    legacy = (
        None
        if legacy_error is None
        else replace(source, closure=replace(source.closure, error=legacy_error), iteration=2)
    )
    continuous = replace(
        source,
        closure=replace(source.closure, error=continuous_error),
        iteration=2,
        branch_policy=BranchPolicy.CONTINUOUS,
    )
    action = Mock(side_effect=(legacy, continuous))
    monkeypatch.setitem(vars(reclosure), "refine", action)
    events: list[dict[str, Any]] = []
    result = reclosure.refine_preserving_legacy(
        boundary, source, 1e-5, 2, lambda: None, events.append, maximum_straight_mm=20.0
    )
    expected = continuous if legacy_error is None or continuous_error < legacy_error else legacy
    assert result is expected
    assert action.call_count == 2
    assert all(
        call.args[3] == 2 and call.kwargs["maximum_straight_mm"] == 20.0
        for call in action.call_args_list
    )


@pytest.mark.parametrize("override", (None, BranchPolicy.INDEX))
@pytest.mark.parametrize("maximum_steps", (1, 4))
def test_actual_refinement_resumes_and_retains_the_recorded_factor_policy(
    pending: tuple[Boundary, reclosure.Unclosed],
    override: BranchPolicy | None,
    maximum_steps: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Propagate recorded or explicitly overridden policy through derivatives, reframe and retained progress.
    """
    boundary, source = pending
    source = replace(source, iteration=2, branch_policy=BranchPolicy.CONTINUOUS)
    correction = Mock(return_value=(0.0, 0.0, 0.0))
    reframed = Mock(return_value=source.chain)
    trials = [
        replace(source.closure, error=source.closure.error / 2 ** (i + 1))
        for i in range(maximum_steps)
    ]
    monkeypatch.setitem(vars(reclosure), "correction", correction)
    monkeypatch.setitem(vars(reclosure), "reframed", reframed)
    monkeypatch.setitem(vars(reclosure), "nearest", Mock(side_effect=trials))
    result = reclosure.refine(
        boundary,
        source,
        1e-5,
        maximum_steps,
        lambda: None,
        lambda e: None,
        branch_policy=override,
        maximum_straight_mm=20.0,
    )
    chosen = source.branch_policy if override is None else override
    assert isinstance(result, reclosure.Unclosed)
    assert result.branch_policy is chosen and result.iteration == 2 + maximum_steps
    assert result.chain is source.chain and result.closure is trials[-1]
    assert correction.call_count == reframed.call_count == maximum_steps
    assert all(call.kwargs["branch_policy"] is chosen for call in reframed.call_args_list)
    assert all(
        call.kwargs["branch_policy"] is chosen and call.kwargs["maximum_straight_mm"] == 20.0
        for call in correction.call_args_list
    )


def test_resumed_progress_gets_one_action_and_hard_errors_do_not_start_an_alternative(
    pending: tuple[Boundary, reclosure.Unclosed], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Preserve the consumed iteration and original continuation allowance without a second policy attempt.
    """
    boundary, source = pending
    source = replace(source, iteration=2, branch_policy=BranchPolicy.CONTINUOUS)
    progressed = replace(source, iteration=6)
    action = Mock(return_value=progressed)
    monkeypatch.setitem(vars(reclosure), "refine", action)
    assert (
        reclosure.refine_preserving_legacy(boundary, source, 1e-5, 4, lambda: None, lambda e: None)
        is progressed
    )
    action.assert_called_once()
    assert action.call_args.args[1] is source and action.call_args.args[3] == 4
    action.reset_mock()
    action.side_effect = TimeoutError("original limit")
    with pytest.raises(TimeoutError, match="original limit"):
        reclosure.refine_preserving_legacy(boundary, source, 1e-5, 4, lambda: None, lambda e: None)
    action.assert_called_once()


@pytest.mark.parametrize("resumed", (False, True))
def test_legal_straight_transfers_are_available_before_the_first_possible_stall(
    pending: tuple[Boundary, reclosure.Unclosed],
    monkeypatch: pytest.MonkeyPatch,
    resumed: bool,
) -> None:
    """
    An initially stalled continuation cannot defer its useful coordinate policy to an unreachable step.

    Mock the nonlinear boundary, with fixed-straight corrections unable to reduce
    the projected residual and transfer-aware corrections making progress. The
    separate analytical endpoint-map tests verify that linear projection itself.
    """
    boundary, original = pending
    source = replace(original, iteration=2 if resumed else 0)
    policies: list[StraightMotion] = []

    def correction(*args: Any, straight_motion: StraightMotion, **kwargs: Any) -> list[float]:
        """
        Observe each scheduled direction without creating another correction allowance.
        """
        del args, kwargs
        policies.append(straight_motion)
        return [0.0, 0.0, 0.0]

    def projected_trial(*args: Any, **kwargs: Any) -> Closure:
        """
        Model actual reallocation progress only when the direction accounted for that freedom.
        """
        del args, kwargs
        factor = 0.5 ** len(policies) if policies[-1] is StraightMotion.REALLOCATABLE else 2.0
        return replace(source.closure, error=source.closure.error * factor)

    monkeypatch.setitem(vars(reclosure), "correction", correction)
    monkeypatch.setitem(vars(reclosure), "reframed", Mock(return_value=source.chain))
    monkeypatch.setitem(vars(reclosure), "nearest", projected_trial)
    result = reclosure.refine(boundary, source, 1e-5, 4, lambda: None, lambda event: None)
    if resumed:
        assert isinstance(result, reclosure.Unclosed)
        assert result.iteration == 6 and result.closure.error == source.closure.error / 16
        assert policies == [StraightMotion.REALLOCATABLE] * 4
    else:
        assert result is None and policies == [StraightMotion.FIXED]


@pytest.mark.parametrize("outcome", ("stable", "partial", "worse_site", "longer", "better"))
def test_closed_legacy_replacement_keeps_its_original_rules(
    pending: tuple[Boundary, reclosure.Unclosed],
    outcome: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Mock closed allocation boundaries to verify progress ranking cannot displace an accepted legacy route.
    """
    boundary, source = pending
    legacy = Mock(spec=Allocation)
    legacy.chain = replace(source.chain, factor_discontinuity=outcome != "stable")
    legacy.score = 1.0
    legacy.route = Mock(material_length_mm=10.0)
    continuous = Mock(spec=Allocation)
    continuous.chain = source.chain
    continuous.score = 2.0 if outcome == "worse_site" else 0.5
    continuous.route = Mock(material_length_mm=11.0 if outcome == "longer" else 9.0)
    alternative = source if outcome == "partial" else continuous
    action = Mock(side_effect=(legacy, alternative))
    monkeypatch.setitem(vars(reclosure), "refine", action)
    result = reclosure.refine_preserving_legacy(
        boundary, source, 1e-5, 2, lambda: None, lambda e: None
    )
    assert result is (continuous if outcome == "better" else legacy)
    assert action.call_count == (1 if outcome == "stable" else 2)
