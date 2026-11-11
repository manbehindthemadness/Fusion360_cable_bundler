"""
Keep open-cap material continuation tied to actual current-pose evidence and original work.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import deviation_sequence, joint_contact
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import MaterialGuidance
from experiments.experiment_ribbon_terminal_hardware.incident_model import IncidentJoints
from experiments.experiment_ribbon_terminal_hardware.joint_handoff import JointHandoff
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from experiments.experiment_ribbon_terminal_hardware.restoration_handoff import RestorationHandoff
from experiments.experiment_ribbon_terminal_hardware.restoration_screen import screen
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_contact_refinement import _gate
from tests.test_ribbon_deviation_sequence import _pending, _result
from tests.test_ribbon_material_return import _witness


class _Equations:
    """
    Supply controlled decreasing cap merit while real material evidence follows the actual joint pose.
    """

    @staticmethod
    def equations(values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Keep the protocol test's algebraic outcome independent of target-distance convergence.
        """
        return (math.exp(-values[0]),) + (0.0,) * 6

    @staticmethod
    def admissible(values: tuple[float, ...]) -> bool:
        """
        Reject nonfinite test proposals before actual model placement.
        """
        return all(math.isfinite(value) for value in values)

    def constraints_changed(self) -> None:
        """
        Retain the controlled merit when actual independently measured constraints are added.
        """


def _source() -> FoldRoute:
    """
    Author a strict straight crossing followed by an unrelated fourth fold, with explicit open caps.
    """
    route = _route(
        (
            Straight(10),
            fold(2, 1.2, math.pi / 2, 0, 0),
            Straight(5),
            fold(2, 1.2, math.pi / 2, 0, 0),
            Straight(5),
            fold(2, 1.2, math.pi / 2, 0, 0),
            Straight(10),
            fold(2, 1.2, 0.2, 0.1, 1),
            Straight(3),
        )
    )
    return replace(route, targets=replace(route.targets, end=Vector3(99, 99, 99)))


def _contact(route: FoldRoute) -> ContactResult:
    """
    Measure strict occupied material with the real bounded negative screen, never a saved specimen.
    """
    result = screen(route, FlatProbe(), 32, lambda: None, lambda witness: True)
    assert result.status == "penetration" and result.witness is not None
    return result


def test_uncertified_handoff_revalidates_actual_material_without_weakening_closed_handoff() -> None:
    """
    Open geometry can carry a negative witness but cannot use the closed proposal contract.
    """
    route = _source()
    contact = _contact(route)
    state = RestorationHandoff(route, contact, "joint_no_descent")
    assert state.route is route and state.evidence is contact and cap_error(route) > 1
    with pytest.raises(ValueError, match="closed"):
        JointHandoff(route, contact)


@pytest.mark.parametrize("invalid", ("miss", "depth", "coordinates", "identity", "point", "stop"))
def test_unknown_or_stale_material_and_resource_stops_cannot_authorize_handoff(
    invalid: str,
) -> None:
    """
    Verify strict source, point, material coordinates and ordinary-stop provenance independently.
    """
    route = _source()
    contact = _contact(route)
    witness = contact.witness
    assert witness is not None
    reason: Any = "joint_no_descent"
    if invalid in ("miss", "depth"):
        contact = replace(
            contact, status="unresolved", limit="depth" if invalid == "depth" else None
        )
    elif invalid == "coordinates":
        contact = replace(contact, witness=replace(witness, first=(0.01, 0.0, 0.0)))
    elif invalid == "identity":
        contact = replace(contact, witness=replace(witness, pieces=(1, 0)))
    elif invalid == "point":
        contact = replace(contact, witness=replace(witness, point=Vector3(999, 999, 999)))
    else:
        reason = "phase_budget"
    with pytest.raises(ValueError):
        RestorationHandoff(route, contact, reason)


