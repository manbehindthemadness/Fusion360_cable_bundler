"""
Preserve a buildable positive lead while reclosing the remaining original material coordinates.
"""

from __future__ import annotations

from math import inf
from typing import Any, Callable
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_feature_insertion.separation import Region, Side
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    ContactGuidance,
    ContactMotion,
    FeatureEvidence,
)
from experiments.experiment_ribbon_terminal_hardware.feature_plane import FeaturePlane, SignedJoints
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.native_slots import extensions
from experiments.experiment_ribbon_terminal_hardware.terminal_protection import Protection
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_contact_refinement import _gate
from tests.test_ribbon_native_slots import _Bounds


@pytest.mark.parametrize("scale", (1e-6, 1.0, 1e6))
@pytest.mark.parametrize("small_mm", (1e-9, 5e-6, 1e-5))
def test_small_positive_lead_gets_one_strict_native_floor_inside_original_bounds(
    scale: float, small_mm: float
) -> None:
    """
    Add only the representable minimum and leave unrelated coordinates and original domain intact.
    """
    source = _Bounds(((0.0, inf), (0.0, 4.0)))
    values = (small_mm / scale, 1.0)
    pinned = extensions(source, values, frozenset({0}), 1e-5, scale)
    assert pinned is not None and set(pinned) == {0}
    assert 1e-5 < pinned[0] * scale < 1.000001e-5
    assert values == (small_mm / scale, 1.0) and source.bounds(0) == (0.0, inf)


def test_small_extension_declines_original_upper_limit_and_rejects_non_slivers() -> None:
    """
    A geometric extension must remain inside original bounds and cannot target absent or normal slots.
    """
    assert extensions(_Bounds(((0.0, 9e-6),)), (5e-6,), frozenset({0}), 1e-5, 1) is None
    for value in (0.0, -1e-6, 2e-5, inf):
        with pytest.raises(ValueError, match="positive sub-native"):
            extensions(_Bounds(), (value,), frozenset({0}), 1e-5, 1)


@pytest.mark.parametrize("motion", (ContactMotion.STRAIGHT_SLOTS, ContactMotion.BEND_JOINTS))
@pytest.mark.parametrize("contact_status", ("separated", "unresolved"))
def test_real_reclosure_keeps_extended_lead_and_final_certificates_mandatory(
    monkeypatch: pytest.MonkeyPatch, motion: ContactMotion, contact_status: str
) -> None:
    """
    Reclose an authored two-fold cap system after lead extension, isolating physical gates with mocks.

    The material equations and projection are real. Mocked hardware/contact
    dispositions establish call ordering only, not independent geometry coverage.
    """
    source = _route(
        (Straight(5e-6), fold(2, 1.2, 1, 0, 1), Straight(3), fold(2, 1.2, -1, 0, 1), Straight(4))
    )
    terminal = _gate(source)
    terminal.hardware = Hardware.create(source.targets, Dimensions(10, 10, 10))
    report = Report("blocked", 1, Witness("start", 1, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0)))
    monkeypatch.setitem(vars(joint_contact), "member_planes", lambda *_args: [])

    def protect(
        model: SignedJoints,
        hardware: Hardware,
        _observed: list[FeaturePlane],
        _checkpoint: Callable[[], None],
    ) -> tuple[Protection, ...]:
        """
        Supply one inactive analytical inequality while preserving real material derivatives.
        """
        tag = Region(0, True)
        return (
            Protection(FeaturePlane(model, tag, (tag,), hardware.boxes[0], 0, Side.BEFORE), -100),
        )

    monkeypatch.setitem(vars(joint_contact), "prepare_terminal_protection", protect)
    terminal.certify.return_value = joint_contact.Report("clear", 1)
    contact = Mock(return_value=ContactResult(contact_status, 4))
    monkeypatch.setitem(vars(joint_contact), "inspect_contact", contact)
    events: list[dict[str, Any]] = []
    result = joint_contact.recover(
        source,
        report,
        terminal,
        lambda: None,
        events.append,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=4,
        mode=ContactGuidance((FeatureEvidence(source, report),), motion),
    )
    assert result is not None and result.route is not None
    assert (result.detail["status"] == "separated") is (contact_status == "separated")
    assert (result.contact is not None) is (contact_status == "separated")
    assert result.detail["native_sliver_extensions"] == 1
    checked_route = contact.call_args.args[0]
    assert checked_route.pieces[0].geometry.material_length_mm > 1e-5
    assert cap_error(checked_route) < 1e-7 and checked_route.targets is source.targets
    if contact_status == "unresolved":
        assert result.route is source
    assert result.detail["newton_steps"] >= 2
    assert result.detail["contact_pairs"] == 4 + result.detail["restoration_screen_pairs"]
    assert result.detail["contact_pairs"] <= 123
    assert "runway_minimization" not in result.detail
    assert sum(e["status"] == "native_sliver_extended" for e in events) == 1
    terminal.certify.assert_called_once()
    contact.assert_called_once()
