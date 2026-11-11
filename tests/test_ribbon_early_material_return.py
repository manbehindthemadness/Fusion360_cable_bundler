"""
Transfer only actual new incident returns while preserving original clocks and physical gates.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import MaterialGuidance
from experiments.experiment_ribbon_terminal_hardware.material_return_selection import (
    UnreflectedReturns,
    select_fold,
)
from experiments.experiment_ribbon_terminal_hardware.restoration_handoff import RestorationHandoff
from tests.test_ribbon_contact_refinement import _gate
from tests.test_ribbon_material_return import _witness
from tests.test_ribbon_restoration_handoff import _contact, _Equations, _source


def test_return_policy_uses_actual_interval_and_never_reverses_a_previous_fold() -> None:
    """
    Independently authored occupied material selects its turn, never the unrelated final fold.
    """
    source = _source()
    contact = _contact(source)
    assert contact.witness is not None
    selected = select_fold(source, contact.witness)
    assert selected is not None and selected != 3
    assert UnreflectedReturns(frozenset({3})).select(source, contact.witness) == selected
    assert UnreflectedReturns(frozenset({selected, 3})).select(source, contact.witness) is None
    with pytest.raises(ValueError):
        UnreflectedReturns(frozenset({-1}))


@pytest.mark.parametrize(
    "outcome", ("early", "default", "repeated", "last_update", "miss", "budget", "late", "cancel")
)
def test_real_joint_transfers_before_another_projection_only_when_new_return_is_available(
    monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """
    Actual placement and negative evidence drive transfer; only algebraic outcomes and clocks are controlled.
    """
    source = _source()
    contact = _contact(source)
    assert contact.witness is not None
    selected = select_fold(source, contact.witness)
    assert selected is not None
    clock = [0.0]
    cancelled = [False]
    for name in ("process_time", "perf_counter"):
        monkeypatch.setitem(vars(joint_contact), name, lambda: clock[0])
    project = Mock()

    def projection(_model: Any, values: tuple[float, ...], *_args: Any, **_kw: Any) -> Any:
        """
        Provide one descent, then decline instead of spending another numerical search.
        """
        project(values)
        return (0.001,) + (0.0,) * (len(values) - 1) if project.call_count == 1 else None

    replacements = {
        "JointEvaluation": Mock(return_value=_Equations()),
        "redistributed_step": projection,
        "joint_jacobian": lambda model, values, *args, **kwargs: [
            [0.0] * len(values) for _ in range(7)
        ],
    }
    for name, replacement in replacements.items():
        monkeypatch.setitem(vars(joint_contact), name, replacement)
    if outcome == "miss":
        monkeypatch.setitem(
            vars(joint_contact),
            "screen_restoration",
            Mock(return_value=ContactResult("unresolved", 1)),
        )
    events: list[dict[str, Any]] = []

    def record(event: dict[str, Any]) -> None:
        """
        Charge witness preparation and logging before any transfer can escape the caller guard.
        """
        events.append(event)
        if event["status"] == "restoration_screen":
            if outcome == "budget":
                clock[0] = 0.36
            cancelled[0] = outcome == "cancel"
        if event["status"] == "material_restoration_prepared" and outcome == "late":
            clock[0] = 0.36

    def checkpoint() -> None:
        """
        Preserve source and cancellation failures as hard stops.
        """
        if cancelled[0]:
            raise InterruptedError("original source stop")

    yielded: list[RestorationHandoff] = []
    policy = (
        None
        if outcome == "default"
        else UnreflectedReturns(
            frozenset({3, selected}) if outcome == "repeated" else frozenset({3})
        )
    )

    def run() -> Any:
        """
        Keep the original numerical allowance and actual independently authored geometry.
        """
        return joint_contact.recover(
            source,
            _witness(6, 8),
            _gate(source),
            checkpoint,
            record,
            maximum_length_mm=source.material_length_mm,
            minimum_straight_mm=1e-5,
            remaining_pairs=512,
            maximum_cpu_seconds=0.35,
            maximum_seconds=2,
            maximum_updates=1 if outcome == "last_update" else 4,
            mode=MaterialGuidance(3),
            on_restoration_blocked=yielded.append,
            early_material_return=policy,
        )

    if outcome == "cancel":
        with pytest.raises(InterruptedError, match="source stop"):
            run()
        assert not yielded
        return
    result = run()
    assert result is not None and result.contact is None
    if outcome == "early":
        assert project.call_count == 1 and len(yielded) == 1
        assert yielded[0].stop_reason == "new_material_return"
        assert result.detail["newton_steps"] == 1
        assert result.detail["restoration_handoff_inverse_checks"] == 2
        prepared = next(e for e in events if e["status"] == "material_restoration_prepared")
        assert prepared["next_fold"] == selected
    elif outcome in ("budget", "late"):
        assert not yielded and result.detail["stop_reason"] == "phase_budget"
    elif outcome == "miss":
        assert not yielded and result.detail["stop_reason"] == "linear_projection_infeasible"
    else:
        assert project.call_count == 2 and len(yielded) == 1
        assert yielded[0].stop_reason == "linear_projection_infeasible"


def test_sequence_passes_frozen_return_history_and_debits_the_first_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A new return keeps prior signs and uses only the original allowance left after evidence preparation.
    """
    from experiments.experiment_ribbon_terminal_hardware import deviation_sequence
    from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
    from tests.test_ribbon_deviation_sequence import _gate as sequence_gate
    from tests.test_ribbon_deviation_sequence import _result

    source = _source()
    contact = _contact(source)
    assert contact.witness is not None
    selected = select_fold(source, contact.witness)
    assert selected is not None
    clock = [0.0]
    for name in ("process_time", "perf_counter"):
        monkeypatch.setitem(vars(deviation_sequence), name, lambda: clock[0])
    seen: list[dict[str, Any]] = []

    def stage(route: Any, *_args: Any, **options: Any) -> Any:
        """
        Check the solver boundary without inventing a physical success for open geometry.
        """
        seen.append(options)
        assert route is source
        assert isinstance(options["mode"], MaterialGuidance)
        if len(seen) == 1:
            assert options["mode"].selected_fold == 3
            assert options["early_material_return"].reflected_folds == frozenset({3})
            options["on_restoration_blocked"](
                RestorationHandoff(route, contact, "new_material_return")
            )
            clock[0] = 0.02
            return _result(route, newton=1, pairs=7)
        assert options["mode"].selected_fold == selected
        assert options["early_material_return"].reflected_folds == frozenset({3, selected})
        assert options["maximum_updates"] == 3 and options["remaining_pairs"] == 93
        assert options["maximum_cpu_seconds"] == pytest.approx(0.33)
        assert options["maximum_seconds"] == pytest.approx(1.98)
        return _result(route, newton=1, pairs=5)

    monkeypatch.setitem(vars(deviation_sequence), "recover_joints", stage)
    result = deviation_sequence.recover(
        source,
        ContactResult("penetration", 0, _witness(6, 8)),
        sequence_gate(source),
        lambda: None,
        lambda event: None,
        work=Work(4, 100, 0.35, 2),
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
    )
    assert len(seen) == 2 and result.contact is None
    assert result.detail["reflected_folds"] == sorted({3, selected})
    assert result.detail["iterations"] == 2 and result.detail["newton_steps"] == 2
    assert result.detail["contact_pairs"] == 12
