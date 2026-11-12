"""
Exercise deficit-derived construction and its single shared physical-recovery allocation.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude
from experiments.experiment_ribbon_bend_relocation.solve import Result as Recovered
from experiments.experiment_ribbon_feature_insertion.features import Chain
from experiments.experiment_ribbon_feature_insertion.reclosure import Unclosed
from experiments.experiment_ribbon_feature_insertion.repair import Closure
from experiments.experiment_ribbon_feature_insertion.selection import Policy
from experiments.experiment_ribbon_feature_insertion.solve import Result
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology
from experiments.experiment_ribbon_locked_solver import initial_closure as runner
from experiments.experiment_ribbon_terminal_hardware import cone_escape
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.test_ribbon_aesthetic import _route


def _missing_direction() -> tuple[Boundary, Unclosed]:
    """
    Author a small forward-only turn family whose actual target needs backward travel.
    """
    route = _route((fold(1, 1.2, 0.2, 0, 0), fold(1, 1.2, 0.3, 0, 0)))
    topology = Topology("analytical missing ray", tuple(p.geometry for p in route.pieces), None)
    chain = Chain(topology, (1,), (route.pieces[0].end_pose(),), 2, (0, 0))
    deficit = Vector3(-1, 0, 1)
    targets = replace(route.targets, end=route.targets.end.translated(deficit, 1))
    boundary = Boundary(targets, 1)
    residual = (1.0, 0.0, -1.0)
    return boundary, Unclosed(chain, Closure((0.0,) * 5, residual, math.sqrt(2)))


def test_escape_supplies_missing_ray_and_restores_original_steering() -> None:
    """
    A real bank-zero turn opens backward workspace without changing the later factors or frames.
    """
    boundary, pending = _missing_direction()
    escape = cone_escape.plan(boundary, pending, Mock())
    assert escape is not None
    assert escape.prefix.radius_mm == boundary.radius_mm
    assert escape.prefix.width_mm == boundary.half_width_mm * 2
    assert escape.prefix.bank_radians == 0
    assert escape.prefix.before_mm == escape.prefix.after_mm == 0
    assert dot(escape.deficit, escape.tangent) > 0
    original = Model(boundary, pending.chain.topology)
    columns, _ = original.straight_equations()
    assert all(sum(a * b for a, b in zip(column, (-1, 0, 1))) < 0 for column in columns)
    start = original.endpoint((0.0,) * original.size)
    # Use the actual input pose rather than the original family's terminal pose.
    start = replace(
        start,
        origin=boundary.targets.start,
        tangent=boundary.targets.start_tangent,
        width=boundary.targets.start_width,
    )
    turn = PlacedPiece(start, escape.prefix, "escape")
    assert magnitude(difference(turn.end_pose().tangent, escape.tangent)) < 1e-10
    assert 1 <= len(escape.windows) <= 2
    for window in escape.windows:
        assert window.targets == pending.chain.targets
        assert window.roots[1:] == pending.chain.roots[1:]
        assert window.topology.folds[window.group_ends[0] :] == pending.chain.topology.folds[1:]
        pose = turn.end_pose()
        for geometry in window.topology.folds[: window.group_ends[0]]:
            pose = PlacedPiece(pose, geometry, "compensation").end_pose()
        assert magnitude(difference(pose.tangent, window.targets[0].tangent)) < 1e-9
        assert magnitude(difference(pose.width, window.targets[0].width)) < 1e-9


@pytest.mark.parametrize("residual", [(0.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, -1.0, 0.0)])
def test_nonseparating_deficit_does_not_add_a_fold(residual: tuple[float, float, float]) -> None:
    """
    No missing direction is inferred from a nonseparating or width-only deficit.
    """
    boundary, pending = _missing_direction()
    pending = replace(pending, closure=replace(pending.closure, residual=residual))
    assert cone_escape.plan(boundary, pending, Mock()) is None


def _controller() -> tuple[Result, Boundary, FoldRoute, Mock]:
    """
    Supply an actual closed route plus independent unclosed evidence for scheduling tests.
    """
    boundary, pending = _missing_direction()
    route = _route((Straight(20),))
    boundary = Boundary(route.targets, boundary.radius_mm)
    result = Result(
        None, None, "no_fixed_radius_closure", 0, 0, 0, 0, closure_candidates=(pending,)
    )
    terminal = Mock(spec=Gate)
    terminal.hardware = Hardware.create(boundary.targets, Dimensions.scaled(boundary.targets))
    terminal.certify.return_value = Report("clear", 1)
    return result, boundary, route, terminal


@pytest.mark.parametrize(
    "change",
    [
        {"status": "other"},
        {"closed_branches": 1},
        {"closure_candidates": ()},
        {"contact_pairs": 2048},
    ],
)
def test_other_construction_failures_do_not_enter(
    monkeypatch: pytest.MonkeyPatch, change: dict[str, Any]
) -> None:
    """
    Initial closure cannot renew physical recovery or act on another failure class.
    """
    result, boundary, _, terminal = _controller()
    result = replace(result, **change)
    planner = Mock()
    monkeypatch.setitem(vars(runner), "plan", planner)
    updated, detail = runner.recover(
        result, boundary, terminal, 3e-5, 30, Mock(), Mock(), selection_policy=Policy.MONOTONIC
    )
    assert updated is result and detail is None
    planner.assert_not_called()


@pytest.mark.parametrize("policy,hardware", [(Policy.MIDPOINT, True), (Policy.MONOTONIC, False)])
def test_disabled_workflows_do_not_enter(
    monkeypatch: pytest.MonkeyPatch, policy: Policy, hardware: bool
) -> None:
    """
    Ordinary construction and hardware-disabled calls retain their original behavior.
    """
    result, boundary, _, terminal = _controller()
    planner = Mock()
    monkeypatch.setitem(vars(runner), "plan", planner)
    updated, detail = runner.recover(
        result,
        boundary,
        terminal if hardware else None,
        3e-5,
        30,
        Mock(),
        Mock(),
        selection_policy=policy,
    )
    assert updated is result and detail is None
    planner.assert_not_called()


def test_physical_sequence_receives_only_remaining_work(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Closure's update, Newton and initial contact costs reduce the existing sequence allowance.
    """
    result, boundary, route, terminal = _controller()
    initial_contact = ContactResult("unresolved", 70)
    final_contact = ContactResult("separated", 352)
    monkeypatch.setitem(vars(runner), "plan", Mock(return_value=object()))

    def construct(*args: Any) -> FoldRoute:
        """
        Report two actual constructor corrections before returning the physical candidate.
        """
        args[3].newton_steps = 2
        args[3].attempted = 2
        return route

    monkeypatch.setitem(vars(runner), "construct", construct)
    monkeypatch.setitem(vars(runner), "inspect_contact", Mock(return_value=initial_contact))
    sequence = Mock(
        return_value=Recovered(
            route,
            final_contact,
            {
                "iterations": 2,
                "newton_steps": 7,
                "contacts": 1,
                "contact_pairs": 544,
                "contact_seconds": 0.01,
                "stop_reason": "accepted",
            },
        )
    )
    monkeypatch.setitem(vars(runner), "continue_route", sequence)
    updated, detail = runner.recover(
        result, boundary, terminal, 3e-5, 30, Mock(), Mock(), selection_policy=Policy.MONOTONIC
    )
    assert detail is not None
    work = sequence.call_args.kwargs["work"]
    assert isinstance(work, Work)
    assert work.updates == 3 and work.newton_steps == 22 and work.pairs == 1978
    assert 0 < work.cpu_seconds < 0.35 and 0 < work.wall_seconds < 2
    assert sequence.call_args.args[2] is terminal
    assert updated.route is route and updated.contact is final_contact
    assert updated.contact_pairs == detail["pairs"] == 614
    assert detail["iterations"] == 3 and detail["newton_steps"] == 9
    assert updated.closed_branches == 1 and detail["status"] == "separated"
    sequence.assert_called_once()


