"""
Choose early correction from intact current material and preserve bounded event refinement after preparation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_terminal_hardware import (
    adaptive_event_continuation as continuation,
)
from experiments.experiment_ribbon_terminal_hardware import adaptive_event_recovery as runner
from experiments.experiment_ribbon_terminal_hardware import deviation_sequence
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_construction import Roots
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_plan import Proposal
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_schedule import (
    Action,
    Correction,
    choose,
    preparation_declined,
)
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_window import (
    Edit,
    EventId,
    Window,
    events,
)
from experiments.experiment_ribbon_terminal_hardware.check import Report, inspect
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.model import Hardware
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.test_ribbon_adaptive_continuation import moved, reply
from tests.test_ribbon_adaptive_events import _bump, _proposal, _source


@dataclass
class Scenario:
    """
    Retain real cap-closed geometry and a measured owned blocker, with explicit final checker boundaries.
    """

    source: FoldRoute
    parent: FoldRoute
    hardware: Hardware
    initial: Report
    blocker: Report
    local: FoldRoute
    lineage: tuple[EventId, ...]
    edit: Edit


@pytest.fixture
def scenario() -> Scenario:
    """
    An authored three-bend insertion still has a strict proxy hit in one interior straight member.
    """
    source, hardware, initial = _source()
    window = Window(source, 0, 1)
    local = _bump(window)
    parent = window.splice(local)
    blocker = inspect(parent, hardware)
    assert blocker.status == "blocked" and blocker.witness is not None
    assert blocker.witness.piece < len(local.pieces)
    assert isinstance(parent.pieces[blocker.witness.piece].geometry, Straight)
    old_ids = tuple((0, i) for i in range(len(source.pieces)))
    children = tuple((1, i) for i in range(len(local.pieces)))
    edit = Edit(children, old_ids[:1], source.pieces[:1], local.pieces)
    return Scenario(source, parent, hardware, initial, blocker, local, children + old_ids[1:], edit)


@pytest.mark.parametrize(
    "variation,expected",
    (
        ("owned", Action.CORRECT_MODULE),
        ("spent", Action.REFINE),
        ("copied_route", Action.STOP),
        ("recreated_piece", Action.REFINE),
        ("retired_id", Action.REFINE),
        ("uncertain", Action.STOP),
        ("unwitnessed", Action.STOP),
        ("roots_exhausted", Action.CORRECT_EXHAUSTED),
        ("all_spent", Action.STOP),
    ),
)
def test_action_requires_current_intact_owned_material_without_a_bend_count_rule(
    scenario: Scenario,
    variation: str,
    expected: Action,
) -> None:
    """
    Equal geometry cannot revive old ownership or evidence; a consumed correction entry stays consumed.
    """
    route, owner, lineage, evidence = (
        scenario.parent,
        scenario.parent,
        scenario.lineage,
        scenario.blocker,
    )
    correction = Correction.SPENT if variation in ("spent", "all_spent") else Correction.READY
    roots = 8 if variation in ("roots_exhausted", "all_spent") else 1
    if variation == "copied_route":
        owner = replace(route)
    elif variation == "recreated_piece":
        route = replace(route, pieces=(replace(route.pieces[0]),) + route.pieces[1:])
        owner = route
    elif variation == "retired_id":
        lineage = ((9, 0),) + lineage[1:]
    elif variation == "uncertain":
        evidence = Report("unresolved", 1)
    elif variation == "unwitnessed":
        evidence = Report("blocked", 1)
    assert events(route) == 9
    assert choose(route, evidence, owner, lineage, (scenario.edit,), roots, correction) is expected


@pytest.mark.parametrize(
    "field,value",
    (
        ("motion_attempted", True),
        ("motion_attempted", None),
        ("motion_attempted", "missing"),
        ("hardware_preparation_only", None),
        ("newton_steps", 1),
        ("contacts", 1),
        ("contact_pairs", 1),
        ("stages", 2),
        ("iterations", 0),
        ("stop_reason", "phase_budget"),
    ),
)
def test_zero_accepted_steps_alone_cannot_authorize_more_topology(
    scenario: Scenario,
    field: str,
    value: Any,
) -> None:
    """
    Only a complete explicit preparation-only receipt can leave the unchanged source eligible for refinement.
    """
    detail = {
        "status": "unresolved",
        "hardware_preparation_only": True,
        "motion_attempted": False,
        "newton_steps": 0,
        "contacts": 0,
        "contact_pairs": 0,
        "stages": 1,
        "iterations": 1,
        "stop_reason": "linear_projection_infeasible",
    }
    assert preparation_declined(
        Result(scenario.parent, None, detail), scenario.parent, scenario.blocker
    )
    if value == "missing":
        detail.pop(field)
    else:
        detail[field] = value
    assert not preparation_declined(
        Result(scenario.parent, None, detail), scenario.parent, scenario.blocker
    )


@dataclass
class Run:
    """
    Observe real local splices while keeping construction choices and physical checker dispositions explicit.
    """

    scenario: Scenario
    gate: Mock
    windows: list[Window]
    candidates: list[FoldRoute]
    records: list[dict[str, Any]]


@pytest.fixture
def configured(scenario: Scenario, monkeypatch: pytest.MonkeyPatch) -> Run:
    """
    Use the actual controller window strategy, with authored straight subwindows and measured current witnesses.
    """
    state = Run(scenario, Mock(spec=Gate, hardware=scenario.hardware), [], [], [])

    def selected(route: FoldRoute, members: tuple[int, ...]) -> Window:
        """
        Supply a small aligned structural interval inside the already inserted material.
        """
        index = 0 if route is scenario.source else members[0]
        assert isinstance(route.pieces[index].geometry, Straight)
        return Window(route, index, index + 1)

    def proposed(
        route: FoldRoute, observed: Report, hardware: Hardware, check: Any, *, select_window: Any
    ) -> Proposal:
        """
        Preserve actual member coverage and exercise reopening versus subdivision through the controller.
        """
        del hardware, check
        assert observed.witness is not None
        return _proposal(select_window(route, (observed.witness.piece,)))

    def constructed(proposal: Proposal, minimum: float, roots: Roots, *args: Any) -> FoldRoute:
        """
        Charge one fit and splice real cap-preserving material; no nonlinear solver success is asserted here.
        """
        del minimum, args
        state.windows.append(proposal.window)
        roots.attempted += 1
        local = (
            scenario.local if proposal.window.source is scenario.source else _bump(proposal.window)
        )
        state.candidates.append(proposal.window.splice(local))
        return local

    def certified(route: FoldRoute, stage: str) -> Report:
        """
        Keep the true inserted blocker for original/undo material, with explicit clear final boundary doubles.
        """
        if stage == "adaptive_continuation_final":
            return Report("clear", 1)
        assert scenario.blocker.witness is not None
        member = scenario.parent.pieces[scenario.blocker.witness.piece]
        if any(piece is member for piece in route.pieces):
            return scenario.blocker
        return Report("clear", 1)

    monkeypatch.setitem(vars(runner), "select", selected)
    monkeypatch.setitem(vars(runner), "plan", proposed)
    monkeypatch.setitem(vars(runner), "construct", constructed)
    monkeypatch.setitem(
        vars(runner), "inspect_contact", Mock(return_value=ContactResult("separated", 7))
    )
    state.gate.certify.side_effect = certified
    state.gate.measure.return_value = scenario.blocker
    return state


def execute(state: Run) -> Result:
    """
    Run one original four-update allocation without saved inputs or renewed correction choices.
    """
    result = runner.recover(
        state.scenario.source,
        state.scenario.initial,
        state.gate,
        lambda: None,
        state.records.append,
        work=Work(4, 2048, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None
    return result


def test_early_correction_clears_the_owned_module_without_more_events(
    configured: Run,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reach correction after one fit, preserving actual caps/material and all reported budgets before pruning.
    """
    stage = Mock(side_effect=lambda route, *args, **kwargs: reply(moved(route)))
    monkeypatch.setitem(vars(continuation), "recover_sequence", stage)
    result = execute(configured)
    assert result.contact is not None and len(configured.windows) == 1 and events(result.route) == 9
    assert result.detail["correction_schedule"] == Action.CORRECT_MODULE.value
    assert result.detail["roots_attempted"] == 1 and result.detail["iterations"] == 2
    assert result.detail["newton_steps"] == 2 and result.detail["pruning_unavailable"] == 1
    assert stage.call_args.kwargs["work"].updates == 3


