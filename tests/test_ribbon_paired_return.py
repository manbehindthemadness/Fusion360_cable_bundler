"""
Verify paired-branch material identity, exact frames and nonrenewable work before live diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_paired_return import allocation, factors, sequence
from experiments.experiment_ribbon_paired_return.allocation import MaterialEvidence
from experiments.experiment_ribbon_paired_return.discovery import Discovery
from experiments.experiment_ribbon_paired_return.factors import Bracket
from experiments.experiment_ribbon_paired_return.ledger import Exhausted, Ledger
from experiments.experiment_ribbon_paired_return.native_model import NativeJoints
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import FeatureEvidence
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work


def _route(scale: float = 1, sign: int = 1, split: bool = False) -> FoldRoute:
    """
    Build an independent two-factor frame with optional outgoing flat splitting.
    """
    pose = Pose(Vector3(2 * scale, -3 * scale, 5 * scale), Vector3(0, 1, 0), Vector3(0, 0, 1))
    start = pose
    geometry = [
        CylindricalFold(0.6 * scale, sign * 1.4, 0.3, 3.15 * scale, 0.8 * scale, 0.8 * scale),
        CylindricalFold(0.6 * scale, sign * -2.1, -0.2, 3.15 * scale, 0.8 * scale, 0.8 * scale),
        *([Straight(0.4 * scale), Straight(0.6 * scale)] if split else [Straight(scale)]),
    ]
    pieces = []
    for item in geometry:
        piece = PlacedPiece(pose, item, "Analytical paired material")
        pieces.append(piece)
        pose = piece.end_pose()
    targets = Targets(
        "Analytical frames",
        start.origin,
        pose.origin,
        start.tangent,
        pose.tangent,
        start.width,
        pose.width,
        4,
        0.75 * scale,
    )
    return FoldRoute(targets, tuple(pieces), 0.6 * scale)


def _ledger(roots: int = 8, updates: int = 4) -> Ledger:
    """
    Use the same original maximum clocks without any geometry or native dependency.
    """
    return Ledger(Work(updates, 2048, 0.35, 2, 0), roots, lambda: None)


@pytest.mark.parametrize("scale", [0.5, 1, 100])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("split", [False, True])
def test_canonical_pair_uses_inverse_flat_coordinates(
    monkeypatch: pytest.MonkeyPatch, scale: float, sign: int, split: bool
) -> None:
    """
    Primitive splitting and scene scale cannot replace ordered material fold identity.

    The inverse boundary is explicit here: synthetic points test classification,
    not penetration or clearance. Production entry always calls the strict inverse.
    """
    route = _route(scale, sign, split)
    first = (0.1 * scale / route.pieces[0].geometry.material_length_mm, 0, 0)
    second = (0.5, 0, 0)
    inverse = Mock(side_effect=[first, second])
    monkeypatch.setitem(vars(factors), "occupied_coordinates", inverse)
    witness = Penetration((0, len(route.pieces) - 1), (1, 0, 0), (1, 0, 0), Vector3(0, 0, 0))
    pair = factors.bracket(route, witness)
    assert pair is not None and pair.folds == (0, 1) and pair.pieces == (0, 1)
    assert pair.source is route and pair.witness.first == first and inverse.call_count == 2


def test_nonoccupied_point_never_starts_a_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A claimed witness cannot bypass the strict occupied-volume inverse.
    """
    inverse = Mock(return_value=None)
    monkeypatch.setitem(vars(factors), "occupied_coordinates", inverse)
    route = _route()
    assert (
        factors.bracket(route, Penetration((0, 2), (0, 0, 0), (0, 0, 0), Vector3(0, 0, 0))) is None
    )
    assert inverse.call_count == 1


