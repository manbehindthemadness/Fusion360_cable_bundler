"""
Verify genuine endpoint-preserving spatial deviation and its one bounded exact-construction action.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any, Callable, Literal
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, restore, snapshot
from experiments.experiment_ribbon_feature_insertion.allocation import fit as fit_exact
from experiments.experiment_ribbon_feature_insertion.deviation_guide import DeviationGuide
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_spline_guide.guide import Guide
from experiments.experiment_ribbon_terminal_hardware import deviation
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.deviation_chain import aim
from experiments.experiment_ribbon_terminal_hardware.deviation_chain import (
    chains as material_chains,
)
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize("scale", (0.2, 1.0, 10.0))
def test_deviation_changes_interior_position_and_tangents_while_preserving_both_caps(
    scale: float,
) -> None:
    """
    One smooth offset creates a real out-of-plane reference and returns exactly to the fixed endpoints.
    """
    source = _route((Straight(20 * scale),))
    base = Guide.create(source.targets)
    offset = Vector3(0, 0, 3 * scale)
    guide = DeviationGuide.deviated(source.targets, offset)
    for u in (0.0, 1.0):
        assert guide.sample(u) == base.sample(u)
    delta = difference(guide.sample(0.5)[0], base.sample(0.5)[0])
    assert delta == offset
    first, last = guide.stations()
    assert 0 < first < 0.5 < last < 1
    assert guide.sample(first)[1].z > 0 > guide.sample(last)[1].z
    assert guide.distances[-1] > base.distances[-1]
    frames = Frames.from_guide(source.targets, guide)
    assert frames.at(0).origin == source.targets.start
    assert frames.at(1).origin == source.targets.end
    assert magnitude(difference(frames.at(1).width, source.targets.end_width)) < 1e-12
    epsilon = 1e-6
    before, after = guide.sample(0.3 - epsilon)[0], guide.sample(0.3 + epsilon)[0]
    actual = guide.sample(0.3)[1]
    finite = difference(after, before)
    assert tuple(getattr(finite, a) / (2 * epsilon) for a in "xyz") == pytest.approx(
        tuple(getattr(actual, a) for a in "xyz"), rel=1e-8, abs=1e-8
    )


@pytest.mark.parametrize(
    "offset", (Vector3(0, 0, 0), Vector3(math.nan, 0, 1), Vector3(0, math.inf, 1))
)
def test_invalid_offsets_do_not_create_a_reference(offset: Vector3) -> None:
    """
    Reject absent or nonfinite spatial instructions before frame construction.
    """
    source = _route((Straight(10),))
    with pytest.raises(ValueError, match="finite nonzero"):
        DeviationGuide.deviated(source.targets, offset)


def test_changed_steering_constructs_an_actual_material_detour_with_exact_endpoints() -> None:
    """
    Build physical fold geometry on an analytical straight-cap control without mocked allocation.
    """
    source = _route((Straight(20),))
    guide = DeviationGuide.deviated(source.targets, Vector3(0, 0, 3))
    frames = Frames.from_guide(source.targets, guide)
    boundary = Boundary(source.targets, source.radius_mm)
    derived = material_chains(boundary, frames, guide.stations(), lambda: None, lambda e: None)
    allocations = [
        fit_exact(
            boundary,
            chain,
            1e-5,
            lambda: None,
            lambda e: None,
            maximum_straight_mm=guide.distances[-1],
        )
        for chain in derived
    ]
    valid = [a for a in allocations if a is not None]
    assert valid
    route = min(valid, key=lambda a: a.route.material_length_mm).route
    assert (
        route.targets is source.targets
        and cap_error(route) < 1e-10
        and material_error(route) < 1e-10
    )
    assert max(route.lane(i / 64, 0)[0].z for i in range(65)) > 1
    assert route.material_length_mm > source.material_length_mm


@pytest.mark.parametrize("bank", (-0.5, 0.0, 0.4))
@pytest.mark.parametrize("angle", (-2.4, -0.7, 0.8, 2.3))
def test_tangent_steering_recovers_material_width_without_an_independent_roll_target(
    bank: float,
    angle: float,
) -> None:
    """
    Recover analytic folds from directed tangents, including both bend signs and oblique creases.
    """
    source = _route((fold(2, 1.2, angle, bank, 0),))
    placed = source.pieces[0]
    expected = placed.end_pose()
    derived = aim(placed.pose, expected.tangent, 2, 1.2)
    assert derived is not None
    result = PlacedPiece(placed.pose, derived, "Analytical tangent control").end_pose()
    assert magnitude(difference(result.tangent, expected.tangent)) < 1e-12
    assert magnitude(difference(result.width, expected.width)) < 1e-12
    assert derived.bank_radians == pytest.approx(bank)
    assert derived.angle_radians == pytest.approx(angle)


def test_aligned_steering_never_adds_a_fold_to_fill_travel() -> None:
    """
    Identity direction needs no bend, while a longitudinal-crease singularity safely declines.
    """
    pose = _route((Straight(10),)).pieces[0].pose
    assert aim(pose, pose.tangent, 1, 1.2) is None
    assert aim(pose, Vector3(1, 1e-8, 0), 1, 1.2) is None


@pytest.fixture
def source() -> FoldRoute:
    """
    Supply an analytical two-fold source with an internal runway and fixed ordered caps.
    """
    return _route(
        (Straight(3), fold(2, 1.2, 1, 0.2, 0), Straight(4), fold(3, 1.2, -1, -0.3, 0), Straight(2))
    )


def _terminal(source: FoldRoute) -> Mock:
    """
    Supply a fixed mocked intrusion boundary with real source-owned hardware dimensions.
    """
    gate = Mock(spec=Gate)
    gate.hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    gate.measure.return_value = Report(
        "blocked", 1, Witness("start", 3, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0))
    )
    return gate


def _closed_proposal(source: FoldRoute) -> tuple[Mock, SimpleNamespace, FoldRoute]:
    """
    Supply a fixed-cap candidate and clear certificate boundary for independent work-accounting controls.
    """
    terminal = _terminal(source)
    terminal.certify.return_value = Report("clear", 1)
    return terminal, SimpleNamespace(roots=(0, 0, 0)), restore(snapshot(source))


@pytest.mark.parametrize(
    "contact_status,hardware_status,accepted",
    (
        ("separated", "clear", True),
        ("penetration", "clear", False),
        ("unresolved", "clear", False),
        ("separated", "blocked", False),
    ),
)
def test_one_changed_guide_uses_exact_allocation_and_no_certificate_can_transfer(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
    contact_status: str,
    hardware_status: Literal["clear", "blocked"],
    accepted: bool,
) -> None:
    """
    Exercise real feature-derived offset planning with mocked exact-builder and physical boundaries.
    """
    gate = _terminal(source)
    gate.certify.return_value = Report(hardware_status, 2)
    chain = SimpleNamespace(roots=(0, 0, 0))
    builder = Mock(return_value=(chain,))
    changed = restore(snapshot(source))
    allocation = SimpleNamespace(route=changed, score=0.0, chain=chain)
    fit = Mock(return_value=allocation)
    certificate = Mock(return_value=ContactResult(contact_status, 17))
    refinement = Mock(return_value=None)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation.refine", refinement
    )
    monkeypatch.setattr("experiments.experiment_ribbon_terminal_hardware.deviation.chains", builder)
    monkeypatch.setattr("experiments.experiment_ribbon_terminal_hardware.deviation.fit", fit)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation.inspect_contact", certificate
    )
    result = deviation.recover(
        source,
        gate,
        lambda: None,
        lambda e: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=1,
    )
    assert result is not None and (result.contact is not None) is accepted
    assert result.route is (changed if accepted else source)
    assert cap_error(result.route) < 1e-10
    assert result.detail["newton_steps"] == 0 and result.detail["contact_pairs"] == 17
    builder.assert_called_once()
    fit.assert_called_once()
    certificate.assert_called_once()
    assert certificate.call_args.args[0] is changed
    boundary, frames, parameters, *_ = builder.call_args.args
    assert boundary.targets is source.targets and isinstance(frames.guide, DeviationGuide)
    assert parameters == frames.guide.stations()
    assert certificate.call_args.kwargs["maximum_pairs"] == 123
    assert fit.call_args.kwargs["maximum_straight_mm"] == frames.guide.distances[-1]
    assert gate.certify.call_count == int(contact_status == "separated")
    assert refinement.call_count == int(not accepted)
    if not accepted:
        assert refinement.call_args.args[0] is changed
        assert refinement.call_args.kwargs["work"].pairs == 123 - 17


def test_missing_witness_does_not_guess_a_detour(source: FoldRoute) -> None:
    """
    An unresolved enclosure grants neither a direction nor another configuration attempt.
    """
    gate = Mock(spec=Gate)
    gate.measure.return_value = Report("unresolved", 512)
    assert (
        deviation.recover(
            source,
            gate,
            lambda: None,
            lambda e: None,
            maximum_length_mm=source.material_length_mm,
            minimum_straight_mm=1e-5,
            remaining_pairs=123,
            maximum_cpu_seconds=0.35,
            maximum_seconds=2,
        )
        is None
    )


def test_hard_source_failure_is_never_relabelled_optional_exhaustion(source: FoldRoute) -> None:
    """
    Preserve the caller's cancellation/source guard before planning any changed reference.
    """
    stop = Mock(side_effect=RuntimeError("source drift"))
    with pytest.raises(RuntimeError, match="source drift"):
        deviation.recover(
            source,
            Mock(spec=Gate),
            stop,
            lambda e: None,
            maximum_length_mm=source.material_length_mm,
            minimum_straight_mm=1e-5,
            remaining_pairs=123,
            maximum_cpu_seconds=0.35,
            maximum_seconds=2,
        )


def test_no_exact_allocation_never_spends_a_physical_certificate(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Failed exact and single-topology closure work grants no physical certificate or another guide.
    """
    builder = Mock(
        return_value=(SimpleNamespace(roots=(0, 0, 0)), SimpleNamespace(roots=(1, 0, 0)))
    )
    fitting = Mock(return_value=None)
    closure = Mock(return_value=None)
    monkeypatch.setitem(vars(deviation), "close_deviation", closure)
    certificate = Mock(side_effect=AssertionError("No geometry to certify"))
    monkeypatch.setattr("experiments.experiment_ribbon_terminal_hardware.deviation.chains", builder)
    monkeypatch.setattr("experiments.experiment_ribbon_terminal_hardware.deviation.fit", fitting)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation.inspect_contact", certificate
    )
    result = deviation.recover(
        source,
        _terminal(source),
        lambda: None,
        lambda e: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
    )
    assert result is not None and result.route is source and result.contact is None
    assert result.detail["roots_attempted"] == 2 and result.detail["newton_steps"] == 0
    assert result.detail["stop_reason"] == "no_exact_deviation_allocation"
    builder.assert_called_once()
    assert fitting.call_count == 2
    closure.assert_called_once()
    assert result.detail["iterations"] == 1
    certificate.assert_not_called()


