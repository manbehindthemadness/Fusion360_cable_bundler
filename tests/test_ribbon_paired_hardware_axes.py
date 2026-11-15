"""
Verify complete-member axis transfer without changing physical identity or acceptance.
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_feature_insertion.separation import Region, Side
from experiments.experiment_ribbon_fold_route.geometry import Pose
from experiments.experiment_ribbon_paired_return import hardware_axes
from experiments.experiment_ribbon_paired_return.allocation import HardwareRow
from experiments.experiment_ribbon_paired_return.native_model import NativeJoints
from experiments.experiment_ribbon_terminal_hardware.feature_plane import FeaturePlane
from experiments.experiment_ribbon_terminal_hardware.model import Box, Dimensions, Terminal
from tests.test_ribbon_pair_family_motion import _route


def _row(scale: float, sign: int, terminal: Terminal) -> HardwareRow:
    """
    Place an analytical finite box far from a real complete oblique material fold.

    This standalone bound test uses explicit geometry, not a gym solver case or
    claimed connector installation. All dimensions scale together.
    """
    model = NativeJoints(_route(scale, sign), 1e-5 * scale)
    box = Box(
        terminal,
        Pose(Vector3(-100 * scale, -50 * scale, -30 * scale), Vector3(1, 0, 0), Vector3(0, 1, 0)),
        Dimensions(scale, scale, scale),
    )
    member = Region(1, False)
    return HardwareRow(FeaturePlane(model, member, (member,), box, 1, Side.AFTER))


@pytest.mark.parametrize("scale", [0.1, 1.0, 100.0])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("terminal", list(Terminal))
def test_better_axis_preserves_complete_bound_and_is_stable(
    scale: float, sign: int, terminal: Terminal
) -> None:
    """
    Preserve identity and strict gap across scale, fold reversal and both terminals.
    """
    row = _row(scale, sign, terminal)
    model = row.plane.model
    values = model.initial
    checkpoint = Mock()
    assert row(values) < 0
    refreshed = hardware_axes.reorient(row, values, checkpoint)
    assert refreshed is not row and refreshed(values) < row(values)
    assert refreshed.plane.model is model and refreshed.plane.box is row.plane.box
    assert refreshed.plane.reference == row.plane.reference
    assert refreshed.plane.members == row.plane.members
    assert refreshed.plane.minimum_gap_mm == row.plane.minimum_gap_mm
    assert hardware_axes.reorient(refreshed, values, checkpoint) is refreshed
    assert row.plane.family == 1 and row.plane.side is Side.AFTER
    assert checkpoint.call_count == 4


@pytest.mark.parametrize("reason", ["violated", "mating", "grouped"])
def test_ineligible_bound_does_not_enumerate_another_axis(
    monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    """
    Do not trade violated guidance, fixed mating topology or a grouped member for an easier bound.
    """
    row = _row(1, 1, Terminal.START)
    if reason == "violated":
        row = HardwareRow(replace(row.plane, side=Side.BEFORE))
        assert row(row.plane.model.initial) > 0
    elif reason == "mating":
        member = Region(0, True)
        row = HardwareRow(replace(row.plane, reference=member, members=(member,)))
        assert row.plane.mating_straight
    else:
        row = HardwareRow(replace(row.plane, members=(row.plane.reference, Region(1, True))))
    selector = Mock(side_effect=AssertionError("must not enumerate"))
    monkeypatch.setitem(vars(hardware_axes), "member_planes", selector)
    assert hardware_axes.reorient(row, row.plane.model.initial, lambda: None) is row
    assert not selector.called


def test_cancelled_or_corrupted_selection_cannot_transfer_a_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Propagate cancellation and reject a selector that changes identity rather than silently dropping it.
    """
    row = _row(1, 1, Terminal.START)
    checkpoint = Mock(side_effect=RuntimeError("source changed"))
    with pytest.raises(RuntimeError, match="source changed"):
        hardware_axes.reorient(row, row.plane.model.initial, checkpoint)
    monkeypatch.setitem(vars(hardware_axes), "member_planes", Mock(return_value=[]))
    with pytest.raises(ArithmeticError, match="one complete member"):
        hardware_axes.reorient(row, row.plane.model.initial, lambda: None)
    other = replace(row.plane, reference=Region(2, False))
    monkeypatch.setitem(vars(hardware_axes), "member_planes", Mock(return_value=[other]))
    with pytest.raises(ArithmeticError, match="physical member"):
        hardware_axes.reorient(row, row.plane.model.initial, lambda: None)


def test_discovery_refreshes_once_without_spending_work_or_changing_other_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep source protections, material suffix, evidence and original ledger while axes refresh.

    Negative probing is doubled to no domain; complete member axis geometry is
    real. This tests guidance ownership, never a physical-clearance certificate.
    """
    from experiments.experiment_ribbon_paired_return import discovery
    from experiments.experiment_ribbon_paired_return.allocation import MaterialRow
    from experiments.experiment_ribbon_paired_return.ledger import Ledger
    from experiments.experiment_ribbon_terminal_hardware.model import Hardware
    from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
    from experiments.experiment_ribbon_terminal_hardware.terminal_protection import Protection

    row = _row(1, 1, Terminal.START)
    model = row.plane.model
    assert isinstance(model, NativeJoints)
    values = list(model.initial)
    values[0] += 0.01
    coordinates = tuple(values)
    route = model.route(coordinates)
    assert route is not None
    gate = Mock(hardware=Hardware.create(route.targets, Dimensions.scaled(route.targets)))
    ledger = Ledger(Work(1, 2048, 0.35, 2, 6), 0, lambda: None)
    ledger.start_action()
    ledger.start_newton()
    events = []
    features = {}
    context = discovery.Discovery(gate, features, ledger, events.append)
    context.begin(model, ledger)
    monkeypatch.setitem(vars(discovery), "moving_domain", Mock(return_value=None))
    protection = Protection(row.plane, 0)
    material = MaterialRow(Mock(), model.scale)
    retained = (protection, row, material)
    result = context.scan(model, route, coordinates, retained)
    assert result.stop is None and len(result.rows) == 3
    assert result.rows[0] is protection and result.rows[-1] is material
    assert isinstance(result.rows[1], HardwareRow) and result.rows[1] is not row
    assert not features and context.latest is None and context.last_proof is None
    assert (ledger.updates, ledger.newton_steps, ledger.roots, ledger.pairs) == (1, 1, 0, 0)
    assert len(events) == 1 and events[0]["stage"] == "paired_hardware_axis"
    assert events[0]["new_gap_mm"] > events[0]["old_gap_mm"]
    repeated = context.scan(model, route, coordinates, result.rows)
    assert repeated.rows is result.rows and len(events) == 1 and not gate.probe.called
