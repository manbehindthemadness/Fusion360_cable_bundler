"""
Keep new closed-material yields inside the adaptive parent's original work and ownership.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_terminal_hardware import (
    adaptive_event_continuation as continuation,
)
from experiments.experiment_ribbon_terminal_hardware import adaptive_event_recovery as adaptive
from experiments.experiment_ribbon_terminal_hardware import deviation_sequence as sequence
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_construction import Roots
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_plan import Proposal
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_window import Window
from experiments.experiment_ribbon_terminal_hardware.check import Report, inspect
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.joint_handoff import JointHandoff
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from experiments.experiment_ribbon_terminal_hardware.run_translation import StraightSlots
from tests.ribbon_adaptive_controls import (
    negative_discovery_boundary as negative_discovery_boundary,
)
from tests.test_ribbon_adaptive_continuation import moved, reply
from tests.test_ribbon_adaptive_events import _bump, _proposal, _source
from tests.test_ribbon_contact_refinement import _gate
from tests.test_ribbon_departure_return import _departure
from tests.test_ribbon_deviation_sequence import _result

pytestmark = pytest.mark.usefixtures(negative_discovery_boundary.__name__)


def _contact(route: FoldRoute) -> ContactResult:
    """
    Supply occupied identities at a mocked strict-checker boundary, not a clearance certificate.
    """
    return ContactResult(
        "penetration",
        3,
        Penetration((0, len(route.pieces) - 1), (0.5, 0, 0), (0.5, 0, 0), Vector3(0, 0, 0)),
    )


def _translated_departure(source: FoldRoute) -> tuple[FoldRoute, Penetration]:
    """
    Move planar internal material while three exact straight contributions retain both target poses.
    """
    model = StraightSlots(source)
    values = list(model.initial)
    a, b, t = (
        source.pieces[1].pose.tangent,
        source.pieces[3].pose.tangent,
        source.targets.start_tangent,
    )
    determinant = a.x * b.z - b.x * a.z
    amount = 0.01
    values[0] += amount / model.scale
    values[1] += -amount * (t.x * b.z - b.x * t.z) / determinant / model.scale
    values[2] += -amount * (a.x * t.z - t.x * a.z) / determinant / model.scale
    current = model.route(tuple(values))
    assert current is not None and cap_error(current) < 1e-10
    witness = _departure(1, 0, 0)[1]
    return current, replace(witness, pieces=(1, 5))


@pytest.mark.parametrize("enabled", (False, True))
@pytest.mark.parametrize("updates", (1, 3))
def test_sequence_yields_new_closed_departure_before_another_reversal(
    monkeypatch: pytest.MonkeyPatch, enabled: bool, updates: int
) -> None:
    """
    Keep standalone reversal behavior while adaptive callers receive the current state without another action.
    """
    source, witness = _departure(1, 0, 0)
    current, new_witness = _translated_departure(source)
    crossing = ContactResult("penetration", 3, witness=new_witness)
    captured = []

    def stage(route: FoldRoute, *args: Any, **options: Any) -> Result:
        """
        Model a measured closed child correction; full physical qualification remains external.
        """
        del args
        captured.append(options)
        if len(captured) == 1:
            options["on_blocked"](JointHandoff(current, crossing))
        return _result(route, pairs=3)

    monkeypatch.setitem(vars(sequence), "recover_joints", stage)
    states: list[JointHandoff] = []
    result = sequence.recover(
        source,
        ContactResult("penetration", 3, witness=witness),
        _gate(source),
        lambda: None,
        Mock(),
        work=Work(updates, 100, 0.35, 2),
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        on_event_refinement=states.append if enabled else None,
    )
    assert result.contact is None and result.route is source
    assert len(captured) == (1 if enabled or updates == 1 else 2)
    if enabled and updates > 1:
        assert len(states) == 1 and states[0].route is current and states[0].evidence is crossing
        assert result.detail["stop_reason"] == "event_refinement_handoff"
        assert result.detail["iterations"] == 1 and result.detail["newton_steps"] == 1
        assert result.detail["contact_pairs"] == 3 and result.detail["reflected_folds"] == [1]
    elif updates > 1:
        assert not states and captured[-1]["mode"].selected_fold == 0
    else:
        assert not states and result.detail["iterations"] == 1


@pytest.mark.parametrize(
    "fault",
    (
        None,
        "missing",
        "duplicate",
        "unchanged",
        "wrong_stop",
        "uncertain",
        "pairs",
        "width",
        "late",
    ),
)
def test_continuation_validates_and_holds_yield_until_its_original_clock_passes(
    monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    """
    Reject malformed receipts and never expose a child state after wrapper time exhaustion.
    """
    source, hardware, evidence = _source()
    current = moved(source)
    clock = [0.0]
    for name in ("process_time", "perf_counter"):
        monkeypatch.setitem(vars(continuation), name, lambda: clock[0])

    def child(*args: Any, **options: Any) -> Result:
        """
        Exercise the callback contract independently of the geometric solver.
        """
        del args
        answer = reply(source, accepted=False)
        answer.detail["stop_reason"] = "event_refinement_handoff"
        if fault != "missing":
            route = source if fault == "unchanged" else current
            contact = _contact(current)
            if fault == "uncertain":
                contact = replace(contact, limit="depth")
            elif fault == "pairs":
                contact = replace(contact, pairs_checked=999)
            elif fault == "width":
                pieces = list(current.pieces)
                index = next(
                    i for i, p in enumerate(pieces) if isinstance(p.geometry, CylindricalFold)
                )
                geometry = pieces[index].geometry
                assert isinstance(geometry, CylindricalFold)
                pieces[index] = replace(pieces[index], geometry=replace(geometry, width_mm=2.0))
                route = replace(current, pieces=tuple(pieces))
            state = JointHandoff(route, contact)
            options["on_event_refinement"](state)
            if fault == "duplicate":
                options["on_event_refinement"](state)
        if fault == "wrong_stop":
            answer.detail["stop_reason"] = "joint_no_descent"
        if fault == "late":
            clock[0] = 0.36
        return answer

    monkeypatch.setitem(vars(continuation), "recover_sequence", child)
    states: list[JointHandoff] = []
    terminal = Mock(spec=Gate, hardware=hardware)

    def run() -> Result:
        """
        Retain the same original counters and clocks across the wrapper.
        """
        return continuation.recover(
            source,
            evidence,
            terminal,
            lambda: None,
            Mock(),
            work=Work(2, 100, 0.35, 2),
            maximum_length_mm=100,
            minimum_straight_mm=1e-5,
            on_event_refinement=states.append,
        )

    if fault not in (None, "late"):
        with pytest.raises(ArithmeticError):
            run()
        assert not states
    else:
        result = run()
        assert result.contact is None and result.route is source
        assert len(states) == (0 if fault == "late" else 1)
        assert result.detail["stop_reason"] == (
            "phase_budget" if fault == "late" else "event_refinement_handoff"
        )


@pytest.mark.parametrize("available,late", ((True, False), (True, True), (False, False)))
def test_parent_refines_new_owned_material_with_residual_roots_and_no_second_correction(
    monkeypatch: pytest.MonkeyPatch, available: bool, late: bool
) -> None:
    """
    Spend existing choices once, retire moved lineage, and require new complete checker results.
    """
    source, hardware, evidence = _source()
    terminal = Mock(spec=Gate, hardware=hardware)
    clock = [0.0]
    for name in ("process_time", "perf_counter"):
        monkeypatch.setitem(vars(adaptive), name, lambda: clock[0])
    root_counts = []
    proposals: list[Proposal] = []
    fixed_calls = []
    records: list[dict[str, Any]] = []

    def plan(route: FoldRoute, *args: Any, **options: Any) -> Proposal:
        """
        Supply closed analytical workspaces at the external planning boundary.
        """
        del args
        index = 0 if not proposals else len(route.pieces) - 1
        if proposals:
            options["select_window"](route, (index,))
        proposed = _proposal(Window(route, index, index + 1))
        proposals.append(proposed)
        return proposed

    def construct(proposal: Proposal, minimum: float, roots: Roots, *args: Any) -> FoldRoute:
        """
        Preserve the global root/Newton ledger across independently authored local modules.
        """
        del minimum, args
        count = (5 if available else 8) if not root_counts else 1
        roots.attempted += count
        roots.declined += count - 1
        root_counts.append(roots.attempted)
        if len(root_counts) == 2:
            assert roots.newton_steps == 2 and roots.attempted == 6
        clock[0] += 0.01
        return _bump(proposal.window)

    def fixed(route: FoldRoute, *args: Any, **options: Any) -> Result:
        """
        Return one new closed blocker instead of requesting renewed fixed-topology work.
        """
        del args
        fixed_calls.append(options["work"])
        answer = reply(route, accepted=False)
        if available:
            current = moved(route)
            options["on_event_refinement"](JointHandoff(current, _contact(current)))
            answer.detail["stop_reason"] = "event_refinement_handoff"
        else:
            assert "on_event_refinement" not in options
        clock[0] = 0.36 if late else clock[0] + 0.01
        return answer

    reports = [0]

    def certify(route: FoldRoute, *args: Any) -> Report:
        """
        Keep an actual first proxy hit; final checker clearance is an explicit controlled boundary.
        """
        del args
        reports[0] += 1
        return inspect(route, hardware) if reports[0] == 1 else Report("clear", 1)

    terminal.certify.side_effect = certify
    monkeypatch.setitem(vars(adaptive), "plan", plan)
    monkeypatch.setitem(vars(adaptive), "construct", construct)
    monkeypatch.setitem(vars(adaptive), "continue_fixed", fixed)
    proof = Mock(return_value=ContactResult("separated", 7))
    monkeypatch.setitem(vars(adaptive), "inspect_contact", proof)
    result = adaptive.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        records.append,
        work=Work(3, 100, 0.35, 2, 10),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and len(fixed_calls) == 1
    assert fixed_calls[0].updates == 2 and fixed_calls[0].newton_steps == 10
    if available and not late:
        assert result.contact is not None and result.detail["iterations"] == 3
        assert result.detail["roots_attempted"] == 6 and result.detail["newton_steps"] == 2
        assert (
            result.detail["contact_pairs"] == 14 and result.detail["closed_material_resumes"] == 1
        )
        candidate = [
            e
            for e in records
            if e.get("stage") == "adaptive_events" and e.get("status") == "candidate"
        ][-1]
        assert all(label[0] == 4 for label in candidate["retired_ids"])
        assert any(e.get("status") == "subdivide_after_closed_material_handoff" for e in records)
        proof.assert_called_once()
    else:
        assert result.contact is None and result.route is source
        assert len(root_counts) == 1 and result.detail["closed_material_resumes"] == 0
        proof.assert_not_called()
