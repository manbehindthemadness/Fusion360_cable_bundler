"""
Verify witness-driven local topology changes independently of saved layouts and native geometry.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Literal
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_feature_insertion.deviation_guide import DeviationGuide
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Straight
from experiments.experiment_ribbon_terminal_hardware import (
    adaptive_event_construction as construction,
)
from experiments.experiment_ribbon_terminal_hardware import adaptive_event_plan as planning
from experiments.experiment_ribbon_terminal_hardware import adaptive_event_recovery as runner
from experiments.experiment_ribbon_terminal_hardware import deviation
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_plan import Proposal
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_window import (
    Edit,
    Window,
    events,
    select,
)
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.test_ribbon_aesthetic import _route


def _source() -> tuple[FoldRoute, Hardware, Report]:
    """
    Author six folds and a true end-proxy intrusion on an earlier straight, without a saved case.
    """

    def geometry(angle: float) -> CylindricalFold:
        """
        Retain one analytical material profile across every authored bend.
        """
        return CylindricalFold(1, angle, 0, 1.2, 0, 0)

    source = _route(
        (
            Straight(20),
            geometry(math.pi),
            Straight(10),
            *(geometry(a) for a in (0.1, 0.1, -0.2, 0.1, -0.1)),
            Straight(2),
        )
    )
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    point = Vector3(source.targets.end.x - 0.5, 0, 0.4)
    material = occupied_coordinates(source.pieces[0], point, 1, 1)
    assert material is not None
    box = hardware.boxes[1]
    coordinates = (
        dot(difference(point, box.pose.origin), box.axes[0]),
        dot(difference(point, box.pose.origin), box.axes[1]),
        dot(difference(point, box.pose.origin), box.axes[2]),
    )
    assert all(b.low < v < b.high for b, v in zip(box.bounds, coordinates))
    return source, hardware, Report("blocked", 1, Witness("end", 0, material, point, coordinates))


def _bump(window: Window, angle: float = 0.3) -> FoldRoute:
    """
    Match both straight-window boundary poses with an independently derived three-bend isometric bump.
    """
    source = window.route
    assert len(source.pieces) == 1 and isinstance(source.pieces[0].geometry, Straight)
    length = source.material_length_mm
    radius = source.radius_mm
    runway = (length - 4 * radius * math.sin(angle)) / (2 * math.cos(angle))
    geometries = (
        CylindricalFold(radius, angle, 0, 2 * source.half_width_mm, 0, 0),
        Straight(runway),
        CylindricalFold(radius, -2 * angle, 0, 2 * source.half_width_mm, 0, 0),
        Straight(runway),
        CylindricalFold(radius, angle, 0, 2 * source.half_width_mm, 0, 0),
    )
    cursor = source.pieces[0].pose
    pieces = []
    for geometry in geometries:
        piece = PlacedPiece(cursor, geometry, "authored closed module")
        pieces.append(piece)
        cursor = piece.end_pose()
    return FoldRoute(source.targets, tuple(pieces), source.radius_mm)


def _proposal(window: Window) -> Proposal:
    """
    Bind a real local guide to a chosen analytical interval without asserting clearance.
    """
    offset = Vector3(0, 0, 3)
    guide = DeviationGuide.deviated(window.route.targets, offset)
    return Proposal(window, Frames.from_guide(window.route.targets, guide), offset)


@pytest.mark.parametrize("count", (6, 10, 20))
def test_windows_have_local_size_without_a_global_event_limit(count: int) -> None:
    """
    The exact same structural selector supports parent chains beyond six and preserves outer identities.
    """
    source = _route(
        tuple(
            p for _ in range(count) for p in (Straight(10), CylindricalFold(1, 0.1, 0, 1.2, 0, 0))
        )
    )
    window = select(source, (len(source.pieces) - 1,))
    assert events(source) == count and events(window.route) <= 2
    assert window.source is source


def test_splicing_can_add_three_events_beyond_six_without_moving_other_geometry() -> None:
    """
    A real boundary-closed material module changes topology while every outer object survives exactly.
    """
    source, _, _ = _source()
    window = Window(source, 0, 1)
    changed = window.splice(_bump(window))
    assert events(source) == 6 and events(changed) == 9
    assert changed.targets is source.targets
    assert all(a is b for a, b in zip(changed.pieces[5:], source.pieces[1:]))
    with pytest.raises(ValueError, match="boundary"):
        window.splice(
            replace(_bump(window), targets=replace(window.route.targets, end=Vector3(99, 0, 0)))
        )


def test_undo_uses_exact_id_ranges_and_never_a_shifted_ordinal() -> None:
    """
    A later overlapping rewrite retires undo eligibility; disjoint outer pieces need no relabeling.
    """
    source, _, _ = _source()
    window = Window(source, 0, 1)
    child = _bump(window)
    changed = window.splice(child)
    original_ids = tuple((0, i) for i in range(len(source.pieces)))
    children = tuple((1, i) for i in range(len(child.pieces)))
    ids = children + original_ids[1:]
    edit = Edit(children, original_ids[:1], source.pieces[:1], child.pieces)
    restored = edit.undo(changed, ids)
    assert (
        restored is not None and restored[0].pieces == source.pieces and restored[1] == original_ids
    )
    assert edit.undo(changed, ((2, 0),) + ids[1:]) is None
    shifted = replace(
        changed,
        pieces=(replace(changed.pieces[0], label="different geometry owner"),) + changed.pieces[1:],
    )
    assert edit.undo(shifted, ids) is None


@pytest.mark.parametrize("stale", (False, True))
def test_planning_requires_current_occupied_geometry(stale: bool) -> None:
    """
    Actual owned-proxy penetration creates an aim; a shifted material coordinate cannot create events.
    """
    source, hardware, evidence = _source()
    if stale:
        assert evidence.witness is not None
        evidence = replace(evidence, witness=replace(evidence.witness, material=(0.001, 0, 0)))
    result = planning.plan(source, evidence, hardware, lambda: None)
    assert (result is None) is stale
    if result is not None:
        assert events(result.window.route) <= 2


def test_uncertainty_and_missing_witness_cannot_add_events() -> None:
    """
    No hardware/model access occurs for a checker limit or numerical failure with no strict witness.
    """
    source, _, _ = _source()
    terminal = Mock()
    result = runner.recover(
        source,
        Report("unresolved", 512),
        terminal,
        lambda: None,
        Mock(),
        work=Work(4, 2048, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is None
    terminal.certify.assert_not_called()


def test_real_local_factorization_fits_closed_straight_window() -> None:
    """
    Exercise actual algebraic roots/allocation, retaining both actual cap frames rather than a mock fit.
    """
    source = _route((Straight(20),))
    window = Window(source, 0, 1)
    roots = construction.Roots()
    result = construction.construct(_proposal(window), 1e-5, roots, lambda: None, Mock())
    assert result is not None and 0 < events(result) <= 6 and roots.attempted <= 8
    window.splice(result)


def test_root_work_is_not_renewed_for_another_window() -> None:
    """
    A previously consumed local-choice budget prevents another fit, independent of event count.
    """
    source = _route((Straight(20),))
    roots = construction.Roots(8)
    assert (
        construction.construct(_proposal(Window(source, 0, 1)), 1e-5, roots, lambda: None, Mock())
        is None
    )
    assert roots.attempted == 8


def test_controller_certifies_grown_route_and_rejects_removal_that_restores_intrusion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Real splice/material/caps are checked; full contact/hardware boundaries are explicit mocks here.
    """
    source, hardware, evidence = _source()
    window = Window(source, 0, 1)
    monkeypatch.setitem(vars(runner), "plan", Mock(return_value=_proposal(window)))
    monkeypatch.setitem(vars(runner), "construct", Mock(return_value=_bump(window)))
    certificate = ContactResult("separated", 2, None, None, "authored checker boundary")
    inspect = Mock(return_value=certificate)
    monkeypatch.setitem(vars(runner), "inspect_contact", inspect)
    terminal = Mock(
        spec=Gate,
        hardware=hardware,
        certify=Mock(
            side_effect=lambda route, stage: (
                evidence if route.pieces == source.pieces else Report("clear", 1)
            )
        ),
    )
    result = runner.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        Mock(),
        work=Work(4, 2048, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and result.contact is certificate and events(result.route) == 9
    assert result.detail["pruning_attempted"] == 1 and result.detail["modules_removed"] == 0
    assert result.detail["contact_pairs"] == 4 and result.detail["iterations"] == 2
    assert inspect.call_args_list[0].kwargs["maximum_pairs"] == 2048
    assert inspect.call_args_list[1].kwargs["maximum_pairs"] == 2046


def test_resource_failure_propagates_without_a_geometry_fallback() -> None:
    """
    Caller source/cancellation failures cannot become unsupported preparation or a renewed strategy.
    """
    source, hardware, evidence = _source()
    with pytest.raises(TimeoutError, match="source"):
        runner.recover(
            source,
            evidence,
            Mock(spec=Gate, hardware=hardware),
            Mock(side_effect=TimeoutError("source")),
            Mock(),
            work=Work(4, 2048, 0.35, 2),
            maximum_length_mm=100,
            minimum_straight_mm=1e-5,
        )


def test_two_local_rewrites_can_grow_then_remove_a_module_within_one_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Real boundary-closed geometry and lineage run; checker dispositions are protocol-only doubles.

    A later disjoint rewrite can make an earlier module redundant. Four charged
    actions cover both insertions and both removal checks; root/pair work never resets.
    """
    source, hardware, evidence = _source()
    visited = []

    def propose(route: FoldRoute, observed: Any, fixed: Any, check: Any) -> Proposal:
        """
        Select two disjoint analytical straight windows to exercise lineage across growth.
        """
        del observed, fixed, check
        index = 0 if not visited else len(route.pieces) - 1
        visited.append(events(route))
        return _proposal(Window(route, index, index + 1))

    def build(
        proposal: Proposal, minimum: float, roots: construction.Roots, check: Any, record: Any
    ) -> FoldRoute:
        """
        Charge the shared root receipt while using actual local material geometry.
        """
        del minimum, check, record
        roots.attempted += 1
        return _bump(proposal.window)

    certificate = ContactResult("separated", 2, None, None, "mock full checker")
    monkeypatch.setitem(vars(runner), "plan", propose)
    monkeypatch.setitem(vars(runner), "construct", build)
    monkeypatch.setitem(vars(runner), "inspect_contact", Mock(return_value=certificate))
    # This explicit boundary double makes the second module necessary and the first redundant.
    terminal = Mock(
        spec=Gate,
        hardware=hardware,
        certify=Mock(
            side_effect=lambda route, stage: (
                Report("clear", 1)
                if isinstance(route.pieces[-1].geometry, CylindricalFold)
                else evidence
            )
        ),
    )
    result = runner.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        Mock(),
        work=Work(4, 2048, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and result.contact is certificate
    assert visited == [6, 9] and result.detail["rewrites"] == 2
    assert result.detail["modules_removed"] == 1 and events(result.route) == 9
    assert result.detail["roots_attempted"] == 2 and result.detail["iterations"] == 4
    assert result.detail["contact_pairs"] == 8


@pytest.mark.parametrize("limit", ("pairs", None))
def test_unresolved_proof_stops_insertion_instead_of_manufacturing_another_event(
    monkeypatch: pytest.MonkeyPatch,
    limit: Literal["pairs"] | None,
) -> None:
    """
    New topology is not justified by an uncertain certificate, even when updates remain.
    """
    source, hardware, evidence = _source()
    window = Window(source, 0, 1)
    planner = Mock(return_value=_proposal(window))
    monkeypatch.setitem(vars(runner), "plan", planner)
    monkeypatch.setitem(vars(runner), "construct", Mock(return_value=_bump(window)))
    monkeypatch.setitem(
        vars(runner),
        "inspect_contact",
        Mock(return_value=ContactResult("unresolved", 4, None, None, "unmeasured", limit=limit)),
    )
    result = runner.recover(
        source,
        evidence,
        Mock(spec=Gate, hardware=hardware),
        lambda: None,
        Mock(),
        work=Work(4, 2048, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and result.contact is None and planner.call_count == 1
    assert result.detail["stop_reason"] == "uncertain_global_proof"


def test_boundary_failure_cannot_be_overridden_by_checker_doubles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Invalid local cap geometry rejects before either global certificate or native construction.
    """
    source, hardware, evidence = _source()
    window = Window(source, 0, 1)
    monkeypatch.setitem(vars(runner), "plan", Mock(return_value=_proposal(window)))
    bad = replace(_bump(window), targets=replace(window.route.targets, end=Vector3(999, 0, 0)))
    monkeypatch.setitem(vars(runner), "construct", Mock(return_value=bad))
    check = Mock()
    monkeypatch.setitem(vars(runner), "inspect_contact", check)
    with pytest.raises(ValueError, match="boundary"):
        runner.recover(
            source,
            evidence,
            Mock(spec=Gate, hardware=hardware),
            lambda: None,
            Mock(),
            work=Work(4, 2048, 0.35, 2),
            maximum_length_mm=100,
            minimum_straight_mm=1e-5,
        )
    check.assert_not_called()


def _recover_wrapper(source: FoldRoute, hardware: Hardware, evidence: Report) -> Result | None:
    """
    Invoke the public recovery boundary with one original analytical allocation.
    """
    return deviation.recover(
        source,
        Mock(spec=Gate, hardware=hardware, measure=Mock(return_value=evidence)),
        lambda: None,
        Mock(),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
        remaining_pairs=2048,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
    )


@pytest.mark.parametrize("attempted", (False, True))
def test_wrapper_never_renews_time_or_restarts_after_attempted_refinement(
    monkeypatch: pytest.MonkeyPatch,
    attempted: bool,
) -> None:
    """
    Unsupported preparation can fall through with leftover time; attempted failure ends the action.
    """
    source, hardware, evidence = _source()
    clock = [0.0]
    monkeypatch.setitem(vars(deviation), "process_time", lambda: clock[0])
    monkeypatch.setitem(vars(deviation), "perf_counter", lambda: clock[0])
    failed = Result(source, None, {"status": "unresolved"})

    def prepare(*args: Any, **kwargs: Any) -> Result | None:
        """
        Spend measurable preparation work without consuming a logical geometry update.
        """
        del args, kwargs
        clock[0] = 0.1
        return failed if attempted else None

    monkeypatch.setitem(vars(deviation), "recover_adaptive", prepare)
    fallback = Mock(return_value=failed)
    monkeypatch.setitem(vars(deviation), "recover_fixed_stages", fallback)
    result = _recover_wrapper(source, hardware, evidence)
    assert result is not None and result.contact is None
    if attempted:
        fallback.assert_not_called()
    else:
        assert fallback.call_count == 1
        assert fallback.call_args.kwargs["maximum_cpu_seconds"] == pytest.approx(0.25)
        assert fallback.call_args.kwargs["maximum_seconds"] == pytest.approx(1.9)
        assert fallback.call_args.kwargs["remaining_pairs"] == 2048


@pytest.mark.parametrize("adaptive", (False, True))
def test_wrapper_rejects_a_late_certificate_from_either_strategy(
    monkeypatch: pytest.MonkeyPatch,
    adaptive: bool,
) -> None:
    """
    A strategy cannot turn a certificate returned after the original clock limit into acceptance.
    """
    source, hardware, evidence = _source()
    clock = [0.0]
    monkeypatch.setitem(vars(deviation), "process_time", lambda: clock[0])
    monkeypatch.setitem(vars(deviation), "perf_counter", lambda: clock[0])
    certificate = ContactResult("separated", 2)

    def late(*args: Any, **kwargs: Any) -> Result:
        """
        Return a protocol-only certificate after consuming too much of the original allocation.
        """
        del args, kwargs
        clock[0] = 0.36
        return Result(source, certificate, {"status": "separated"})

    monkeypatch.setitem(
        vars(deviation), "recover_adaptive", late if adaptive else Mock(return_value=None)
    )
    monkeypatch.setitem(vars(deviation), "recover_fixed_stages", late)
    result = _recover_wrapper(source, hardware, evidence)
    assert result is not None and result.contact is None
    assert result.detail["stop_reason"] == "phase_budget"