@pytest.mark.parametrize("scale", [0.5, 1, 100])
@pytest.mark.parametrize("sign", [-1, 1])
def test_alternate_preserves_complete_ordered_orientation_and_radii(
    scale: float, sign: int
) -> None:
    """
    Derive an actual exact paired branch without claiming endpoint position or physical clearance.
    """
    route = _route(scale, sign)
    pair = Bracket(
        (0, 1), (0, 1), Penetration((0, 2), (0, 0, 0), (0.5, 0, 0), Vector3(0, 0, 0)), route
    )
    ledger = _ledger()
    result = factors.alternate(route, pair, ledger)
    assert result is not None and result.targets is route.targets
    before = [p.geometry for p in route.pieces if isinstance(p.geometry, CylindricalFold)]
    after = [p.geometry for p in result.pieces if isinstance(p.geometry, CylindricalFold)]
    assert len(before) == len(after) == 2
    assert [(p.radius_mm, p.width_mm) for p in before] == [(p.radius_mm, p.width_mm) for p in after]
    assert before[0].angle_radians * after[0].angle_radians < 0
    old, new = route.pieces[-1].end_pose(), result.pieces[-1].end_pose()
    assert magnitude(difference(old.tangent, new.tangent)) < 1e-10
    assert magnitude(difference(old.width, new.width)) < 1e-10
    assert ledger.roots == 2 and ledger.derived_roots == 2
    with pytest.raises(ValueError, match="identical"):
        factors.alternate(replace(route), pair, ledger)
    assert ledger.roots == 2


def test_root_reservation_is_charged_before_interrupted_derivation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A failed root helper cannot refund its pool or acquire another pair of roots.
    """
    route = _route()
    pair = Bracket(
        (0, 1), (0, 1), Penetration((0, 2), (0, 0, 0), (0.5, 0, 0), Vector3(0, 0, 0)), route
    )
    ledger = _ledger(2)
    helper = Mock(side_effect=ValueError("interrupted"))
    monkeypatch.setitem(vars(factors), "rotation_choices", helper)
    with pytest.raises(ValueError, match="interrupted"):
        factors.alternate(route, pair, ledger)
    assert ledger.roots == 2 and ledger.derived_roots == 0
    with pytest.raises(Exhausted, match="root_budget"):
        factors.alternate(route, pair, ledger)
    assert helper.call_count == 1


def test_update_and_pair_counters_never_renew() -> None:
    """
    Completion at the exact pair ceiling is recorded but grants no next action.
    """
    ledger = _ledger(updates=1)
    ledger.start_action()
    ledger.charge_pairs(2048)
    assert ledger.updates == 1 and ledger.pairs == 2048
    with pytest.raises(Exhausted, match="work_exhausted"):
        ledger.start_action()
    with pytest.raises(ArithmeticError):
        ledger.charge_pairs(1)


@pytest.mark.parametrize("negative", [-1e-17, -1e-4])
def test_allocation_retains_positive_material_and_declines_nonroundoff_bounds(
    monkeypatch: pytest.MonkeyPatch, negative: float
) -> None:
    """
    Only an absent slot's signed roundoff reaches the existing bounded advance.

    The projection is doubled; assertions cover caller bounds/native-floor
    contracts, not physical feasibility or optimality of a doubled vector.
    """
    route = _route()
    hardware = Hardware.create(route.targets, Dimensions.scaled(route.targets))
    monkeypatch.setitem(vars(allocation), "prepare", Mock(return_value=()))
    projected = Mock(return_value=(negative, 0.0, 0.0))
    monkeypatch.setitem(vars(allocation), "active_step", projected)
    result = allocation.allocate(route, route, (), (), hardware, 1e-5, _ledger())
    assert projected.call_count == 1
    initial, rows, residual = projected.call_args.args[1:4]
    assert len(rows) == len(residual) == 7
    assert initial[0] == 0 and residual[-1] < 0 < initial[-1]
    if negative < -1e-10:
        assert result is None
    else:
        assert result is not None
        assert result.material_length_mm == pytest.approx(route.material_length_mm)


def test_physical_capacity_declines_without_dropping_retained_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Excess remembered constraints stop before projection instead of silently omitting any.
    """
    route = _route()
    witness = Penetration((0, 2), (0, 0, 0), (0.5, 0, 0), Vector3(0, 0, 0))
    hardware = Hardware.create(route.targets, Dimensions.scaled(route.targets))
    monkeypatch.setitem(vars(allocation), "prepare", Mock(return_value=()))
    creator = Mock(return_value=Mock())
    monkeypatch.setattr(allocation.FlatSeparation, "create", creator)
    projected = Mock()
    monkeypatch.setitem(vars(allocation), "active_step", projected)
    material = (MaterialEvidence(route, witness),) * 13
    assert allocation.allocate(route, route, material, (), hardware, 1e-5, _ledger()) is None
    assert creator.call_count == 13 and not projected.called