def test_actual_unsupported_preparation_can_subdivide_and_grow_beyond_six(
    configured: Run,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Run the real sequence's no-motion decline, then preserve outer groups while adding an exact local module.
    """
    stage = Mock(return_value=None)
    monkeypatch.setitem(vars(deviation_sequence), "recover_joints", stage)
    result = execute(configured)
    assert result.contact is not None and len(configured.windows) == 2
    assert (events(configured.candidates[0]), events(result.route)) == (9, 12)
    selected = configured.windows[1]
    assert selected.end - selected.begin == 1 and isinstance(
        selected.route.pieces[0].geometry, Straight
    )
    assert cap_error(result.route) < 1e-10 and material_error(result.route) < 1e-10
    assert all(
        a is b
        for a, b in zip(
            result.route.pieces[: selected.begin], selected.source.pieces[: selected.begin]
        )
    )
    assert all(
        a is b
        for a, b in zip(
            result.route.pieces[selected.begin + 5 :], selected.source.pieces[selected.end :]
        )
    )
    assert result.detail["preparation_only_resumes"] == 1 and result.detail["iterations"] == 4
    assert result.detail["roots_attempted"] == 2 and result.detail["newton_steps"] == 0
    assert result.detail["fixed_continuation"]["hardware_preparation_only"] is True
    assert any(e.get("status") == "subdivide_after_preparation_decline" for e in configured.records)
    stage.assert_called_once()


@pytest.mark.parametrize("attempted", (True, None, "missing"))
def test_trial_or_unknown_motion_receipt_cannot_resume_refinement(
    configured: Run,
    monkeypatch: pytest.MonkeyPatch,
    attempted: Any,
) -> None:
    """
    Even zero accepted Newton steps leave no fallback permission after a trial or an unknown motion report.
    """

    def decline(route: FoldRoute, *args: Any, **kwargs: Any) -> Result:
        """
        Model an attempted or unmeasured correction without accepting geometry.
        """
        del args, kwargs
        child = reply(route, False)
        child.detail.update(
            iterations=1,
            newton_steps=0,
            contacts=0,
            contact_pairs=0,
            stages=1,
            motion_attempted=attempted,
            hardware_preparation_only=True,
            stop_reason="linear_projection_infeasible",
        )
        if attempted == "missing":
            child.detail.pop("motion_attempted")
        return child

    stage = Mock(side_effect=decline)
    monkeypatch.setitem(vars(continuation), "recover_sequence", stage)
    result = execute(configured)
    assert (
        result.contact is None and len(configured.windows) == 1 and result.detail["iterations"] == 2
    )
    assert result.detail["preparation_only_resumes"] == 0 and result.detail["roots_attempted"] == 1
    stage.assert_called_once()


@pytest.mark.parametrize("attempted", (False, True, None, "missing"))
def test_sequence_requires_explicit_child_motion_evidence_for_preparation_only(
    scenario: Scenario,
    monkeypatch: pytest.MonkeyPatch,
    attempted: Any,
) -> None:
    """
    Aggregate the actual sequence boundary conservatively instead of treating an omitted field as no motion.
    """
    detail = {
        "status": "unresolved",
        "iterations": 0,
        "newton_steps": 0,
        "contacts": 0,
        "contact_pairs": 0,
        "contact_seconds": 0.0,
        "stop_reason": "linear_projection_infeasible",
        "motion_attempted": attempted,
    }
    if attempted == "missing":
        detail.pop("motion_attempted")
    monkeypatch.setitem(
        vars(deviation_sequence),
        "recover_joints",
        Mock(return_value=Result(scenario.parent, None, detail)),
    )
    gate = Mock(spec=Gate, hardware=scenario.hardware, measure=Mock(return_value=scenario.blocker))
    result = deviation_sequence.recover(
        scenario.parent,
        scenario.blocker,
        gate,
        lambda: None,
        Mock(),
        work=Work(2, 23, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result.detail["hardware_preparation_only"] is (attempted is False)
    assert result.detail["motion_attempted"] is (attempted if type(attempted) is bool else None)
    assert result.detail["iterations"] == 1


def test_declined_local_allocation_cannot_retry_its_same_family_after_preparation(
    configured: Run,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Unsupported correction cannot renew a local family that already failed before any module was built.
    """

    def decline(proposal: Proposal, minimum: float, roots: Roots, *args: Any) -> None:
        """
        Record a finite declined family with fewer than the overall eight allowed fitted roots.
        """
        del proposal, minimum, args
        roots.attempted = 4

    build = Mock(side_effect=decline)
    monkeypatch.setitem(vars(runner), "construct", build)
    stage = Mock(return_value=None)
    monkeypatch.setitem(vars(deviation_sequence), "recover_joints", stage)
    configured.gate.measure.return_value = configured.scenario.initial
    result = execute(configured)
    assert (
        result.contact is None
        and result.detail["correction_schedule"] == Action.CORRECT_DECLINED.value
    )
    assert result.detail["roots_attempted"] == 4 and result.detail["iterations"] == 2
    assert result.detail["preparation_only_resumes"] == 0
    build.assert_called_once()
    stage.assert_called_once()