@pytest.mark.parametrize("maximum_updates", (1, 4))
@pytest.mark.parametrize("contact_status", ("separated", "penetration"))
def test_reclosed_deviation_is_checked_and_only_unused_work_can_continue(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
    maximum_updates: int,
    contact_status: str,
) -> None:
    """
    Debit one logical/four angular updates, then retain mandatory physical checks and the original remainder.
    """
    gate, chain, changed = _closed_proposal(source)
    monkeypatch.setitem(vars(deviation), "chains", Mock(return_value=(chain,)))
    monkeypatch.setitem(vars(deviation), "fit", Mock(return_value=None))

    def close(
        boundary: Boundary,
        attempted: tuple[Any, ...],
        threshold_mm: float,
        maximum_straight_mm: float,
        checkpoint: Callable[[], None],
        record: Callable[[dict[str, Any]], None],
    ) -> Any:
        """
        Model four accepted closure corrections while retaining a real closed route for contract checks.
        """
        assert attempted == (chain,) and maximum_straight_mm > 0 and threshold_mm == 1e-5
        assert boundary.targets is source.targets
        checkpoint()
        for _ in range(4):
            record({"stage": "feature_reclosure", "status": "residual_reduced"})
        return SimpleNamespace(route=changed, score=0.0, chain=chain)

    closure = Mock(side_effect=close)
    monkeypatch.setitem(vars(deviation), "close_deviation", closure)
    certificate = Mock(return_value=ContactResult(contact_status, 17))
    monkeypatch.setitem(vars(deviation), "inspect_contact", certificate)
    refinement = Mock(return_value=None)
    monkeypatch.setitem(vars(deviation), "refine", refinement)
    result = deviation.recover(
        source,
        gate,
        lambda: None,
        lambda e: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=maximum_updates,
    )
    assert result is not None
    assert (result.contact is not None) is (contact_status == "separated")
    assert result.detail["iterations"] == 1 and result.detail["newton_steps"] == 4
    assert result.detail["exact_closed_roots"] == 0 and result.detail["closed_roots"] == 1
    closure.assert_called_once()
    certificate.assert_called_once()
    assert certificate.call_args.args[0] is changed
    assert gate.certify.call_count == int(contact_status == "separated")
    assert refinement.call_count == int(contact_status == "penetration" and maximum_updates > 1)
    if refinement.called:
        left = refinement.call_args.kwargs["work"]
        assert left.updates == maximum_updates - 1 and left.pairs == 106
        assert left.cpu_seconds < 0.35 and left.wall_seconds < 2