def test_ambiguous_entry_reversals_do_not_rank_or_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Two eligible roots are unresolved, while both root reservations remain charged.
    """
    route = _route()
    witness = Penetration((0, 2), (0, 0, 0), (0.5, 0, 0), Vector3(0, 0, 0))
    pair = Bracket((0, 1), (0, 1), witness, route)
    opposite = (replace(route.pieces[0].geometry, angle_radians=-1.4), route.pieces[1].geometry)
    monkeypatch.setitem(vars(factors), "rotation_choices", Mock(return_value=(opposite, opposite)))
    ledger = _ledger()
    assert factors.alternate(route, pair, ledger) is None
    assert ledger.roots == 2 and ledger.derived_roots == 2


def test_terminal_protection_uses_the_pre_action_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    An open factorization cannot replace the source of legitimate mating-touch preferences.
    """
    anchor = _route()
    working = replace(anchor)
    hardware = Hardware.create(anchor.targets, Dimensions.scaled(anchor.targets))
    prepare = Mock(return_value=())
    monkeypatch.setitem(vars(allocation), "prepare", prepare)
    monkeypatch.setitem(vars(allocation), "active_step", Mock(return_value=None))
    assert allocation.allocate(working, anchor, (), (), hardware, 1e-5, _ledger()) is None
    assert prepare.call_args.args[0].original is anchor


def test_external_checkpoint_error_is_not_an_optional_decline() -> None:
    """
    Source, cancellation and host failures must escape the prototype unchanged.
    """
    failure = RuntimeError("source changed")
    external = Mock(side_effect=failure)
    ledger = Ledger(Work(1, 1, 0.35, 2, 0), 2, external)
    with pytest.raises(RuntimeError, match="source changed") as caught:
        ledger.start_action()
    assert caught.value is failure and ledger.updates == 0 and ledger.roots == 0


