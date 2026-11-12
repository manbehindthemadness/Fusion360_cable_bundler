"""
Use one already attempted root for bounded measured closure without renewing guide masks or work.
"""

from __future__ import annotations

from typing import Any, Callable
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_feature_insertion import reclosure
from experiments.experiment_ribbon_feature_insertion.allocation import Allocation, fit
from experiments.experiment_ribbon_feature_insertion.deviation_guide import DeviationGuide
from experiments.experiment_ribbon_feature_insertion.features import Chain, chains
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.reclosure import ReclosureAllocation, Unclosed
from experiments.experiment_ribbon_feature_insertion.repair import Closure, nearest
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_terminal_hardware import (
    adaptive_event_construction as construction,
)
from experiments.experiment_ribbon_terminal_hardware import deviation_closure
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_plan import Proposal
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_window import Window
from tests.test_ribbon_adaptive_events import _proposal
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_feature_insertion import _targets


@pytest.fixture
def straight_system() -> tuple[Proposal, Allocation]:
    """
    Supply a real exact allocation for protocol boundaries independently of saved layouts.
    """
    proposal = _proposal(Window(_route((Straight(20),)), 0, 1))
    boundary = Boundary(proposal.window.route.targets, proposal.window.source.radius_mm)
    allocated = None
    for parameters in ((0.5,), DeviationGuide.stations()):
        choices = chains(boundary, proposal.frames, parameters, lambda: None, lambda e: None)
        for chain in choices:
            allocated = fit(
                boundary,
                chain,
                1e-5,
                lambda: None,
                lambda e: None,
                maximum_straight_mm=proposal.frames.guide.distances[-1],
            )
            if allocated is not None:
                break
        if allocated is not None:
            break
    assert allocated is not None
    return proposal, allocated


def test_real_angle_reclosure_uses_native_cone_coordinates_without_guide_mask_renewal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Close one authored spatial frame family using actual derivatives, factors, native lengths and caps.
    """
    frames = Frames.create(_targets())
    boundary = Boundary(frames.targets, 0.101)
    chain = next(
        c
        for c in chains(boundary, frames, (0.5,), lambda: None, lambda e: None)
        if c.roots == (0, 1)
    )
    initial = nearest(
        Model(boundary, chain.topology),
        lambda: None,
        maximum_straight_mm=20,
        minimum_straight_mm=1e-5,
    )
    assert initial.error > 1e-3
    guide_fit = Mock(side_effect=AssertionError("No renewed guide masks"))
    monkeypatch.setitem(vars(reclosure), "fit", guide_fit)
    events: list[dict[str, Any]] = []
    result = deviation_closure.close(
        boundary,
        (chain,),
        1e-5,
        20,
        lambda: None,
        events.append,
        allocation_policy=ReclosureAllocation.MEASURED,
    )
    assert result is not None and result.chain.roots == chain.roots
    assert cap_error(result.route) < 1e-10 and material_error(result.route) < 1e-10
    assert all(f.radius_mm == boundary.radius_mm for f in result.chain.topology.folds)
    assert all(value == 0 for value in result.values[1::2])
    assert all(
        value == 0 or value * boundary.targets.diameter_mm > 1e-5 for value in result.values[::2]
    )
    started = [e for e in events if e.get("stage") == "feature_reclosure_step"]
    assert 1 <= len(started) <= 4
    assert all(e["allocation_policy"] == "measured_closure" for e in started)
    guide_fit.assert_not_called()


@pytest.fixture
def unfinished_system() -> tuple[Boundary, Unclosed]:
    """
    Supply an authored unfinished state for correction accounting and continuation contracts.
    """
    frames = Frames.create(_targets())
    boundary = Boundary(frames.targets, 0.101)
    chain = chains(boundary, frames, (0.5,), lambda: None, lambda e: None)[0]
    source = Unclosed(
        chain, Closure((), (1, 0, 0), 1), allocation_policy=ReclosureAllocation.MEASURED
    )
    return boundary, source


def test_derivative_failure_is_charged_before_declining_the_same_root(
    unfinished_system: tuple[Boundary, Unclosed],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A correction attempt consumes work even when it cannot produce a direction.
    """
    boundary, source = unfinished_system
    action = Mock(return_value=None)
    monkeypatch.setitem(vars(reclosure), "correction", action)
    events: list[dict[str, Any]] = []
    assert reclosure.refine(boundary, source, 1e-5, 4, lambda: None, events.append) is None
    assert events[0]["stage"] == "feature_reclosure_step" and events[0]["status"] == "started"
    assert len([e for e in events if e.get("stage") == "feature_reclosure_step"]) == 1
    action.assert_called_once()


