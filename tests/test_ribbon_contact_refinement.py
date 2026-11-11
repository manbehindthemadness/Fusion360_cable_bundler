"""
Check uncertain flat-region guidance and coupled hardware refinement on analytical material controls.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import dot
from experiments.experiment_ribbon_feature_insertion.separation import Side, locate
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import deviation_refinement, joint_contact
from experiments.experiment_ribbon_terminal_hardware.check import Report, inspect
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    ContactGuidance,
    ContactMotion,
    FeatureEvidence,
    IncidentGuidance,
)
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.flat_separation import (
    FlatSeparation,
    flat_prism,
    flat_span,
)
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.material_constraint import MaterialConstraint
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.test_ribbon_aesthetic import _route


def _source(bank: float = 0.0) -> FoldRoute:
    """
    Supply a closed analytical hairpin with occupied fold leads and separated end straights.
    """
    return _route((Straight(0.25), fold(2, 1.2, math.pi, bank, 1), Straight(3)))


def _depth(first: int = 1, second: int = 2) -> ContactResult:
    """
    Model the checker boundary with two unresolved cells, without a penetration witness.
    """
    return ContactResult(
        "unresolved",
        7,
        unresolved_pieces=(first, second),
        limit="depth",
        unresolved_regions=(
            Cell(first, Span(0.01, 0.02), Span(-0.05, 0.05), Span(-0.1, 0.1)),
            Cell(second, Span(0.25, 0.5), Span(-0.05, 0.05), Span(-0.1, 0.1)),
        ),
    )


def _gate(source: FoldRoute) -> Mock:
    """
    Keep real scaled hardware and mock only the external certificate boundary.
    """
    gate = Mock(spec=Gate)
    gate.hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    gate.certify.return_value = Report("clear", 1)
    return gate


@pytest.mark.parametrize("bank", (0.0, -0.3, 0.4))
def test_depth_cells_guide_complete_flat_phases_without_becoming_penetration(bank: float) -> None:
    """
    Classify the entire uncertain rectangle and enclose full material regions on both sides.
    """
    source = _source(bank)
    model = SignedJoints(source)
    evidence = _depth()
    bound = FlatSeparation.from_measurement(model, source, evidence)
    assert bound is not None and evidence.witness is None and evidence.status == "unresolved"
    assert tuple(part.phase for part in bound.parts) == (FlatPhase.BEFORE, FlatPhase.STRAIGHT)
    for tag, part in zip(bound.pair, bound.parts):
        assert (part.low_q, part.high_q) == (-source.half_width_mm, source.half_width_mm)
        assert part.half_height >= source.targets.diameter_mm / 2
        piece = locate(source, model.pieces(model.initial), tag)
        points, _, _ = flat_prism(piece, part)
        projections = tuple(dot(p, bound.axis) for p in points)
        assert flat_span(piece, part, bound.axis) == pytest.approx(
            (min(projections), max(projections))
        )


@pytest.mark.parametrize(
    "invalid", ("mixed", "curved", "width", "height", "nan", "reversed", "identity", "pairs")
)
def test_unsupported_or_malformed_uncertainty_never_fabricates_a_flat_region(invalid: str) -> None:
    """
    Decline unsupported phase/interval evidence before joint motion or certification.
    """
    source = _source(0.3)
    evidence = _depth()
    assert evidence.unresolved_regions is not None
    first, second = evidence.unresolved_regions
    if invalid == "mixed":
        first = replace(first, u=Span(0, 1))
    elif invalid == "curved":
        first = replace(first, u=Span(0.45, 0.55))
    elif invalid == "width":
        second = replace(second, q=Span(-1, 1))
    elif invalid == "height":
        second = replace(second, height=Span(-1, 1))
    elif invalid == "nan":
        second = replace(second, u=Span(math.nan, 0.5))
    elif invalid == "reversed":
        second = replace(second, u=Span(0.7, 0.5))
    elif invalid == "identity":
        second = replace(second, piece=0)
    else:
        evidence = replace(evidence, limit="pairs")
    evidence = replace(evidence, unresolved_regions=(first, second))
    assert FlatSeparation.from_measurement(SignedJoints(source), source, evidence) is None


@pytest.mark.parametrize("motion", (ContactMotion.STRAIGHT_SLOTS, ContactMotion.BEND_JOINTS))
@pytest.mark.parametrize("material_clear", (False, True))
def test_initial_projection_retains_material_and_hardware_constraints_together(
    monkeypatch: pytest.MonkeyPatch,
    motion: ContactMotion,
    material_clear: bool,
) -> None:
    """
    Inspect real cap/feature equations at an analytical intrusion, without solving a saved layout.
    """
    source = _source()
    gate = _gate(source)
    gate.hardware = Hardware.create(source.targets, Dimensions(10, 10, 10))
    report = inspect(source, gate.hardware)
    assert report.status == "blocked" and report.witness is not None
    captured: list[tuple[float, ...]] = []

    def stop_projection(*args: Any, **_kwargs: Any) -> None:
        """
        Observe the first simultaneous linearized system, then decline motion.
        """
        captured.append(args[3])
        if motion is ContactMotion.STRAIGHT_SLOTS:
            assert all(i % 4 == 0 for i in args[0].indices)

    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.joint_contact."
        + ("shortest_run_step" if motion is ContactMotion.STRAIGHT_SLOTS else "redistributed_step"),
        stop_projection,
    )
    events: list[dict[str, Any]] = []
    result = joint_contact.recover(
        source,
        ContactResult("separated", 7) if material_clear else _depth(),
        gate,
        lambda: None,
        events.append,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=1,
        mode=ContactGuidance((FeatureEvidence(source, report),), motion),
    )
    assert result is not None and result.route is source and result.contact is None
    started = events[0]
    assert started["initial_flat_constraints"] == int(not material_clear)
    assert started["initial_hardware_members"] > 0
    protections = started["terminal_protections"]
    assert protections
    assert {item["terminal"] for item in protections} | {report.witness.terminal} == {
        "start",
        "end",
    }
    assert captured and len(captured[0]) == (
        6 + started["initial_hardware_members"] + len(protections) + int(not material_clear)
    )
    assert result.detail["method"] == "coupled_contact_refinement"
    assert result.detail["flat_constraints"] == int(not material_clear)
    assert result.detail["newton_steps"] == 0
    gate.certify.assert_not_called()


@pytest.mark.parametrize("status", ("separated", "unresolved", "penetration"))
def test_motion_guidance_cannot_substitute_for_strict_final_contact(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    """
    Even initially separated guidance requires route-bound refined hardware and complete contact proof.
    """
    source = _source()
    gate = _gate(source)
    checker = Mock(return_value=ContactResult(status, 13))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.joint_contact.inspect_contact", checker
    )
    result = joint_contact.recover(
        source,
        _depth(0, 2),
        gate,
        lambda: None,
        lambda e: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=1,
        mode=ContactGuidance(),
    )
    assert result is not None and (result.contact is not None) is (status == "separated")
    gate.certify.assert_called_once()
    checker.assert_called_once()
    assert gate.certify.call_args.args[0] is checker.call_args.args[0]
    assert checker.call_args.kwargs["maximum_pairs"] == 123
    assert result.detail["contact_pairs"] == 13


def test_hardware_preparation_consumes_the_same_remaining_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A spent preparation budget cannot start or renew a nonlinear correction.
    """
    source = _source()
    clock = [0.0]
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation_sequence.process_time",
        lambda: clock[0],
    )
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation_sequence.perf_counter",
        lambda: clock[0],
    )
    gate = _gate(source)

    def exhausted(*_args: Any) -> Report:
        """
        Consume the entire allocation at the mocked hardware boundary.
        """
        clock[0] = 0.2
        return Report("clear", 1)

    gate.measure.side_effect = exhausted
    nonlinear = Mock(side_effect=AssertionError("No renewed allocation"))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation_sequence.recover_joints",
        nonlinear,
    )
    result = deviation_refinement.refine(
        source,
        _depth(),
        gate,
        lambda: None,
        lambda e: None,
        work=Work(1, 123, 0.1, 1),
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and result.contact is None
    assert result.detail["stop_reason"] == "phase_budget"
    nonlinear.assert_not_called()


def test_contact_guidance_rejects_guessed_hardware_evidence() -> None:
    """
    Empty evidence adds no plane; a retained report must actually demonstrate intrusion.
    """
    source = _source()
    with pytest.raises(ValueError, match="actual intrusion"):
        ContactGuidance((FeatureEvidence(source, Report("unresolved", 5)),))


@pytest.mark.parametrize("bank", (-0.3, 0.0, 0.4))
def test_strict_curved_guidance_encloses_entire_pieces_instead_of_witness_patch(
    bank: float,
) -> None:
    """
    A mocked strict crossing enables shared complete-piece projection, retaining material identities.
    """
    source = _source(bank)
    model = SignedJoints(source)
    point = source.pieces[1].surface(0.5, 0)[0]
    witness = Penetration((0, 1), (0.5, 0, 0), (0.5, 0, 0), point)
    evidence = ContactResult("penetration", 3, witness)
    assert FlatSeparation.from_measurement(model, source, evidence) is None
    bound = MaterialConstraint.create(model, source, evidence)
    assert bound is not None and not bound.parts
    assert bound.pair[0].straight and not bound.pair[1].straight
    for side in (Side.BEFORE, Side.AFTER):
        assert math.isfinite(bound.gap(model.initial, side))
    mixed = replace(
        _depth(),
        unresolved_regions=(
            Cell(1, Span(0, 1), Span(-0.05, 0.05), Span(-0.1, 0.1)),
            Cell(2, Span(0.25, 0.5), Span(-0.05, 0.05), Span(-0.1, 0.1)),
        ),
    )
    assert MaterialConstraint.create(model, source, mixed) is None


def test_new_curved_contact_retains_the_prior_flat_constraint_in_same_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    After the strict checker reports a new curved pair, both material bounds remain active together.
    """
    source = _source()
    gate = _gate(source)
    witness = Penetration((0, 1), (0.5, 0, 0), (0.5, 0, 0), source.pieces[1].surface(0.5, 0)[0])
    checker = Mock(return_value=ContactResult("penetration", 11, witness))
    captured: list[tuple[float, ...]] = []

    def stop_projection(*args: Any, **_kwargs: Any) -> None:
        """
        Capture the two simultaneous material inequalities, without a physical solve claim.
        """
        captured.append(args[3])

    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.joint_contact.inspect_contact", checker
    )
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.joint_contact.redistributed_step",
        stop_projection,
    )
    result = joint_contact.recover(
        source,
        _depth(0, 2),
        gate,
        lambda: None,
        lambda e: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=1,
        mode=ContactGuidance(),
    )
    assert result is not None and result.contact is None and result.route is source
    assert result.detail["flat_constraints"] == 2 and result.detail["contact_pairs"] == 11
    assert result.detail["terminal_protection_constraints"] > 0
    assert captured and len(captured[0]) == 8 + result.detail["terminal_protection_constraints"]


@pytest.mark.parametrize("incident", (False, True))
def test_angular_physical_entries_share_bounded_cap_restoration(
    monkeypatch: pytest.MonkeyPatch, incident: bool
) -> None:
    """
    Use the same existing projector/evidence without replacing final certificates or allocating motion.
    """
    source = _source(0.2)
    gate = _gate(source)
    gate.hardware = Hardware.create(source.targets, Dimensions(10, 10, 10))
    report = inspect(source, gate.hardware)
    assert report.status == "blocked" and report.witness is not None
    retained = (FeatureEvidence(source, report),)
    mode = IncidentGuidance(0, retained) if incident else ContactGuidance(retained)
    projector = Mock(return_value=None)
    monkeypatch.setitem(vars(joint_contact), "redistributed_step", projector)
    result = joint_contact.recover(
        source,
        report if incident else ContactResult("separated", 7),
        gate,
        lambda: None,
        lambda event: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=1,
        mode=mode,
    )
    assert result is not None and result.route is source and result.contact is None
    assert projector.call_count == 1
    assert result.detail["linear_projection"] == "redistributed_cap_restoration"
    assert result.detail["motion_regularization"] == "cap_step_normalized_merit_squared"
    assert result.detail["newton_steps"] == result.detail["contact_pairs"] == 0
    gate.certify.assert_not_called()