def test_coexisting_hardware_reaches_the_first_pair_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve the actual report and source pose before any replacement geometry is attempted.

    The motion boundaries are doubled; this verifies evidence transport, not the
    synthetic report's physical validity.
    """
    route = _route()
    witness = Penetration((0, 2), (0, 0, 0), (0.5, 0, 0), Vector3(0, 0, 0))
    contact = ContactResult("penetration", 1, witness)
    hardware = Report("blocked", 1, Witness("end", 0, (0.5, 0, 0), route.targets.start, (0, 0, 0)))
    monkeypatch.setitem(
        vars(sequence), "bracket", Mock(return_value=Bracket((0, 1), (0, 1), witness, route))
    )
    monkeypatch.setitem(vars(sequence), "alternate", Mock(return_value=route))
    allocation_step = Mock(return_value=None)
    monkeypatch.setitem(vars(sequence), "allocate", allocation_step)
    monkeypatch.setitem(vars(sequence), "correct_started", Mock(return_value=None))
    result = sequence.recover(
        route,
        contact,
        Mock(),
        lambda: None,
        lambda event: None,
        work=Work(2, 20, 0.35, 2, 6),
        maximum_roots=2,
        minimum_straight_mm=1e-5,
        hardware_evidence=hardware,
    )
    features = allocation_step.call_args.args[3]
    assert len(features) == 1 and features[0].route is route and features[0].report is hardware
    assert result.detail["hardware_features"] == 1 and result.accepted is None


def test_sequence_stops_before_reflecting_a_measured_pair_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The same negative evidence cannot renew a root action after one changed pair.

    Solver boundaries are doubled to isolate control/accounting; this test is
    deliberately not a physical geometry certificate.
    """
    route = _route()
    witness = Penetration((0, 2), (0, 0, 0), (0.5, 0, 0), Vector3(0, 0, 0))
    contact = ContactResult("penetration", 7, witness)
    pair = Bracket((0, 1), (0, 1), witness, route)
    monkeypatch.setitem(vars(sequence), "bracket", Mock(return_value=pair))

    def refactor(source: FoldRoute, selected: Bracket, ledger: Ledger) -> FoldRoute:
        """
        Debit real ledger operations while replacing only the geometry boundary.
        """
        assert selected.source is source
        ledger.reserve_factors()
        ledger.derived_roots += 2
        return source

    action = Mock(side_effect=refactor)
    monkeypatch.setitem(vars(sequence), "alternate", action)
    monkeypatch.setitem(vars(sequence), "allocate", Mock(return_value=route))
    monkeypatch.setitem(vars(sequence), "inspect_contact", Mock(return_value=contact))
    gate = Mock()
    gate.certify.return_value = Report("clear", 1)
    result = sequence.recover(
        route,
        contact,
        gate,
        lambda: None,
        lambda e: None,
        work=Work(4, 2048, 0.35, 2, 0),
        maximum_roots=8,
        minimum_straight_mm=1e-5,
    )
    assert (
        result.accepted is None
        and result.last_candidate is route
        and result.evidence_route is route
    )
    assert result.detail["stop_reason"] == "unsupported_or_repeated_pair"
    assert result.detail["roots_debited"] == 2 and result.detail["pairs"] == 9
    assert result.detail["updates"] == 2 and action.call_count == 1


@dataclass(frozen=True)
class PairedCrossing:
    """
    Share one explicit geometry/proof boundary for different continuation ownership controls.
    """

    source: FoldRoute
    candidate: FoldRoute
    original: ContactResult
    crossing: ContactResult
    refactor: Mock
    terminal: Mock


@pytest.fixture
def paired_crossing(monkeypatch: pytest.MonkeyPatch) -> PairedCrossing:
    """
    Charge real root reservations while doubling geometry and two distinct measured witness poses.
    """
    source, candidate = _route(), _route()
    first = Penetration((0, 2), (0, 0, 0), (0.5, 0, 0), Vector3(0, 0, 0))
    later = ContactResult("penetration", 7, replace(first, point=Vector3(1, 0, 0)))
    monkeypatch.setitem(
        vars(sequence), "bracket", Mock(side_effect=(Bracket((0, 1), (0, 1), first, source), None))
    )

    def reflect(route: FoldRoute, pair: Bracket, ledger: Ledger) -> FoldRoute:
        """
        Retain identical source ownership before spending one balanced-root reservation.
        """
        assert route is source and pair.source is source
        ledger.reserve_factors()
        return candidate

    refactor = Mock(side_effect=reflect)
    monkeypatch.setitem(vars(sequence), "alternate", refactor)
    monkeypatch.setitem(vars(sequence), "allocate", Mock(return_value=candidate))
    monkeypatch.setitem(
        vars(sequence), "inspect_contact", Mock(side_effect=(later, ContactResult("separated", 3)))
    )
    terminal = Mock()
    terminal.certify.return_value = Report("clear", 1)
    return PairedCrossing(
        source, candidate, ContactResult("penetration", 1, first), later, refactor, terminal
    )


