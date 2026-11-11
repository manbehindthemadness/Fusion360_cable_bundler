"""
Advance measured cap closure to ordinary certificates without weakening their contracts.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Literal
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.cap_completion import ordered_caps_complete
from experiments.experiment_ribbon_terminal_hardware.check import Report, inspect
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.joint_evaluation import JointEvaluation
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_contact_refinement import _gate


@pytest.mark.parametrize("scale", (0.5, 1.0, 100.0))
@pytest.mark.parametrize("offset", (1e-10, 1e-8, 2e-7))
def test_actual_ordered_cap_contract_is_independent_of_normalized_progress(
    scale: float, offset: float
) -> None:
    """
    Measure authored endpoint error at three sizes rather than accepting a normalized proxy.
    """
    source = _route(
        (Straight(2 * scale), fold(2 * scale, 1.2, 0.8, 0.2, scale), Straight(3 * scale))
    )
    shifted = replace(
        source,
        targets=replace(
            source.targets, end=source.targets.end.translated(Vector3(0, 0, 1), offset)
        ),
    )
    model = SignedJoints(shifted)
    residual = model.residual(model.initial) + (-1.0,)
    assert max(abs(term) for term in residual[:6]) > 1e-13
    assert ordered_caps_complete(shifted, residual) is (offset < 1e-7)


@pytest.mark.parametrize("endpoint", ("start", "end"))
@pytest.mark.parametrize("frame", ("tangent", "width"))
def test_complete_ordered_frames_cannot_be_hidden_by_small_normalized_terms(
    endpoint: str, frame: str
) -> None:
    """
    Reject opposite directions even when an external progress equation claims zero.
    """
    source = _route((Straight(2), fold(2, 1.2, 0.8, 0.2, 1), Straight(3)))
    name = endpoint + "_" + frame
    vector = getattr(source.targets, name)
    changed = replace(
        source, targets=replace(source.targets, **{name: Vector3(-vector.x, -vector.y, -vector.z)})
    )
    assert not ordered_caps_complete(changed, (0.0,) * 7)


@pytest.mark.parametrize(
    "terms",
    (
        (0.0,) * 5,
        (math.nan,) + (0.0,) * 6,
        (0.0,) * 6 + (math.inf,),
        (0.0,) * 6 + (1e-13,),
        (0.0,) * 6 + (1e-8,),
    ),
)
def test_invalid_or_violated_equations_cannot_advance_to_certification(
    terms: tuple[float, ...],
) -> None:
    """
    Retain the original strict inequality threshold and fail closed on missing data.
    """
    assert not ordered_caps_complete(_route((Straight(2),)), terms)


def test_small_center_frame_error_does_not_hide_ordered_side_lane_displacement() -> None:
    """
    A wide profile must meet the same positional contract at both actual outer lanes.
    """
    source = _route((Straight(2),))
    targets = replace(
        source.targets, lines=101, end_width=Vector3(0, math.cos(1e-8), math.sin(1e-8))
    )
    assert not ordered_caps_complete(replace(source, targets=targets), (0.0,) * 7)


@pytest.mark.parametrize(
    "hardware_status,contact_status",
    (("clear", "separated"), ("unresolved", "separated"), ("clear", "unresolved")),
)
def test_completed_actual_caps_reach_but_never_replace_physical_certificates(
    monkeypatch: pytest.MonkeyPatch,
    hardware_status: Literal["clear", "unresolved"],
    contact_status: str,
) -> None:
    """
    Model a stationary progress residual with real prepared geometry and strict external boundaries.
    """
    source = _route((Straight(0.25), fold(2, 1.2, math.pi, 0.2, 1), Straight(3)))
    terminal = _gate(source)
    terminal.hardware = Hardware.create(source.targets, Dimensions(10, 10, 10))
    evidence = inspect(source, terminal.hardware)
    assert evidence.status == "blocked"
    terminal.measure.return_value = Report(hardware_status, 1)

    def equations(_self: JointEvaluation, _values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Represent a normalized cap metric that cannot improve below its numerical residual.
        """
        return (1e-10,) + (0.0,) * 5 + (-1.0,)

    monkeypatch.setattr(JointEvaluation, "equations", equations)
    projector = Mock(return_value=None)
    contact = Mock(return_value=ContactResult(contact_status, 7))
    monkeypatch.setitem(vars(joint_contact), "quality_step", projector)
    monkeypatch.setitem(vars(joint_contact), "inspect_contact", contact)
    result = joint_contact.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        lambda _: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=4,
    )
    assert result is not None
    terminal.measure.assert_called_once()
    projector.assert_not_called()
    assert result.detail["ordered_cap_completions"] == 1
    if hardware_status != "clear":
        assert result.contact is None
        contact.assert_not_called()
    else:
        contact.assert_called_once()
        assert result.detail["contact_pairs"] == 7
        assert (result.contact is not None) is (contact_status == "separated")