@pytest.mark.parametrize(
    "outcome", ("linear", "descent", "stale", "budget", "late_budget", "cancel", "miss")
)
def test_real_joint_entry_only_yields_unchanged_current_witness_after_an_ordinary_stop(
    monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """
    Mock only algebraic dispositions while real material placement, screening and witness validation run.
    """
    source = _source()
    clock = [0.0]
    cancelled = [False]
    for name in ("process_time", "perf_counter"):
        monkeypatch.setitem(vars(joint_contact), name, lambda: clock[0])
    calls = 0

    def project(
        _model: Any, values: tuple[float, ...], *_args: Any, **_kwargs: Any
    ) -> tuple[float, ...] | None:
        """
        Move once before a measured crossing, then select a controlled original stop disposition.
        """
        nonlocal calls
        calls += 1
        clock[0] = 0.36 if outcome == "budget" and calls > 1 else 0.01
        cancelled[0] = outcome == "cancel" and calls > 1
        if calls == 1 or (outcome == "stale" and calls == 2):
            return (0.001,) + (0.0,) * (len(values) - 1)
        return (0.0,) * len(values) if outcome == "descent" else None

    monkeypatch.setitem(vars(joint_contact), "JointEvaluation", Mock(return_value=_Equations()))
    monkeypatch.setitem(vars(joint_contact), "redistributed_step", project)
    monkeypatch.setitem(
        vars(joint_contact),
        "joint_jacobian",
        lambda model, values, *args, **kwargs: [[0.0] * len(values) for _ in range(7)],
    )
    screens = 0

    def measured(*args: Any, **kwargs: Any) -> ContactResult:
        """
        Use the actual original screen once, then model a miss without inventing another witness.
        """
        nonlocal screens
        screens += 1
        if outcome == "miss" or screens > 1:
            return ContactResult("unresolved", 1)
        return screen(*args, **kwargs)

    monkeypatch.setitem(vars(joint_contact), "screen_restoration", measured)
    yielded: list[RestorationHandoff] = []

    def record(event: dict[str, Any]) -> None:
        """
        Account preparation/recording time before the final unchanged resource guard.
        """
        if event["status"] == "material_restoration_prepared" and outcome == "late_budget":
            clock[0] = 0.36

    def checkpoint() -> None:
        """
        Propagate the original caller cancellation before any callback can run.
        """
        if cancelled[0]:
            raise InterruptedError("original source stop")

    options: dict[str, Any] = dict(
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=512,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=4,
        mode=MaterialGuidance(3),
        on_restoration_blocked=yielded.append,
    )
    if outcome == "cancel":
        with pytest.raises(InterruptedError, match="source"):
            joint_contact.recover(
                source, _witness(6, 8), _gate(source), checkpoint, record, **options
            )
        assert not yielded
        return
    result = joint_contact.recover(
        source, _witness(6, 8), _gate(source), checkpoint, record, **options
    )
    assert result is not None and result.contact is None
    expected = outcome in ("linear", "descent")
    assert len(yielded) == int(expected)
    if expected:
        assert result.detail["stop_reason"] == "material_restoration_handoff"
        assert yielded[0].stop_reason == (
            "joint_no_descent" if outcome == "descent" else "linear_projection_infeasible"
        )
        assert result.detail["restoration_handoff_inverse_checks"] == 2
    else:
        assert result.detail["stop_reason"] == (
            "phase_budget"
            if outcome in ("budget", "late_budget")
            else "linear_projection_infeasible"
        )
        assert result.detail["restoration_handoff_inverse_checks"] == (
            2 if outcome == "late_budget" else 0
        )


@pytest.mark.parametrize(
    "updates,claimed_clear,changed_targets",
    ((1, False, False), (4, False, False), (4, True, False), (4, False, True)),
)
def test_sequence_passes_uncertified_geometry_only_under_decreasing_original_work(
    monkeypatch: pytest.MonkeyPatch, updates: int, claimed_clear: bool, changed_targets: bool
) -> None:
    """
    Another return is selected from the actual crossing; no stage or cap acceptance is invented.
    """
    source = _source()
    gate = _gate(source)
    gate.measure.return_value = joint_contact.Report("clear", 1)
    contact = _contact(source)
    options_seen: list[dict[str, Any]] = []

    def stage(route: FoldRoute, *_args: Any, **options: Any) -> Any:
        """
        Simulate a checked partial handoff while preserving actual input targets and explicit work charges.
        """
        options_seen.append(options)
        if len(options_seen) == 1:
            handed = (
                replace(route, targets=replace(route.targets, end=Vector3(98, 99, 99)))
                if changed_targets
                else route
            )
            options["on_restoration_blocked"](
                RestorationHandoff(handed, contact, "joint_no_descent")
            )
        else:
            assert isinstance(options["mode"], MaterialGuidance)
            assert options["maximum_updates"] == updates - 1 and options["remaining_pairs"] == 95
            model = IncidentJoints(route, options["mode"].selected_fold)
            assert model.admissible(model.initial) and model.original.targets == source.targets
            reflected = model.route(model.initial)
            assert reflected is not None and model.preserves(reflected)
            assert max(map(abs, model.residual(model.initial))) > 0.0
            if claimed_clear:
                return _result(route, ContactResult("separated", 5))
        return _result(route)

    monkeypatch.setitem(vars(deviation_sequence), "recover_joints", stage)

    def run() -> Any:
        """
        Keep the same original targets and work for either a rejected or falsely claimed child result.
        """
        return deviation_sequence.recover(
            source,
            _pending(),
            gate,
            lambda: None,
            lambda e: None,
            work=Work(updates, 100, 0.35, 2),
            maximum_length_mm=source.material_length_mm,
            minimum_straight_mm=1e-5,
        )

    if claimed_clear or changed_targets:
        with pytest.raises(
            ArithmeticError, match="fixed targets" if changed_targets else "ordered caps"
        ):
            run()
        gate.certify.assert_not_called()
        return
    result = run()
    assert result.contact is None and result.detail["status"] == "unresolved"
    assert len(options_seen) == (1 if updates == 1 else 2)
