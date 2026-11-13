"""
Select coupled escape geometry from the existing root pool without changing closure or acceptance.
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_feature_insertion.allocation import Allocation
from experiments.experiment_ribbon_feature_insertion.features import Chain
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_joint_route.frames import Topology
from experiments.experiment_ribbon_terminal_hardware import adaptive_event_construction as runner
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_plan import RootPreference
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_window import Window
from tests.test_ribbon_adaptive_events import _bump, _proposal
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize(
    "preference,spent,expected_calls,expected_root",
    (
        (RootPreference.FIRST_CLOSED, 0, 1, 0),
        (RootPreference.GUIDE_FIT, 0, 3, 2),
        (RootPreference.GUIDE_FIT, 6, 2, 1),
    ),
)
def test_guide_quality_can_choose_a_longer_closed_escape_without_renewing_choices(
    monkeypatch: pytest.MonkeyPatch,
    preference: RootPreference,
    spent: int,
    expected_calls: int,
    expected_root: int,
) -> None:
    """
    Real isometric cap-closed alternatives isolate typed selection from the explicit fit boundary.
    """
    source = _route((Straight(20),))
    window = Window(source, 0, 1)
    proposal = replace(_proposal(window), root_preference=preference)
    routes = tuple(_bump(window, angle) for angle in (0.15, 0.3, 0.5))
    assert routes[2].material_length_mm > routes[0].material_length_mm
    choices = tuple(
        Chain(
            Topology(
                str(i),
                tuple(p.geometry for p in route.pieces if isinstance(p.geometry, CylindricalFold)),
                None,
            ),
            (),
            (),
            1,
            (i,),
        )
        for i, route in enumerate(routes)
    )
    allocations = tuple(
        Allocation(route, chain, (), score, 1)
        for route, chain, score in zip(routes, choices, (20.0, 5.0, 1.0))
    )
    monkeypatch.setitem(vars(runner), "chains", Mock(return_value=choices))
    fit = Mock(side_effect=allocations)
    monkeypatch.setitem(vars(runner), "fit", fit)
    reclose = Mock(side_effect=AssertionError("A closed choice needs no second optimizer"))
    monkeypatch.setitem(vars(runner), "close", reclose)
    roots = runner.Roots(attempted=spent, declined=spent)
    result = runner.construct(proposal, 1e-5, roots, lambda: None, Mock())
    assert result is not None
    assert result is routes[expected_root]
    assert routes[expected_root].targets == source.targets
    assert roots.attempted == spent + expected_calls and roots.declined == spent
    assert roots.newton_steps == roots.reclosures == 0
    assert fit.call_count == expected_calls
    assert all(
        call.kwargs["maximum_straight_mm"] == proposal.frames.guide.distances[-1]
        for call in fit.call_args_list
    )
    reclose.assert_not_called()
