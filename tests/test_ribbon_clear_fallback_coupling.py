"""
Preserve guide dominance when a clear fallback funds coupled straight-crossing correction.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_feature_insertion.contact_recovery import (
    BaselinePolicy,
    Recovery,
)
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.solve import Result as Construction
from experiments.experiment_ribbon_feature_insertion.solve import construct
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_locked_solver import (
    fallback_feasibility,
    mating_feasibility,
    solver_v2,
)
from experiments.experiment_ribbon_locked_solver.mating_feasibility import MatingSupport
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.joint_contact import JointMode
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work


def _targets() -> Targets:
    """
    Retain exact Fusion-authored N5/450453649 poses, A17/11/25 and B7/1/23.

    Regenerating trigonometric frames in a different runtime can change stored
    floats. Replay the frozen input rather than silently substituting that variant.
    """
    return Targets(
        name="Rubik gym preview",
        start=Vector3(12.592200272177815, -7.859485030412114, -9.667221393691936),
        end=Vector3(-11.067872916338459, 9.385932686966743, -1.1855124233215215),
        start_tangent=Vector3(0.8506508083520399, 0.5257311121191335, 0.0),
        end_tangent=Vector3(0.5257311121191336, 0.0, 0.8506508083520399),
        start_width=Vector3(0.516071950840313, -0.8350219571000916, 0.19080899537654467),
        end_width=Vector3(0.82884868324359, 0.22495105434386464, -0.5122566577751341),
        lines=5,
        diameter_mm=0.75,
    )


@pytest.fixture(scope="module")
def branches() -> Construction:
    """
    Derive the same shorter crossing and separated fallback without artifact dependencies.
    """
    source = _targets()
    frames = Frames.create(source)
    radius = source.diameter_mm / 2 / PinchLimit().fraction * (1 + 1e-9)
    result = construct(
        Boundary(source, radius),
        frames,
        (0.5,),
        1e-5,
        lambda: None,
        lambda event: None,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
    )
    assert result.route is not None and result.rejected[0][1].witness is not None
    branch, contact = result.rejected[0]
    assert contact.witness is not None
    assert all(
        isinstance(branch.route.pieces[i].geometry, Straight) for i in contact.witness.pieces
    )
    return result


@pytest.mark.parametrize("status", ("clear", "blocked"))
@pytest.mark.parametrize(
    "child_policy", (BaselinePolicy.RESTORE_BLOCKED, BaselinePolicy.RESTORE_BLOCKED_GOAL)
)
def test_clear_baseline_cannot_borrow_restoration_waiver(
    branches: Construction,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    child_policy: BaselinePolicy,
) -> None:
    """
    A clear baseline keeps guide dominance while all child work remains charged to its allocation.
    """
    branch, contact = branches.rejected[0]
    assert branches.route is not None
    terminal = Mock(spec=Gate)
    terminal.measure.return_value = Report(status, 1)
    child = Recovery(None, None, 12, 1, 0.01, {"iterations": 1}, child_policy)
    selected = Mock(return_value=child)
    monkeypatch.setitem(
        vars(fallback_feasibility), "mating_supported", Mock(return_value=MatingSupport(0.5, True))
    )
    monkeypatch.setitem(vars(fallback_feasibility), "recover_mating", selected)
    before = fallback_feasibility.before_optional_motion(
        branches.route, branch.route, contact, terminal, 1e-5, lambda: None, lambda event: None
    )
    assert before is not None
    result = before(Work(3, 600, 0.2, 0.7))
    expected = BaselinePolicy.GUIDE_IMPROVEMENT if status == "clear" else child_policy
    assert result is not None and result.baseline_policy is expected
    assert selected.call_args.kwargs["baseline_policy"] is (
        BaselinePolicy.GUIDE_IMPROVEMENT if status == "clear" else BaselinePolicy.RESTORE_BLOCKED
    )
    allocation = selected.call_args.args[5]
    assert allocation.updates == 3 and allocation.pairs == 600
    assert 0 < allocation.cpu_seconds <= 0.2 and 0 < allocation.wall_seconds <= 0.7
    assert result.pairs == 12 and result.contacts == 1 and result.detail["iterations"] == 1
    assert result.detail["cpu_seconds"] >= 0 and result.detail["elapsed_seconds"] >= 0


def test_unresolved_baseline_retains_original_contact_action(
    branches: Construction, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Incomplete hardware evidence grants neither a changed correction nor a feasibility waiver.
    """
    branch, contact = branches.rejected[0]
    assert branches.route is not None
    terminal = Mock(spec=Gate)
    terminal.measure.return_value = Report("unresolved", 1)
    selected = Mock(side_effect=AssertionError("No new action for unresolved eligibility"))
    monkeypatch.setitem(
        vars(fallback_feasibility), "mating_supported", Mock(return_value=MatingSupport(0.5, True))
    )
    monkeypatch.setitem(vars(fallback_feasibility), "recover_mating", selected)
    before = fallback_feasibility.before_optional_motion(
        branches.route, branch.route, contact, terminal, 1e-5, lambda: None, lambda event: None
    )
    assert before is not None and before(Work(4, 600, 0.2, 0.7)) is None
    selected.assert_not_called()