@pytest.mark.parametrize("completed", [False, True])
def test_new_crossing_uses_current_action_without_reflecting_owned_pairs(
    monkeypatch: pytest.MonkeyPatch, completed: bool, paired_crossing: PairedCrossing
) -> None:
    """
    New evidence can drive signed motion, retaining both poses and every original action/root charge.

    Geometry/proof boundaries are doubled; this is an accounting and evidence
    protocol test, not a physical certificate.
    """

    def correct(*args: object, **_kwargs: object) -> FoldRoute | None:
        """
        Check an already charged action and the distinct retained evidence poses before motion.
        """
        material, ledger = args[3], args[7]
        assert isinstance(ledger, Ledger) and ledger.updates == 2 and ledger.action_newton == 0
        assert (
            isinstance(material, tuple)
            and material[0].route is paired_crossing.source
            and material[1].route is paired_crossing.candidate
        )
        ledger.start_newton()
        return paired_crossing.candidate if completed else None

    correction = Mock(side_effect=correct)
    monkeypatch.setitem(vars(sequence), "correct_started", correction)
    result = sequence.recover(
        paired_crossing.source,
        paired_crossing.original,
        paired_crossing.terminal,
        lambda: None,
        lambda event: None,
        work=Work(2, 20, 0.35, 2, 6),
        maximum_roots=2,
        minimum_straight_mm=1e-5,
    )
    assert (result.accepted is paired_crossing.candidate) == completed
    assert result.detail["updates"] == 2 and result.detail["newton_steps"] == 1
    assert (
        result.detail["roots_debited"] == 2
        and paired_crossing.refactor.call_count == correction.call_count == 1
    )
    assert result.detail["material_constraints"] == 2


@pytest.mark.parametrize("roots,updates,yields", [(4, 2, True), (2, 2, False), (4, 1, False)])
def test_closed_new_crossing_handoff_requires_real_refinement_work(
    monkeypatch: pytest.MonkeyPatch,
    roots: int,
    updates: int,
    yields: bool,
    paired_crossing: PairedCrossing,
) -> None:
    """
    Yield before another action is charged only when the original parent can still refine.

    Motion and proofs are doubled to isolate handoff ownership and resource
    conservation; no physical feasibility is claimed.
    """
    correction = Mock(return_value=None)
    monkeypatch.setitem(vars(sequence), "correct_started", correction)
    yielded = []
    result = sequence.recover(
        paired_crossing.source,
        paired_crossing.original,
        paired_crossing.terminal,
        lambda: None,
        lambda event: None,
        work=Work(updates, 20, 0.35, 2, 6),
        maximum_roots=roots,
        minimum_straight_mm=1e-5,
        on_event_refinement=yielded.append,
    )
    assert bool(yielded) == yields and result.accepted is None
    assert result.detail["roots_debited"] == 2 and result.detail["newton_steps"] == 0
    if yields:
        assert (
            len(yielded) == 1
            and yielded[0].route is paired_crossing.candidate
            and yielded[0].evidence is paired_crossing.crossing
        )
        assert result.detail["updates"] == 1 and not correction.called
        assert result.detail["stop_reason"] == "event_refinement_handoff"


@pytest.fixture
def hardware_stages(paired_crossing: PairedCrossing) -> tuple[Report, Report]:
    """
    Introduce a distinct measured blocker before the doubled hardware certificate clears.
    """
    old = Report("blocked", 1, Witness("start", 0, (0.5, 0, 0), Vector3(0, 0, 0), (0, 0, 0)))
    new = Report("blocked", 1, Witness("end", 0, (0.5, 0, 0), Vector3(1, 0, 0), (0, 0, 0)))
    paired_crossing.terminal.certify.side_effect = (new, Report("clear", 1))
    return old, new