def test_failed_sequence_retains_candidate_without_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A numerical candidate remains inspectable while unsuccessful physical evidence stays rejected.
    """
    result, boundary, route, terminal = _controller()
    monkeypatch.setitem(vars(runner), "plan", Mock(return_value=object()))
    monkeypatch.setitem(vars(runner), "construct", Mock(return_value=route))
    monkeypatch.setitem(
        vars(runner), "inspect_contact", Mock(return_value=ContactResult("unresolved", 12))
    )
    sequence = Mock(
        return_value=Recovered(
            route,
            None,
            {
                "iterations": 1,
                "newton_steps": 0,
                "contacts": 0,
                "contact_pairs": 0,
                "contact_seconds": 0,
                "stop_reason": "unsupported_guidance",
            },
        )
    )
    monkeypatch.setitem(vars(runner), "continue_route", sequence)
    updated, detail = runner.recover(
        result, boundary, terminal, 3e-5, 30, Mock(), Mock(), selection_policy=Policy.MONOTONIC
    )
    assert updated.route is None and updated.contact is None
    assert updated.inspection_route is route
    assert detail is not None and detail["status"] == "unresolved"
    assert detail["stop_reason"] == "unsupported_guidance"
    sequence.assert_called_once()


def test_interrupted_initial_proof_charges_upper_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A phase interruption cannot claim measured pair exhaustion or start another action.
    """
    result, boundary, route, terminal = _controller()
    clock = [0.0]
    monkeypatch.setitem(vars(runner), "process_time", lambda: clock[0])
    monkeypatch.setitem(vars(runner), "plan", Mock(return_value=object()))
    monkeypatch.setitem(vars(runner), "construct", Mock(return_value=route))

    def interrupted(*args: Any, **kwargs: Any) -> ContactResult:
        """
        Hit the actual parent clock from inside an initial contact check.
        """
        clock[0] = 0.36
        kwargs["checkpoint"]()
        raise AssertionError("Exhausted phase continued")

    monkeypatch.setitem(vars(runner), "inspect_contact", interrupted)
    sequence = Mock()
    monkeypatch.setitem(vars(runner), "continue_route", sequence)
    updated, detail = runner.recover(
        result, boundary, terminal, 3e-5, 30, Mock(), Mock(), selection_policy=Policy.MONOTONIC
    )
    assert updated.route is None and updated.inspection_route is route
    assert detail is not None and detail["stop_reason"] == "phase_budget"
    assert detail["pairs"] == 1024
    assert detail["interrupted_pair_charge"] == "allowance_upper_bound"
    sequence.assert_not_called()