@pytest.mark.parametrize(
    "policy", (BaselinePolicy.GUIDE_IMPROVEMENT, BaselinePolicy.RESTORE_BLOCKED)
)
@pytest.mark.parametrize("released", (False, True))
def test_mating_entry_cannot_grant_blocked_quality_policy_to_a_clear_baseline(
    branches: Construction,
    monkeypatch: pytest.MonkeyPatch,
    policy: BaselinePolicy,
    released: bool,
) -> None:
    """
    Keep clear-entry permissions even if child metadata claims a released length ceiling.
    """
    branch, contact = branches.rejected[0]
    assert branches.route is not None
    child = Result(
        branch.route,
        ContactResult("separated", 1),
        {
            "contact_pairs": 1,
            "contacts": 1,
            "contact_seconds": 0.01,
            "length_ceiling_released": released,
        },
    )
    called = Mock(return_value=child)
    monkeypatch.setitem(vars(mating_feasibility), "recover_joints", called)
    result = mating_feasibility.recover(
        branches.route,
        branch.route,
        contact,
        Mock(spec=Gate),
        1e-5,
        Work(3, 600, 0.2, 0.7),
        lambda: None,
        lambda event: None,
        baseline_policy=policy,
    )
    expected = (
        BaselinePolicy.RESTORE_BLOCKED_GOAL
        if released and policy is BaselinePolicy.RESTORE_BLOCKED
        else policy
    )
    assert result is not None and result.baseline_policy is expected
    assert called.call_args.kwargs["mode"] is (
        JointMode.MATING_CEILING
        if policy is BaselinePolicy.GUIDE_IMPROVEMENT
        else JointMode.BLOCKED_MATING
    )


def test_coupled_crossings_keep_physical_proofs_and_original_work_limits() -> None:
    """
    Retain simultaneous measured crossings instead of spending all updates on a fixed world plane.
    """
    source = _targets()
    events: list[dict[str, Any]] = []
    result = solver_v2.solve(source, Settings(1, False, True, True), lambda: None, events.append)
    assert result.route is not None and result.route.targets == source
    assert result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    recovery = result.detail["construction"]["recovery"]
    assert (
        recovery["purpose"] == "improve_separated_fallback" and recovery["accepted_improvement"]
    ), recovery
    assert "accepted_feasibility_restoration" not in recovery
    assert recovery["flat_constraints"] > 1
    assert recovery["iterations"] <= 4 and recovery["newton_steps"] <= 24
    assert recovery["cpu_seconds"] < 0.35 and recovery["elapsed_seconds"] < 2
    assert result.detail["construction"]["contact_pairs"] <= 2048
    assert result.detail["cap_error_mm"] < 1e-7 and result.detail["material_metric_error"] < 1e-10
    eligibility = next(
        event
        for event in events
        if event.get("stage") == "terminal_hardware"
        and event.get("phase") == "fallback_feasibility"
    )
    assert eligibility["status"] == "clear"


@pytest.mark.parametrize("fraction,straight_pair", ((1.0, True), (0.5, False), (None, True)))
def test_clear_fallback_keeps_full_step_and_curved_contact_actions(
    branches: Construction,
    monkeypatch: pytest.MonkeyPatch,
    fraction: float | None,
    straight_pair: bool,
) -> None:
    """
    Preserve established motions unless the actual straight-pair correction is trust-clipped.
    """
    branch, contact = branches.rejected[0]
    assert branches.route is not None
    terminal = Mock(spec=Gate)
    terminal.measure.return_value = Report("clear", 1)
    selected = Mock(side_effect=AssertionError("Keep the established first motion"))
    monkeypatch.setitem(
        vars(fallback_feasibility),
        "mating_supported",
        Mock(return_value=MatingSupport(fraction, straight_pair)),
    )
    monkeypatch.setitem(vars(fallback_feasibility), "recover_mating", selected)
    before = fallback_feasibility.before_optional_motion(
        branches.route, branch.route, contact, terminal, 1e-5, lambda: None, lambda event: None
    )
    assert before is not None and before(Work(4, 600, 0.2, 0.7)) is None
    selected.assert_not_called()
