"""
Find strict internal hardware intrusion without granting clearance to a focused material subset.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_feature_insertion.separation import Region, regions
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.check import Report, inspect
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import MaterialGuidance
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware, Terminal
from experiments.experiment_ribbon_terminal_hardware.moving_probe import moving_domain
from experiments.experiment_ribbon_terminal_hardware.probe_domain import ProbeDomain
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_feature_geometry_reuse import _plane
from tests.test_ribbon_restoration_handoff import _contact, _Equations
from tests.test_ribbon_terminal_hardware import _primitives, _straight


def test_focused_internal_intrusion_uses_original_indices_and_same_small_cell_allowance() -> None:
    """
    Reach an actual occupied member hidden behind unrelated root visits, without complete-route claims.
    """
    route = _primitives(
        (_straight(0, 0, 0, 10), _straight(-2, 0, 0, 1))
        + tuple(_straight(100 + index, 20, 20, 1) for index in range(40))
    )
    hardware = Hardware.create(route.targets, Dimensions(4, 4, 5))
    baseline = inspect(route, hardware, maximum_cells=32)
    domain = ProbeDomain(route, ((Terminal.START, 1),))
    focused = inspect(route, hardware, maximum_cells=32, probe_domain=domain)
    assert baseline.status == "unresolved" and baseline.cells_checked == 32
    assert focused.status == "blocked" and focused.cells_checked == 1
    witness = focused.witness
    assert witness is not None and witness.piece == 1 and witness.terminal == "start"
    assert -2 < witness.point.x < -1
    assert all(-1 < coordinate < 1 for coordinate in witness.box_coordinates[1:])


def test_subset_miss_cannot_certify_clearance_or_hide_an_unselected_intrusion() -> None:
    """
    Even a completed empty-space subset remains explicitly unmeasured for the whole route.
    """
    route = _primitives((_straight(0, 0, 0, 10), _straight(-2, 0, 0, 1), _straight(30, 0, 0, 1)))
    hardware = Hardware.create(route.targets, Dimensions(4, 4, 5))
    domain = ProbeDomain(route, ((Terminal.START, 2),))
    missed = inspect(route, hardware, probe_domain=domain)
    assert missed.status == "unresolved" and missed.witness is None and missed.cells_checked == 1
    assert "full clearance unmeasured" in missed.reason
    assert inspect(route, hardware).status == "blocked"


@pytest.mark.parametrize(
    "pairs",
    (
        (),
        ((Terminal.START, 0),) * 2,
        (("start", 0),),
        ((Terminal.END, True),),
        ((Terminal.END, 9),),
    ),
)
def test_probe_domain_rejects_invalid_duplicate_or_missing_material(pairs: Any) -> None:
    """
    Do not reinterpret invalid material identities before the shared checker starts.
    """
    route = _primitives((_straight(0, 0, 0, 10),))
    with pytest.raises(ValueError, match="unique existing"):
        ProbeDomain(route, pairs)


def test_stale_domain_cannot_transfer_even_to_an_equivalent_route_or_cached_clearance() -> None:
    """
    Validate exact source ownership before either direct checking or a shared Gate cache lookup.
    """
    route = _primitives((_straight(0, 0, 0, 10),))
    domain = ProbeDomain(route, ((Terminal.START, 0),))
    other = replace(route)
    hardware = Hardware.create(route.targets, Dimensions.scaled(route.targets))
    with pytest.raises(ValueError, match="exact immutable source"):
        inspect(other, hardware, probe_domain=domain)
    gate = Gate(route.targets, Mock(), Mock())
    assert gate.certify(other, "complete").status == "clear"
    with pytest.raises(ValueError, match="exact immutable source"):
        gate.probe(other, "stale", domain=domain)


def test_partial_probe_does_not_cache_clearance_or_renew_shared_gate_work() -> None:
    """
    Charge repeated negative-only misses before an independent complete final certificate.
    """
    route = _primitives((_straight(0, 0, 0, 10),))
    domain = ProbeDomain(route, ((Terminal.START, 0),))
    gate = Gate(route.targets, Mock(), Mock())
    assert gate.probe(route, "subset", domain=domain).status == "unresolved"
    assert gate.probe(route, "same_subset", domain=domain).status == "unresolved"
    assert gate.cells == 2 and gate.cache_hits == 0
    assert gate.certify(route, "full").status == "clear"
    assert gate.cells == 4
    gate.cells = 1024
    assert gate.probe(replace(route), "exhausted").status == "unresolved"
    assert gate.cells == 1024


def test_actual_moving_domain_uses_stable_changed_slots_and_only_owned_hardware_guidance() -> None:
    """
    Existing complete member guidance and own mating material do not consume optional discovery.
    """
    plane = _plane()
    model = plane.model
    values = (model.initial[0] + 0.01,) + model.initial[1:]
    route = model.route(values)
    assert route is not None
    hardware = Hardware.create(route.targets, Dimensions.scaled(route.targets))
    covered = replace(plane, box=hardware.boxes[1], members=(Region(2, True),))
    domain = moving_domain(route, model, values, hardware, (covered,), Mock())
    assert domain is not None and domain.source is route and domain.terminals[0] is Terminal.END
    tags = regions(route)
    assert (Terminal.END, tags.index(Region(2, True))) not in domain.pairs
    assert (Terminal.END, len(route.pieces) - 1) not in domain.pairs
    assert (Terminal.START, 0) not in domain.pairs
    assert (Terminal.START, tags.index(Region(2, True))) in domain.pairs
    assert len(set(domain.pairs)) == len(domain.pairs)
    foreign = _plane()
    unowned = moving_domain(route, model, values, hardware, (foreign,), Mock())
    assert unowned is not None and (Terminal.END, tags.index(Region(2, True))) in unowned.pairs
    assert moving_domain(route, model, model.initial, hardware, (), Mock()) is None
    initial = model.route(model.initial)
    assert initial is not None
    assert moving_domain(initial, model, model.initial, hardware, (), Mock()) is None


def test_probe_keeps_original_cancellation_and_unattempted_gate_accounting() -> None:
    """
    A caller source/resource error must propagate rather than becoming a negative miss.
    """
    route = _primitives((_straight(0, 0, 0, 10),))
    domain = ProbeDomain(route, ((Terminal.START, 0),))
    gate = Gate(route.targets, Mock(side_effect=InterruptedError("original source")), Mock())
    with pytest.raises(InterruptedError, match="original source"):
        gate.probe(route, "cancel", domain=domain)
    assert gate.cells == 0


def test_local_correction_deadline_propagates_during_cell_traversal() -> None:
    """
    The global Gate allowance cannot outlive the caller's shorter remaining correction clock.
    """
    route = _primitives((_straight(0, 0, 0, 10),))
    domain = ProbeDomain(route, ((Terminal.START, 0),))
    gate = Gate(route.targets, Mock(), Mock())
    guard = Mock(side_effect=(None, None, TimeoutError("local correction clock")))
    with pytest.raises(TimeoutError, match="local correction clock"):
        gate.probe(route, "local_deadline", domain=domain, checkpoint=guard)
    assert guard.call_count == 3 and gate.cells == 1
    assert gate.detail()["checks"] == 0


@pytest.mark.parametrize("outcome", ("blocked", "miss", "late"))
def test_real_joint_retains_actual_internal_hardware_evidence_before_another_projection(
    monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """
    Real placement, negative hardware checking and feature binding surround controlled optimization steps.

    This authored crossing is a mechanism control, not accepted geometry. Only
    an actual strict hardware report may add guidance; a miss or late report
    cannot grant clearance, another correction allowance or a native claim.
    """
    source = _route(
        (
            Straight(10),
            fold(2, 1.2, math.pi, 0, 1),
            Straight(12),
            fold(2, 1.2, math.pi, 0, 1),
            Straight(10),
        )
    )
    contact = _contact(source)
    assert contact.witness is not None
    terminal = Gate(source.targets, Mock(), Mock())
    terminal.hardware = Hardware.create(source.targets, Dimensions(20, 20, 20))
    clock = [0.0]
    for name in ("process_time", "perf_counter"):
        monkeypatch.setitem(vars(joint_contact), name, lambda: clock[0])
    monkeypatch.setitem(vars(joint_contact), "JointEvaluation", Mock(return_value=_Equations()))
    monkeypatch.setitem(vars(joint_contact), "prepare_terminal_protection", lambda *_: ())
    monkeypatch.setitem(
        vars(joint_contact), "screen_restoration", Mock(return_value=ContactResult("unresolved", 0))
    )
    project = Mock()

    def projection(
        _model: Any, values: tuple[float, ...], *_args: Any, **_kwargs: Any
    ) -> tuple[float, ...] | None:
        """
        Accept one bounded open-cap translation, then decline without another geometry search.
        """
        project(values)
        return (0.001,) + (0.0,) * (len(values) - 1) if project.call_count == 1 else None

    monkeypatch.setitem(vars(joint_contact), "redistributed_step", projection)
    original_probe = terminal.probe

    def probe(*args: Any, **kwargs: Any) -> Report:
        """
        Keep the actual occupied-member checker except an explicit inconclusive boundary control.
        """
        report = Report("unresolved", 1) if outcome == "miss" else original_probe(*args, **kwargs)
        if outcome != "miss":
            assert report.status == "blocked" and report.witness is not None
        if outcome == "late":
            clock[0] = 0.36
        return report

    observed = Mock(side_effect=probe)
    monkeypatch.setattr(terminal, "probe", observed)
    result = joint_contact.recover(
        source,
        contact.witness,
        terminal,
        Mock(),
        Mock(),
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=2,
        mode=MaterialGuidance(1),
    )
    assert result is not None and result.contact is None
    assert result.detail["moving_hardware_probe_checks"] == 1
    assert result.detail["moving_hardware_probe_constraints"] == int(outcome == "blocked")
    assert result.detail["newton_steps"] == 1
    assert observed.call_args.kwargs["domain"].source is observed.call_args.args[0]
    assert callable(observed.call_args.kwargs["checkpoint"])
    if outcome == "late":
        assert result.detail["stop_reason"] == "phase_budget" and project.call_count == 1
