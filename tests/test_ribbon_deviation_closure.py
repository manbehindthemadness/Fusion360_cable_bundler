"""
Bound one closest-topology deviation closure without treating linear progress as clearance.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_feature_insertion.allocation import Allocation
from experiments.experiment_ribbon_feature_insertion.closure_goal import ClosureGoal
from experiments.experiment_ribbon_feature_insertion.continuation import BranchPolicy
from experiments.experiment_ribbon_feature_insertion.features import Chain, chains
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.reclosure import Unclosed
from experiments.experiment_ribbon_feature_insertion.repair import Closure
from experiments.experiment_ribbon_feature_insertion.repair import nearest as original_nearest
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_terminal_hardware import deviation_closure
from tests.test_ribbon_feature_insertion import _targets


@pytest.fixture
def original() -> tuple[Boundary, tuple[Chain, ...]]:
    """
    Supply two already derived analytical topologies independently of historical layouts.
    """
    frames = Frames.create(_targets())
    boundary = Boundary(frames.targets, 0.101)
    return boundary, chains(boundary, frames, (0.3, 0.7), lambda: None, lambda e: None)[:2]


@pytest.mark.parametrize("outcome", ("stalled", "unfinished", "closed"))
def test_only_one_closest_original_topology_receives_four_bounded_corrections(
    original: tuple[Boundary, tuple[Chain, ...]], outcome: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Never select another guide/root after failure; propagate the original straight and factor policies.
    """
    boundary, attempted = original
    assert len(attempted) == 2
    closures = tuple(
        Closure((0.0,) * (2 * len(chain.topology.folds) + 1), (error, 0, 0), error)
        for chain, error in zip(attempted, (1.0, 0.2))
    )
    measure = Mock(side_effect=closures)
    monkeypatch.setitem(vars(deviation_closure), "nearest", measure)
    accepted = Mock(spec=Allocation)
    result = (
        None
        if outcome == "stalled"
        else Unclosed(attempted[1], closures[1])
        if outcome == "unfinished"
        else accepted
    )
    action = Mock(return_value=result)
    monkeypatch.setitem(vars(deviation_closure), "refine", action)
    records: list[dict[str, object]] = []
    measured = deviation_closure.close(
        boundary, attempted, 1e-5, 25.0, lambda: None, records.append
    )
    assert measured is (accepted if outcome == "closed" else None)
    action.assert_called_once()
    selected = action.call_args.args[1]
    assert selected.chain is attempted[1] and selected.closure is closures[1]
    assert selected.branch_policy is BranchPolicy.CONTINUOUS
    assert selected.goal is ClosureGoal.MATING
    assert action.call_args.args[3] == 4 and action.call_args.kwargs["maximum_straight_mm"] == 25.0
    assert measure.call_count == 2
    snapshots = [event for event in records if event["stage"] == "spatial_deviation_unclosed"]
    assert len(snapshots) == (1 if outcome == "unfinished" else 0)
    if snapshots:
        assert snapshots[0]["route"] and snapshots[0]["position_error_diameters"] == 0.2
    assert all(call.kwargs["maximum_straight_mm"] == 25.0 for call in measure.call_args_list)


def test_closed_endpoint_with_failed_allocation_cannot_bypass_other_contracts(
    original: tuple[Boundary, tuple[Chain, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Decline closure work when the positional equation already passes but another allocation guard failed.
    """
    boundary, attempted = original
    monkeypatch.setitem(
        vars(deviation_closure), "nearest", Mock(return_value=Closure((), (0, 0, 0), 0.0))
    )
    action = Mock(side_effect=AssertionError("Already closed endpoint"))
    monkeypatch.setitem(vars(deviation_closure), "refine", action)
    assert (
        deviation_closure.close(boundary, attempted, 1e-5, 25.0, lambda: None, lambda e: None)
        is None
    )
    action.assert_not_called()


def test_original_cancellation_stops_before_preparation_or_alternative_actions(
    original: tuple[Boundary, tuple[Chain, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Preserve the caller's resource/source stop rather than relabelling it unresolved closure.
    """
    measure = Mock()
    monkeypatch.setitem(vars(deviation_closure), "nearest", measure)
    boundary, attempted = original
    with pytest.raises(TimeoutError, match="original limit"):
        deviation_closure.close(
            boundary,
            attempted,
            1e-5,
            25.0,
            Mock(side_effect=TimeoutError("original limit")),
            lambda e: None,
        )
    measure.assert_not_called()


@pytest.mark.parametrize("scale", (0.1, 1.0, 20.0))
@pytest.mark.parametrize("fraction", (0.4, 1.0))
def test_relaxed_bounds_preserve_the_actual_nearest_root_and_coordinates(
    scale: float, fraction: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Compare native-sized ranking to exhaustive preparation on independently authored material chains.
    """
    frames = Frames.create(_targets(scale))
    boundary = Boundary(frames.targets, 0.101 * scale)
    attempted = chains(boundary, frames, (0.3, 0.7), lambda: None, lambda e: None)
    budget = frames.guide.distances[-1] * fraction
    selected = Mock(return_value=None)
    measure = Mock(wraps=original_nearest)
    monkeypatch.setitem(vars(deviation_closure), "nearest", measure)
    monkeypatch.setitem(vars(deviation_closure), "refine", selected)
    records: list[dict[str, object]] = []
    deviation_closure.close(boundary, attempted, 1e-5 * scale, budget, lambda: None, records.append)
    bounded = selected.call_args.args[1] if selected.called else None
    bounded_calls = measure.call_count
    selected.reset_mock()
    measure.reset_mock()
    monkeypatch.setitem(vars(deviation_closure), "separate", lambda *_: None)
    deviation_closure.close(boundary, attempted, 1e-5 * scale, budget, lambda: None, lambda e: None)
    exhaustive = selected.call_args.args[1] if selected.called else None
    assert bounded == exhaustive
    skipped = sum(e["status"] == "dominated_endpoint_projection" for e in records)
    assert bounded_calls + skipped == measure.call_count
    assert skipped > 0