def test_unfinished_measured_policy_survives_resume_without_becoming_guide_search(
    unfinished_system: tuple[Boundary, Unclosed],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Store the allocation policy with unfinished progress just like its factor and precision policies.
    """
    boundary, source = unfinished_system
    chain = source.chain
    monkeypatch.setitem(vars(reclosure), "correction", Mock(return_value=[0.001, 0, 0]))
    monkeypatch.setitem(vars(reclosure), "reframed", Mock(return_value=chain))
    monkeypatch.setitem(
        vars(reclosure),
        "nearest",
        Mock(side_effect=(Closure((), (0.5, 0, 0), 0.5), Closure((), (0.25, 0, 0), 0.25))),
    )
    events: list[dict[str, Any]] = []
    first = reclosure.refine(boundary, source, 1e-5, 1, lambda: None, events.append)
    assert isinstance(first, Unclosed) and first.allocation_policy is ReclosureAllocation.MEASURED
    second = reclosure.refine(boundary, first, 1e-5, 1, lambda: None, events.append)
    assert isinstance(second, Unclosed) and second.allocation_policy is ReclosureAllocation.MEASURED
    assert [
        e["allocation_policy"] for e in events if e.get("stage") == "feature_reclosure_step"
    ] == ["measured_closure"] * 2


def test_exact_closed_fastpath_never_launches_local_reclosure(
    straight_system: tuple[Proposal, Allocation], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Preserve the existing exact root path and leave its correction pool untouched.
    """
    proposal, allocated = straight_system
    monkeypatch.setitem(vars(construction), "chains", Mock(return_value=(allocated.chain,)))
    monkeypatch.setitem(vars(construction), "fit", Mock(return_value=allocated))
    close = Mock(side_effect=AssertionError("Exact root needs no angle work"))
    monkeypatch.setitem(vars(construction), "close", close)
    work = construction.Roots(newton_limit=0)
    assert construction.construct(proposal, 1e-5, work, lambda: None, Mock()) is allocated.route
    assert work.attempted == 1 and work.newton_steps == work.reclosures == 0
    close.assert_not_called()


def test_local_windows_share_corrections_and_only_actually_attempted_roots(
    straight_system: tuple[Proposal, Allocation], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Drive controlled closure dispositions while preserving real material allocation/cap boundaries.
    """
    proposal, allocated = straight_system
    monkeypatch.setitem(
        vars(construction),
        "chains",
        Mock(side_effect=((allocated.chain,), (), (allocated.chain,), (), (allocated.chain,), ())),
    )
    monkeypatch.setitem(vars(construction), "fit", Mock(return_value=None))
    limits: list[int] = []

    def closed(
        boundary: Boundary,
        attempted: list[Chain],
        minimum: float,
        maximum: float,
        check: Callable[[], None],
        record: Callable[[dict[str, Any]], None],
        *,
        maximum_steps: int,
        allocation_policy: ReclosureAllocation,
    ) -> Allocation | None:
        """
        Report started corrections under the original shared allowance without generating another root.
        """
        del boundary, minimum, maximum, check
        assert attempted == [allocated.chain] and allocation_policy is ReclosureAllocation.MEASURED
        limits.append(maximum_steps)
        for iteration in range(min(2, maximum_steps)):
            record({"stage": "feature_reclosure_step", "status": "started", "iteration": iteration})
        return allocated if len(limits) == 1 else None

    monkeypatch.setitem(vars(construction), "close", closed)
    work = construction.Roots(newton_limit=3)
    assert construction.construct(proposal, 1e-5, work, lambda: None, Mock()) is allocated.route
    assert construction.construct(proposal, 1e-5, work, lambda: None, Mock()) is None
    assert construction.construct(proposal, 1e-5, work, lambda: None, Mock()) is None
    assert limits == [3, 1, 0] and work.newton_steps == 3 and work.attempted == 3
    assert work.declined == 2 and work.reclosures == 3


def test_exhausted_root_pool_cannot_start_a_fresh_closure_family(
    straight_system: tuple[Proposal, Allocation], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    With no newly attempted original root, another call cannot reuse old geometry as a renewed action.
    """
    proposal, _ = straight_system
    close = Mock(side_effect=AssertionError("No original attempted root in this window"))
    monkeypatch.setitem(vars(construction), "close", close)
    work = construction.Roots(8)
    assert construction.construct(proposal, 1e-5, work, lambda: None, Mock()) is None
    assert work.attempted == 8 and work.newton_steps == 0
    close.assert_not_called()
