"""
Bind initializer reclosure precision to its actual terminal-proof contract without renewing work.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

import experiments.experiment_ribbon_feature_insertion.solve as runner
from experiments.experiment_ribbon_feature_insertion.allocation import Allocation
from experiments.experiment_ribbon_feature_insertion.closure_goal import ClosureGoal
from experiments.experiment_ribbon_feature_insertion.features import Chain
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.repair import Closure
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize("hardware", (False, True))
def test_initializer_requests_required_precision_inside_original_two_steps(
    monkeypatch: pytest.MonkeyPatch, hardware: bool
) -> None:
    """
    Exercise actual constructor selection and proof boundaries with explicit fit/reclosure doubles.
    """
    route = _route((Straight(10),))
    boundary = Boundary(route.targets, 1)
    frames = Frames.create(route.targets)
    chain = Chain(Topology("authored", (), None), (), (), 1, (0,))
    original = Closure((10,), (6e-10, 0, 0), 6e-10)
    allocated = Allocation(route, chain, (10,), 0, 1)
    monkeypatch.setitem(vars(runner), "chains", Mock(return_value=(chain,)))
    monkeypatch.setitem(vars(runner), "fit", Mock(return_value=None))
    monkeypatch.setitem(vars(runner), "nearest", Mock(return_value=original))
    correction = Mock(return_value=allocated)
    monkeypatch.setitem(vars(runner), "refine", correction)
    measured = ContactResult("separated", 3)
    contact = Mock(return_value=measured)
    monkeypatch.setitem(vars(runner), "inspect_contact", contact)
    terminal = Mock(spec=Gate, measure=Mock(return_value=Report("clear", 2))) if hardware else None
    result = runner.construct(
        boundary,
        frames,
        (0.5,),
        1e-5,
        lambda: None,
        Mock(),
        maximum_straight_mm=20,
        terminal=terminal,
    )
    assert result.route is route and result.contact is measured
    correction.assert_called_once()
    pending = correction.call_args.args[1]
    assert pending.goal is (ClosureGoal.MATING if hardware else ClosureGoal.ROUTE)
    assert pending.chain is chain and pending.closure is original and pending.iteration == 0
    assert correction.call_args.args[3] == 2
    assert correction.call_args.kwargs["maximum_straight_mm"] == 20
    contact.assert_called_once()
    assert result.contact_pairs == 3
    if terminal is not None:
        terminal.measure.assert_called_once_with(route, "construction_before_contact")