def test_caller_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A caller timeout remains a run failure rather than an ordinary phase decline.
    """
    result, boundary, _, terminal = _controller()
    monkeypatch.setitem(vars(runner), "plan", lambda _b, _s, check: check())
    with pytest.raises(TimeoutError, match="outer"):
        runner.recover(
            result,
            boundary,
            terminal,
            3e-5,
            30,
            Mock(side_effect=TimeoutError("outer")),
            Mock(),
            selection_policy=Policy.MONOTONIC,
        )


def test_constructor_retains_original_missing_ray_without_resampling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep the already computed closure object when all original allocations and corrections decline.
    """
    from experiments.experiment_ribbon_feature_insertion import solve as construction
    from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames

    boundary, pending = _missing_direction()
    frames = Frames.create(boundary.targets)
    measured = Mock(return_value=pending.closure)
    monkeypatch.setitem(vars(construction), "chains", Mock(return_value=(pending.chain,)))
    monkeypatch.setitem(vars(construction), "fit", Mock(return_value=None))
    monkeypatch.setitem(vars(construction), "nearest", measured)
    monkeypatch.setitem(vars(construction), "refine", Mock(return_value=None))
    result = construction.construct(boundary, frames, (0.5,), 3e-5, Mock(), Mock())
    assert result.route is None and result.closed_branches == 0
    assert result.status == "no_fixed_radius_closure"
    assert len(result.closure_candidates) == 1
    assert result.closure_candidates[0].closure is pending.closure
    assert result.closure_candidates[0].chain is pending.chain
    measured.assert_called_once()