def test_final_certificate_cannot_escape_total_phase_clock(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Charge reporting overhead too, discarding a physically certified but late proposal.
    """
    gate = _terminal(source)
    gate.certify.return_value = Report("clear", 1)
    chain = SimpleNamespace(roots=(0, 0, 0))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation.chains",
        Mock(return_value=(chain,)),
    )
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation.fit",
        Mock(return_value=SimpleNamespace(route=restore(snapshot(source)), score=0.0, chain=chain)),
    )
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation.inspect_contact",
        Mock(return_value=ContactResult("separated", 17)),
    )
    clock = [0.0]
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation.process_time", lambda: clock[0]
    )
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation.perf_counter", lambda: clock[0]
    )

    def record(event: dict[str, object]) -> None:
        """
        Demonstrate completion overhead crossing the unchanged original CPU ceiling.
        """
        if event["stage"] == "spatial_deviation" and event["status"] == "separated":
            clock[0] = 0.36

    result = deviation.recover(
        source,
        gate,
        lambda: None,
        record,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
    )
    assert result is not None and result.route is source and result.contact is None
    assert result.detail["stop_reason"] == "phase_budget" and result.detail["contact_pairs"] == 17


@pytest.mark.parametrize("outcome", ("separated", "penetration", "pairs", "interrupted"))
def test_contact_resumption_spends_only_original_unused_pairs_before_refinement(
    source: FoldRoute, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """
    Retain one source/traversal, charge cumulative comparisons once and debit all continuation work.
    """
    gate, chain, candidate = _closed_proposal(source)
    monkeypatch.setitem(vars(deviation), "chains", Mock(return_value=(chain,)))
    monkeypatch.setitem(
        vars(deviation),
        "fit",
        Mock(return_value=SimpleNamespace(route=candidate, score=0, chain=chain)),
    )
    initial = ContactResult("unresolved", 1024, limit="pairs")
    final = (
        deviation._Exhausted()
        if outcome == "interrupted"
        else ContactResult("unresolved", 2048, limit="pairs")
        if outcome == "pairs"
        else ContactResult(outcome, 1403)
    )
    advance = Mock(side_effect=(initial, final))
    factory = Mock(return_value=SimpleNamespace(advance=advance))
    monkeypatch.setitem(vars(deviation), "ContactTraversal", factory)
    refinement = Mock(return_value=None)
    monkeypatch.setitem(vars(deviation), "refine", refinement)
    result = deviation.recover(
        source,
        gate,
        lambda: None,
        lambda e: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=2048,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
    )
    assert result is not None
    assert factory.call_args.args[0] is candidate
    assert factory.call_args.kwargs["maximum_pairs"] == 2048
    assert [call.args[0] for call in advance.call_args_list] == [1024, 2048]
    assert result.detail["contacts"] == 1
    if outcome == "interrupted":
        assert result.detail["stop_reason"] == "phase_budget"
        assert result.detail["interrupted_pairs_charged_as_upper_bound"] == 1024
    else:
        assert result.detail["contact_resumptions"] == 1
    assert result.detail["contact_pairs"] == (2048 if outcome in ("pairs", "interrupted") else 1403)
    assert (result.contact is not None) is (outcome == "separated")
    assert refinement.call_count == int(outcome == "penetration")
    if outcome == "penetration":
        assert refinement.call_args.args[0] is candidate
        assert refinement.call_args.kwargs["work"].pairs == 645
        assert refinement.call_args.kwargs["work"].cpu_seconds < 0.35
