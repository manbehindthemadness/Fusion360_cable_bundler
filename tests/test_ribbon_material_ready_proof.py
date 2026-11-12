"""
Request actual physical proof after accepted angular motion without requiring guidance to vanish.
"""

from __future__ import annotations

from typing import Any, Literal
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.mating import fixed_fold_frames_match
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.check import Report, inspect
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    ContactGuidance,
    FeatureEvidence,
)
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.joint_evaluation import JointEvaluation
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_contact_refinement import _gate, _source


@pytest.mark.parametrize(
    ("hardware", "contact"),
    (
        ("clear", "separated"),
        ("unresolved", "separated"),
        ("clear", "penetration"),
        ("clear", "unresolved"),
    ),
)
@pytest.mark.parametrize("delayed_orientation", (False, True))
def test_actual_readiness_requests_one_proof_after_ordinary_negative_discovery(
    monkeypatch: pytest.MonkeyPatch,
    hardware: Literal["clear", "unresolved"],
    contact: str,
    delayed_orientation: bool,
) -> None:
    """
    Keep real cap-preserving translation; mock equations and independent certificate boundaries only.
    """
    source = _source()
    model = SignedJoints(source)
    terminal = _gate(source)
    terminal.hardware = Hardware.create(source.targets, Dimensions(10, 10, 10))
    evidence = inspect(source, terminal.hardware)
    assert evidence.status == "blocked" and evidence.witness is not None
    first, last = model.straight_indices[0], model.straight_indices[-1]
    delta = tuple(
        0.1 / model.scale if i in (first, last) else 0.0 for i in range(len(model.initial))
    )
    angle = next(i for i, index in enumerate(model.indices) if index % 4 == 1)
    if delayed_orientation:
        delta = tuple(-1e-9 if i == angle else value for i, value in enumerate(delta))
    initial_proposal = tuple(value + change for value, change in zip(model.initial, delta))
    assert model.admissible(initial_proposal)
    initial_pose = model.route(initial_proposal)
    assert initial_pose is not None
    assert (
        fixed_fold_frames_match(initial_pose.pieces, initial_pose.targets)
        is not delayed_orientation
    )

    def equations(_self: JointEvaluation, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Retain nonzero finite guidance after one actual cap-preserving accepted motion.
        """
        guidance = (
            1e-4
            if values[first] == model.initial[first]
            else 1e-8
            if not delayed_orientation or values[angle] != model.initial[angle]
            else 1e-9
        )
        return (0.0,) * 6 + (guidance,)

    monkeypatch.setattr(JointEvaluation, "equations", equations)
    steps: list[tuple[float, ...] | AssertionError] = [delta]
    if delayed_orientation:
        steps.append(tuple(1e-9 if i == angle else 0.0 for i in range(len(delta))))
    steps.append(AssertionError("Physical proof precedes another Newton step"))
    projector = Mock(side_effect=steps)
    monkeypatch.setitem(vars(joint_contact), "redistributed_step", projector)
    order: list[str] = []

    def negative(*_args: Any, **_kwargs: Any) -> ContactResult:
        """
        Record the ordinary discovery opportunity before proof scheduling.
        """
        order.append("negative")
        return ContactResult("unresolved", 7)

    def certified(*_args: Any, **_kwargs: Any) -> Report:
        """
        Keep the terminal certificate separate from readiness and contact measurement.
        """
        order.append("hardware")
        return Report(hardware, 2)

    monkeypatch.setitem(vars(joint_contact), "screen_restoration", negative)
    terminal.probe.return_value = Report("unresolved", 0)
    terminal.certify.side_effect = certified
    checker = Mock(return_value=ContactResult(contact, 11))
    monkeypatch.setitem(vars(joint_contact), "inspect_contact", checker)
    events: list[dict[str, Any]] = []
    result = joint_contact.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        events.append,
        maximum_length_mm=source.material_length_mm + 1,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=4,
        mode=ContactGuidance((FeatureEvidence(source, evidence),)),
    )
    expected = 2 if delayed_orientation else 1
    assert result is not None and projector.call_count == expected
    assert order == ["negative"] * expected + ["hardware"]
    request = next(e for e in events if e["status"] == "stalled_certificate_requested")
    assert request["original_stop"] == "material_ready"
    assert (
        result.detail["newton_steps"] == expected
        and result.detail["stalled_certificate_requests"] == 1
    )
    assert checker.call_count == int(hardware == "clear")
    if hardware == "clear":
        assert checker.call_args.kwargs["maximum_pairs"] == 123 - 7 * expected
    assert (result.contact is not None) is (hardware == "clear" and contact == "separated")
    position = events.index(request)
    assert not any(e["status"] in ("update", "constraint_added") for e in events[position + 1 :])