def test_escape_has_no_global_six_fold_limit() -> None:
    """
    Additional untouched downstream events do not prevent a geometrically required departure bend.
    """
    boundary, pending = _missing_direction()
    folds = pending.chain.topology.folds + (fold(1, 1.2, -0.01, 0, 0),) * 5
    chain = replace(pending.chain, topology=replace(pending.chain.topology, folds=folds))
    pending = replace(pending, chain=chain, closure=replace(pending.closure, values=(0.0,) * 15))
    escape = cone_escape.plan(boundary, pending, Mock())
    assert escape is not None
    assert all(len(window.topology.folds) + 1 > 6 for window in escape.windows)
    assert all(
        window.topology.folds[window.group_ends[0] :] == folds[1:] for window in escape.windows
    )


def test_already_safe_candidate_needs_no_physical_motion(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Full self-contact separation and exact-route hardware clearance suffice after numerical construction.
    """
    result, boundary, route, terminal = _controller()
    monkeypatch.setitem(vars(runner), "plan", Mock(return_value=object()))
    monkeypatch.setitem(vars(runner), "construct", Mock(return_value=route))
    contact = ContactResult("separated", 40)
    monkeypatch.setitem(vars(runner), "inspect_contact", Mock(return_value=contact))
    sequence = Mock()
    monkeypatch.setitem(vars(runner), "continue_route", sequence)
    updated, detail = runner.recover(
        result, boundary, terminal, 3e-5, 30, Mock(), Mock(), selection_policy=Policy.MONOTONIC
    )
    assert updated.route is route and updated.contact is contact
    assert detail is not None and detail["iterations"] == 1 and detail["pairs"] == 40
    terminal.certify.assert_called_once_with(route, "initial_closure_final")
    sequence.assert_not_called()


def test_constructor_uses_one_closest_window_and_charges_started_corrections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Exact compensation roots share one correction window, original travel ceiling and Newton ledger.
    """
    from experiments.experiment_ribbon_feature_insertion.closure_goal import ClosureGoal
    from experiments.experiment_ribbon_feature_insertion.continuation import BranchPolicy
    from experiments.experiment_ribbon_feature_insertion.reclosure import ReclosureAllocation
    from experiments.experiment_ribbon_terminal_hardware.adaptive_event_construction import Roots

    boundary, pending = _missing_direction()
    escape = cone_escape.plan(boundary, pending, Mock())
    assert escape is not None
    measured: list[Model] = []

    def nearest(model: Model, check: Any, **kwargs: Any) -> Closure:
        """
        Leave each actual compensation unclosed without starting another geometric family.
        """
        check()
        assert kwargs == {"maximum_straight_mm": 30, "minimum_straight_mm": 3e-5}
        measured.append(model)
        return Closure((0.0,) * model.size, (1.0, 0.0, 0.0), 1.0)

    def refine(
        local: Boundary,
        initial: Unclosed,
        minimum: float,
        steps: int,
        check: Any,
        record: Any,
        **kwargs: Any,
    ) -> None:
        """
        Charge every started correction even when the one permitted local window fails.
        """
        assert local.targets.end == boundary.targets.end
        assert initial.branch_policy is BranchPolicy.CONTINUOUS
        assert initial.goal is ClosureGoal.MATING
        assert initial.allocation_policy is ReclosureAllocation.MEASURED
        assert minimum == 3e-5 and steps == 4
        assert kwargs == {"maximum_straight_mm": 30}
        for _ in range(steps):
            check()
            record({"stage": "feature_reclosure_step", "status": "started"})

    monkeypatch.setitem(vars(cone_escape), "nearest", nearest)
    correction = Mock(side_effect=refine)
    monkeypatch.setitem(vars(cone_escape), "refine", correction)
    roots = Roots()
    assert cone_escape.construct(escape, 3e-5, 30, roots, Mock(), Mock()) is None
    assert roots.attempted == len(escape.windows) == len(measured)
    assert roots.newton_steps == 4 and roots.reclosures == 1
    correction.assert_called_once()