def test_root_and_hardware_reclosure_use_their_already_charged_actions(
    paired_crossing: PairedCrossing,
    hardware_stages: tuple[Report, Report],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    An exhausted first action charges the next hardware action exactly once.

    Geometry and proofs are doubled; ledger counters, retained evidence and the
    six-step per-action limit remain real.
    """
    old, new = hardware_stages
    monkeypatch.setitem(vars(sequence), "allocate", Mock(return_value=None))
    monkeypatch.setitem(
        vars(sequence), "inspect_contact", Mock(return_value=ContactResult("separated", 3))
    )
    corrections = 0

    def correct(*args: object, **_kwargs: object) -> FoldRoute:
        """
        Use actual ledger operations and confirm both hardware reports survive the second stage.
        """
        nonlocal corrections
        corrections += 1
        features, ledger = args[4], args[7]
        assert (
            isinstance(ledger, Ledger)
            and ledger.updates == corrections
            and ledger.action_newton == 0
        )
        assert isinstance(features, tuple) and len(features) == corrections
        assert features[0].report is old
        if corrections == 2:
            assert features[1].route is paired_crossing.candidate and features[1].report is new
        for _ in range(6 if corrections == 1 else 4):
            ledger.start_newton()
        return paired_crossing.candidate

    monkeypatch.setitem(vars(sequence), "correct_started", correct)
    result = sequence.recover(
        paired_crossing.source,
        paired_crossing.original,
        paired_crossing.terminal,
        lambda: None,
        lambda event: None,
        work=Work(2, 20, 0.35, 2, 12),
        maximum_roots=2,
        minimum_straight_mm=1e-5,
        hardware_evidence=old,
    )
    assert result.accepted is paired_crossing.candidate and corrections == 2
    assert result.detail["updates"] == 2 and result.detail["newton_steps"] == 10
    assert result.detail["roots_debited"] == 2 and result.detail["hardware_features"] == 2


@pytest.mark.parametrize("completed", [False, True])
def test_new_hardware_uses_only_the_charged_action_remainder(
    paired_crossing: PairedCrossing,
    hardware_stages: tuple[Report, Report],
    monkeypatch: pytest.MonkeyPatch,
    completed: bool,
) -> None:
    """
    Retain new evidence and all charges without repeating allocation or deriving more roots.

    Geometry and certificates are doubles; real ledger operations enforce the
    original six-step action and global Newton limits on success and decline.
    """
    old, new = hardware_stages

    allocation_step = Mock(return_value=None)
    monkeypatch.setitem(vars(sequence), "allocate", allocation_step)
    contact = Mock(return_value=ContactResult("separated", 3))
    monkeypatch.setitem(vars(sequence), "inspect_contact", contact)

    def initial(*args: object, **_kwargs: object) -> FoldRoute:
        """
        Close the first proposal after four charged corrections.
        """
        ledger = args[7]
        assert isinstance(ledger, Ledger)
        for _ in range(4):
            ledger.start_newton()
        return paired_crossing.candidate

    def remaining(*args: object, **_kwargs: object) -> FoldRoute | None:
        """
        Verify evidence ownership and spend the two genuine remaining steps.
        """
        features, ledger = args[4], args[7]
        assert isinstance(ledger, Ledger) and (ledger.updates, ledger.action_newton) == (1, 4)
        assert isinstance(features, tuple) and [item.report for item in features] == [old, new]
        assert features[1].route is paired_crossing.candidate
        ledger.start_newton()
        ledger.start_newton()
        with pytest.raises(Exhausted, match="newton_budget"):
            ledger.start_newton()
        return paired_crossing.candidate if completed else None

    monkeypatch.setitem(vars(sequence), "correct_started", initial)
    correction = Mock(side_effect=remaining)
    monkeypatch.setitem(vars(sequence), "correct_remaining", correction)
    result = sequence.recover(
        paired_crossing.source,
        paired_crossing.original,
        paired_crossing.terminal,
        lambda: None,
        lambda event: None,
        work=Work(1, 20, 0.35, 2, 6),
        maximum_roots=2,
        minimum_straight_mm=1e-5,
        hardware_evidence=old,
    )
    assert (result.accepted is paired_crossing.candidate) == completed
    assert result.detail["updates"] == 1 and result.detail["newton_steps"] == 6
    assert allocation_step.call_count == correction.call_count == 1
    assert result.detail["roots_debited"] == 2 and result.detail["hardware_features"] == 2
    assert contact.call_count == int(completed)


@pytest.mark.parametrize("interrupted", [False, True])
def test_final_full_certificate_is_required_for_acceptance(
    monkeypatch: pytest.MonkeyPatch, interrupted: bool
) -> None:
    """
    Hardware clearance alone cannot turn an unresolved contact measurement into success.
    """
    route = _route()
    witness = Penetration((0, 2), (0, 0, 0), (0.5, 0, 0), Vector3(0, 0, 0))
    contact = ContactResult("penetration", 1, witness)
    monkeypatch.setitem(
        vars(sequence), "bracket", Mock(return_value=Bracket((0, 1), (0, 1), witness, route))
    )
    monkeypatch.setitem(vars(sequence), "alternate", Mock(return_value=route))
    monkeypatch.setitem(vars(sequence), "allocate", Mock(return_value=route))
    monkeypatch.setitem(
        vars(sequence),
        "inspect_contact",
        Mock(side_effect=Exhausted("phase_budget"))
        if interrupted
        else Mock(return_value=ContactResult("unresolved", 19, limit="pairs")),
    )
    gate = Mock()
    gate.certify.return_value = Report("clear", 1)
    result = sequence.recover(
        route,
        contact,
        gate,
        lambda: None,
        lambda e: None,
        work=Work(1, 20, 0.35, 2, 0),
        maximum_roots=8,
        minimum_straight_mm=1e-5,
    )
    assert result.accepted is None
    assert result.detail["stop_reason"] == ("phase_budget" if interrupted else "contact_unresolved")
    assert result.detail["pairs"] == 20
    assert result.detail["contact_checks"] == 1
    assert result.detail["interrupted_pairs_charged_as_upper_bound"] == (19 if interrupted else 0)


@pytest.mark.parametrize("proof", [False, True])
def test_failed_correction_returns_its_actual_hardware_evidence(
    paired_crossing: PairedCrossing, monkeypatch: pytest.MonkeyPatch, proof: bool
) -> None:
    """
    Preserve the new measured pose without turning an open failure into a closed refinement handoff.

    Motion/probe boundaries are doubled; actual open placement, evidence identity
    and charged action/Newton/root accounting remain active.
    """
    model = NativeJoints(paired_crossing.candidate, 1e-5)
    moved = list(model.initial)
    moved[0] += 0.01
    opened = model.route(tuple(moved))
    assert opened is not None and sequence.cap_error(opened) > 1e-7
    report = (
        Report("unresolved", 3)
        if proof
        else Report("blocked", 1, Witness("start", 1, (0.5, 0, 0), Vector3(0, 0, 0), (0, 0, 0)))
    )
    monkeypatch.setitem(vars(sequence), "allocate", Mock(return_value=None))

    def decline(*args: object, discovery: Discovery) -> None:
        """
        Retain one genuine Newton debit and its new route-bound negative evidence.
        """
        ledger = args[7]
        assert isinstance(ledger, Ledger) and discovery.ledger is ledger
        assert opened is not None
        ledger.start_newton()
        if proof:
            discovery.last_proof = paired_crossing.candidate, report
        else:
            discovery.latest = FeatureEvidence(opened, report)

    monkeypatch.setitem(vars(sequence), "correct_started", decline)
    handoff = Mock()
    result = sequence.recover(
        paired_crossing.source,
        paired_crossing.original,
        paired_crossing.terminal,
        lambda: None,
        lambda event: None,
        work=Work(2, 20, 0.35, 2, 6),
        maximum_roots=2,
        minimum_straight_mm=1e-5,
        on_event_refinement=handoff,
    )
    expected = paired_crossing.candidate if proof else opened
    assert (
        result.accepted is None and result.evidence is report and result.evidence_route is expected
    )
    assert result.last_candidate is paired_crossing.source and not handoff.called
    assert result.detail["updates"] == result.detail["newton_steps"] == 1
    assert result.detail["roots_debited"] == 2 and not paired_crossing.terminal.certify.called
