"""
Allow necessary straight-travel growth through unchanged cap closure and final physical gates.
"""

from __future__ import annotations

from typing import Callable
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    ContactGuidance,
    ContactMotion,
    FeatureEvidence,
)
from experiments.experiment_ribbon_terminal_hardware.feature_plane import FeaturePlane, SignedJoints
from experiments.experiment_ribbon_terminal_hardware.model import Hardware
from tests.test_ribbon_contact_refinement import _gate, _source


@pytest.mark.parametrize("contact_status", ("separated", "unresolved"))
def test_real_fixed_bend_projection_keeps_necessary_extension_and_requires_final_proof(
    monkeypatch: pytest.MonkeyPatch, contact_status: str
) -> None:
    """
    Extend an authored hairpin's two runways equally to retain both caps and unchanged bend geometry.

    Real cap derivatives, runway minimization and nonlinear closure determine
    motion. A mocked linear member inequality requests a quarter-millimeter
    offset; physical gate dispositions verify ordering, not geometry coverage.
    """
    source = _source(0.0)
    terminal = _gate(source)
    report = Report("blocked", 1, Witness("start", 1, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0)))

    def member_planes(
        _planes: list[FeaturePlane], model: SignedJoints, _values: tuple[float, ...]
    ) -> list[FeaturePlane]:
        """
        Supply an independent affine clearance condition that requires positive net runway travel.
        """
        member = Mock(spec=FeaturePlane)
        target = model.initial[0] + 0.25 / model.scale
        member.gap.side_effect = lambda values: values[0] - target
        return [member]

    def protections(
        _model: SignedJoints,
        _hardware: Hardware,
        _observed: list[FeaturePlane],
        _checkpoint: Callable[[], None],
    ) -> tuple[joint_contact.Protection, ...]:
        """
        Isolate the single analytical member constraint from unrelated terminal geometry.
        """
        return ()

    monkeypatch.setitem(vars(joint_contact), "member_planes", member_planes)
    monkeypatch.setitem(vars(joint_contact), "prepare_terminal_protection", protections)
    expansion = Mock(side_effect=AssertionError("A feasible straight extension must be attempted"))
    monkeypatch.setitem(vars(joint_contact), "expand_hardware", expansion)
    contact = Mock(return_value=ContactResult(contact_status, 4))
    monkeypatch.setitem(vars(joint_contact), "inspect_contact", contact)
    events: list[dict[str, object]] = []
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
        mode=ContactGuidance((FeatureEvidence(source, report),), ContactMotion.ADAPTIVE_HARDWARE),
    )
    assert result is not None
    contact.assert_called_once()
    checked = contact.call_args.args[0]
    assert checked.material_length_mm > source.material_length_mm + 0.49
    assert checked.targets is source.targets and cap_error(checked) < 1e-7
    assert [p.geometry for p in checked.pieces if isinstance(p.geometry, CylindricalFold)] == [
        p.geometry for p in source.pieces if isinstance(p.geometry, CylindricalFold)
    ]
    assert (result.detail["status"] == "separated") is (contact_status == "separated")
    assert (result.contact is not None) is (contact_status == "separated")
    assert not result.detail["hardware_domain_expanded"]
    assert result.detail["contact_pairs"] == 4 and result.detail["newton_steps"] <= 6
    terminal.certify.assert_called_once()
    expansion.assert_not_called()
