"""
Verify first-motion feasibility priority, paired return evidence and nonrenewable work.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_feature_insertion import contact_recovery
from experiments.experiment_ribbon_feature_insertion.contact_recovery import (
    BaselinePolicy,
    InitialPolicy,
    Recovery,
    recover,
)
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.selection import Policy
from experiments.experiment_ribbon_feature_insertion.solve import Result as Construction
from experiments.experiment_ribbon_feature_insertion.solve import construct
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_locked_solver import fallback_feasibility, solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware import incident_recovery
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.flat_separation import paired_return_fold
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work


def _scene() -> Scene:
    """
    Recreate the retained signed-preset case3 boundary inputs without loading transient jobs.
    """
    return Scene(
        Config(1957585417, 10, 0.75, 300, 300),
        Goal.from_degrees(17, 3, 30),
        Goal.from_degrees(11, 7, 43),
    )


@pytest.fixture(scope="module")
def branches() -> Construction:
    """
    Retain the actual shorter penetrating branch and separated fallback before any new correction.
    """
    scene = _scene()
    frames = Frames.create(scene.targets)
    radius = scene.targets.diameter_mm / 2 / PinchLimit().fraction * (1 + 1e-9)
    result = construct(
        Boundary(scene.targets, radius),
        frames,
        (0.5,),
        1e-5,
        lambda: None,
        lambda e: None,
        selection_policy=Policy.MONOTONIC,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
    )
    assert result.route is not None and result.rejected[0][1].status == "penetration"
    return result


def test_return_bracket_selects_entry_fold_and_rejects_wrong_phases(branches: Construction) -> None:
    """
    Require actual BEFORE-to-AFTER adjacent folds instead of guessing either contact index.
    """
    branch, contact = branches.rejected[0]
    witness = contact.witness
    assert witness is not None and witness.pieces == (4, 5)
    assert paired_return_fold(branch.route, witness) == 2
    wrong = replace(witness, first=(1.0, witness.first[1], witness.first[2]))
    assert paired_return_fold(branch.route, wrong) is None


def test_pair_entry_forwards_a_smaller_allocation_without_renewal(
    monkeypatch: pytest.MonkeyPatch,
    branches: Construction,
) -> None:
    """
    The shared reflection routine receives the caller's exact remaining update count.
    """
    branch, contact = branches.rejected[0]
    assert contact.witness is not None
    answer = Recovery(None, None, 0, 0, 0.0, {"status": "unresolved"})
    selected = Mock(return_value=answer)
    monkeypatch.setitem(vars(incident_recovery), "_recover_selected", selected)
    result = incident_recovery.recover_paired_return(
        branch.route,
        contact.witness,
        Mock(spec=Gate),
        lambda: None,
        lambda e: None,
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
        remaining_pairs=321,
        maximum_cpu_seconds=0.1,
        maximum_seconds=0.5,
        maximum_updates=2,
    )
    assert result is answer and selected.call_args.args[1] == 2
    assert selected.call_args.kwargs["maximum_updates"] == 2
    assert selected.call_args.kwargs["remaining_pairs"] == 321
    assert selected.call_args.kwargs["maximum_cpu_seconds"] == 0.1


def test_existing_overflow_deferral_precedes_eligibility_measurement(
    monkeypatch: pytest.MonkeyPatch, branches: Construction
) -> None:
    """
    Already deferred expensive first steps do not spend hardware work or change accepted controls.
    """
    branch, contact = branches.rejected[0]
    monkeypatch.setitem(vars(contact_recovery), "plan_step", Mock(return_value=Mock(fraction=0.2)))
    before = Mock(side_effect=AssertionError("No eligibility work after overflow deferral"))
    result = recover(
        branch.route,
        contact,
        610,
        1e-5,
        lambda: None,
        lambda e: None,
        initial_policy=InitialPolicy.DEFER_OVERFLOW,
        before_first_motion=before,
    )
    assert result.detail["status"] == "deferred" and result.detail["iterations"] == 0
    before.assert_not_called()


@pytest.mark.parametrize("field,value", (("iterations", 5), ("newton_steps", 25), ("pairs", 2049)))
def test_first_motion_cannot_return_excess_work(
    branches: Construction,
    field: str,
    value: int,
) -> None:
    """
    Reject counters outside the supplied allocation before accepting a callback result.
    """
    branch, contact = branches.rejected[0]
    detail = {"status": "unresolved", "iterations": 0, "newton_steps": 0}
    pairs = value if field == "pairs" else 0
    if field != "pairs":
        detail[field] = value
    before = Mock(return_value=Recovery(None, None, pairs, 0, 0.0, detail))
    with pytest.raises(ArithmeticError, match="shared work"):
        recover(
            branch.route,
            contact,
            1702,
            1e-5,
            lambda: None,
            lambda e: None,
            initial_policy=InitialPolicy.DEFER_OVERFLOW,
            before_first_motion=before,
        )


@pytest.mark.parametrize("baseline_policy", tuple(BaselinePolicy))
def test_hook_receives_only_preparation_debited_work(
    branches: Construction, baseline_policy: BaselinePolicy
) -> None:
    """
    A zero-motion deferral still includes its first projection and callback preparation in CPU accounting.
    """
    branch, contact = branches.rejected[0]
    allocations: list[Work] = []

    def before(work: Work) -> Recovery:
        """
        Retain the real allocation while declining motion without a contact certificate.
        """
        allocations.append(work)
        return Recovery(
            None, None, 0, 0, 0.0, {"status": "deferred", "iterations": 0}, baseline_policy
        )

    result = recover(
        branch.route,
        contact,
        1702,
        1e-5,
        lambda: None,
        lambda e: None,
        initial_policy=InitialPolicy.DEFER_OVERFLOW,
        before_first_motion=before,
    )
    assert len(allocations) == 1 and allocations[0].updates == 4 and allocations[0].pairs == 1702
    assert 0 < allocations[0].cpu_seconds < 0.35 and 0 < allocations[0].wall_seconds < 2
    assert result.detail["status"] == "deferred" and result.pairs == result.contacts == 0
    assert result.detail["cpu_seconds"] > 0 and result.detail["iterations"] == 0
    assert result.baseline_policy is baseline_policy


@pytest.mark.parametrize("status", ("clear", "unresolved"))
def test_other_eligibility_outcomes_preserve_the_original_action(
    monkeypatch: pytest.MonkeyPatch,
    branches: Construction,
    status: str,
) -> None:
    """
    Neither cleared nor incomplete baseline evidence selects a new physical correction.
    """
    branch, contact = branches.rejected[0]
    assert branches.route is not None
    terminal = Mock(spec=Gate)
    terminal.measure.return_value = Report(status, 1)
    selected = Mock(side_effect=AssertionError("No new correction"))
    monkeypatch.setitem(vars(fallback_feasibility), "recover_paired_return", selected)
    before = fallback_feasibility.before_optional_motion(
        branches.route, branch.route, contact, terminal, 1e-5, lambda: None, lambda e: None
    )
    assert before is not None and before(Work(4, 1702, 0.3, 1)) is None
    selected.assert_not_called()


def test_unsupported_contact_does_not_probe_or_replace_original_recovery(
    monkeypatch: pytest.MonkeyPatch, branches: Construction
) -> None:
    """
    A contact without the return bracket cannot consume hardware work or select a joint fallback.
    """
    branch, contact = branches.rejected[0]
    assert contact.witness is not None and branches.route is not None
    witness = replace(
        contact.witness, first=(1.0, contact.witness.first[1], contact.witness.first[2])
    )
    assert paired_return_fold(branch.route, witness) is None
    unsupported = replace(contact, witness=witness)
    terminal = Mock(spec=Gate)
    selected = Mock(side_effect=AssertionError("Unsupported contact retains its original action"))
    monkeypatch.setitem(vars(fallback_feasibility), "recover_paired_return", selected)
    before = fallback_feasibility.before_optional_motion(
        branches.route, branch.route, unsupported, terminal, 1e-5, lambda: None, lambda e: None
    )
    assert before is not None and before(Work(4, 1702, 0.3, 1)) is None
    terminal.measure.assert_not_called()
    selected.assert_not_called()


def test_ordinary_contact_recovery_retains_actual_mating_certification() -> None:
    """
    Preserve the earlier ordered-cap repair instead of replacing its successful first motion.
    """
    scene = Scene(
        Config(995783115, 8, 0.75, 300, 300),
        Goal.from_degrees(4, 2, 7),
        Goal.from_degrees(23, 3, 31),
    )
    events: list[dict[str, Any]] = []
    result = solver_v2.solve(
        scene.targets, Settings(1, False, True, True), lambda: None, events.append
    )
    assert result.route is not None and result.route.targets == scene.targets
    assert result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    assert result.detail["cap_error_mm"] < 1e-10
    assert result.detail["construction"]["recovery"]["accepted_improvement"]
    assert not any(event.get("stage") == "paired_fold_return" for event in events)


def test_retained_layout_uses_the_shorter_branch_and_one_measured_reflection() -> None:
    """
    Preserve actual fixed caps while replacing the163mm fallback with strict compact material.
    """
    scene = _scene()
    events: list[dict[str, Any]] = []
    result = solver_v2.solve(
        scene.targets, Settings(1, False, True, True), lambda: None, events.append
    )
    assert result.route is not None and result.route.targets == scene.targets
    assert result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    recovery = result.detail["construction"]["recovery"]
    assert recovery["accepted_improvement"] and recovery["selected_fold"] == 2
    assert recovery["method"] == "fallback_coupled_feasibility"
    assert recovery["baseline_length_mm"] > 160 and result.route.material_length_mm < 80
    assert recovery["iterations"] <= 4 and recovery["newton_steps"] <= 24
    assert 0 < recovery["cpu_seconds"] <= 0.35 and recovery["pairs"] <= 1702
    assert result.detail["construction"]["contact_pairs"] <= 2048
    assert len([e for e in events if e.get("stage") == "paired_fold_return"]) == 1
    assert result.detail["cap_error_mm"] < 1e-7 and result.detail["material_metric_error"] < 1e-10


def test_mating_crossing_restores_blocked_baseline_before_separate_repairs_exhaust_work() -> None:
    """
    Keep complete physical feasibility within the old length ceiling even when guide dominance is absent.
    """
    scene = Scene(
        Config(3294378590, 2, 0.75, 300, 300),
        Goal.from_degrees(16, 0, 56),
        Goal.from_degrees(12, 10, 16),
    )
    events: list[dict[str, Any]] = []
    result = solver_v2.solve(
        scene.targets, Settings(1, False, True, True), lambda: None, events.append
    )
    recovery = result.detail["construction"]["recovery"]
    assert result.route is not None, recovery
    assert result.route.targets == scene.targets and result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    assert recovery["method"] == "fallback_mating_feasibility"
    assert recovery["purpose"] == "restore_blocked_fallback"
    assert recovery["accepted_feasibility_restoration"] and not recovery["accepted_improvement"]
    assert recovery["length_mm"] <= recovery["baseline_length_mm"]
    assert recovery["iterations"] <= 4 and recovery["newton_steps"] <= 24
    assert recovery["cpu_seconds"] < 0.35 and recovery["pairs"] <= 2048
    assert result.detail["construction"]["contact_pairs"] <= 2048
    assert result.detail["cap_error_mm"] < 1e-7 and result.detail["material_metric_error"] < 1e-10
    eligibility = next(
        e
        for e in events
        if e.get("stage") == "terminal_hardware" and e.get("phase") == "fallback_feasibility"
    )
    assert eligibility["status"] == "blocked"
    prediction = next(e for e in events if e.get("stage") == "mating_feasibility_prediction")
    assert prediction["status"] == "coupling_required"
    assert prediction["committed_updates"] == prediction["contact_certificates"] == 0
    assert prediction["preparation_newton_upper_bound"] <= 12
