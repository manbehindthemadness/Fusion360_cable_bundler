"""
Close exact caps, finite connector clearance and complete measured material contact regions together.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from enum import Enum
from functools import partial
from time import perf_counter, process_time
from typing import Any, Callable, Union, cast

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_feature_insertion.separation import Side
from experiments.experiment_ribbon_fold_relaxation.steps import advance, step_limit
from experiments.experiment_ribbon_fold_route.contact import (
    ContactResult,
    Penetration,
    ProjectionReuse,
    inspect_contact,
)
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight

from .active_projection import active_step
from .cap_completion import ordered_caps_complete
from .check import Report
from .contact_addition import Addition, ContactPolicy
from .contact_addition import prepare as prepare_contact_addition
from .feature_guidance import (
    ContactGuidance,
    ContactMotion,
    IncidentGuidance,
    MaterialGuidance,
    ReturnLength,
    member_planes,
)
from .feature_plane import FeatureCoverage, FeaturePlane, SignedJoints
from .flat_continuation import ClosedFlatContinuation, ContactContinuation
from .flat_separation import FlatSeparation, ProfileExtent
from .gate import Gate
from .hardware_motion import expand as expand_hardware
from .incident_model import IncidentJoints
from .joint_derivatives import jacobian as joint_jacobian
from .joint_evaluation import JointEvaluation
from .joint_handoff import JointHandoff
from .line_search import contracted_fraction
from .material_constraint import MaterialConstraint
from .material_return_selection import UnreflectedReturns
from .native_slots import bind_proposal as bind_native_slots
from .native_slots import extensions as extend_native_slots
from .native_slots import zero_step
from .quality_projection import quality_step
from .radius_model import RadiusJoints
from .recovery_limits import validate
from .redistributed_projection import GuidancePolicy, ProjectionEvidence, redistributed_step
from .restoration_handoff import RestorationHandoff, RestorationStop
from .restoration_screen import represented_phases
from .restoration_screen import screen as screen_restoration
from .reversal_model import incident_fold
from .run_translation import StraightSlots
from .straight_projection import RunwayEvidence, shortest_run_step
from .straight_quality import StraightQuality
from .terminal_protection import Protection
from .terminal_protection import prepare as prepare_terminal_protection
from .terminal_protection import uncovered as uncovered_terminal_protection


class JointMode(Enum):
    """
    Distinguish parent improvement, mating quality policies and one-radius physical restoration.
    """

    PARENT_CEILING = "parent_ceiling"
    MATING_CEILING = "mating_ceiling"
    BLOCKED_MATING = "blocked_mating"
    RADIUS_RESTORATION = "radius_restoration"


class _Exhausted(RuntimeError):
    """
    Stop only this optional shared allocation without masking caller cancellation or resource errors.
    """


RecoveryMode = Union[JointMode, IncidentGuidance, MaterialGuidance, ContactGuidance]


def recover(
    original: FoldRoute,
    evidence: Report | Penetration | ContactResult,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    remaining_pairs: int,
    maximum_cpu_seconds: float,
    maximum_seconds: float,
    maximum_updates: int,
    mode: RecoveryMode = JointMode.PARENT_CEILING,
    on_blocked: Callable[[JointHandoff], None] | None = None,
    on_restoration_blocked: Callable[[RestorationHandoff], None] | None = None,
    early_material_return: UnreflectedReturns | None = None,
) -> Result | None:
    """
    Use remaining original work on caps and actual connector or flat-contact evidence.

    An opted-in adaptive hardware stage may retain its first actual complete
    flat crossing in the same straight-only model before a closed handoff. All
    earlier hardware constraints, clocks, pairs and update limits remain. A
    projection/descent decline can yield only its identical retained closed state;
    motion invalidates that fallback and every success needs fresh full proofs.

    An opted-in sequence may stop a reflected material stage at a newly retained
    strict crossing selecting a distinct unreflected turn, while another logical
    update remains. The same current-pose inverse validation and original clocks
    guard this uncertified transfer. It grants no closure, clearance or new work.

    The parent length is an inequality ceiling, never a growth target. All signs,
    radii, material identity/order and target poses stay fixed. Negative-only hull
    probing runs only until a first actual contact; subsequent certificates use
    the complete original checker, with bounded identical projection reuse.
    Every certificate and witness comparison shares the original pair pool.
    The default retains every radius and the parent length ceiling. Explicit
    radius restoration grows only the evidence-incident radius and treats the
    invalid source length as a quality goal rather than a physical veto. It
    receives only genuinely unused work after a measured fold-domain boundary.
    All material, cap, contact and finite-hardware requirements remain strict.
    Actual ordered mating caps within the existing1e-7contract may advance to
    ordinary physical certification even when their normalized progress metric
    remains above1e-13. Every represented inequality retains its original gate;
    native slots, material identity, hardware and full contact still must pass.
    Explicit mating restoration retains every radius and the strict parent
    ceiling, placing its length target inside that ceiling with the existing
    StraightQuality margin. It avoids rounded equality without accepting any
    excess or changing physical tolerances. Default parent targeting is unchanged.
    Contact guidance jointly retains depth-limited flat phases and actual
    hardware members without reflecting folds. It uses the same bounded-cap
    projector and complete independent inequalities, treating invalid-source
    length as a reported quality goal. It does not turn uncertain contact into
    a penetration witness or clearance. Final hardware uses refined certification.
    A confirmed curved crossing can add the shared analytic whole-piece
    projection while retaining earlier flat/hardware constraints. Mixed curved
    depth uncertainty remains unsupported; no local witness patch is accepted.
    Mating restoration retains each witnessed flat contact as an independent
    full-profile inequality. More than four scalar inequalities use the existing
    sixteen-step active projection; constraint, update, time and pair limits stay
    unchanged. Other modes retain their original aggregated profile-arc guidance.
    A strict material crossing can initialize complete-profile flat guidance
    without inventing hardware intrusion. That entry can subsequently add
    up to two demonstrated connector planes. One-radius restoration can also
    retain a second actually witnessed hardware feature after clearing its
    initial constraint. Each occupied member gets its own closest box halfspace;
    adjoining members need not clear the same box face. Up to thirteen physical
    inequalities use the existing sixteen-step projection when needed. Both
    features share the same remaining updates, clocks and pair pool; no additional
    radius is released. Other legacy hardware entries retain their single-plane
    stopping behavior and profile-arc guidance.
    Incident guidance retains actual prior reports, reflects their one witnessed
    event and gives occupied members independent separating planes. At most four
    features/thirteen physical inequalities use sixteen dual active-set steps,
    replacing scalar subset enumeration under the same caller work allocation.
    Angular restoration shares independent cap residuals across incident,
    material and coupled guidance. Cap residuals may change independently
    within the previous maximum merit, using the same single
    bounded projector and strict predicted/nonlinear maximum-merit descent.
    Motion regularization decays with the square of that merit; original bounds
    receive an equivalent positive coordinate transform inside the projector.
    A working set declined for exhaustion or raw inequalities can supply its
    already-computed geometry after one
    coordinate-box projection, still requiring the same predicted/nonlinear gates.
    Exhaustion and bounded proposals are reported separately from accepted work.
    Physical violations retain their shared restoration fraction; satisfied rows
    cannot acquire a positive linear violation. Material guidance selects a fold
    from an actual crossing and retains its complete regions. It allows equal
    parent length, with no compulsory shortening, and chooses its initial
    separating side in the reflected geometry. Confirmed curved crossings use
    analytic whole-piece guidance. All subsequent material and hardware
    certificates remain mandatory.
    Coupled and reflected correction constrain both terminal fold neighborhoods
    before motion, including the opposite connector without an intrusion witness.
    Uncertified enclosures target separation; only a complete analytic mating-cap
    certificate permits retaining source touch. These are conservative motion
    preferences, not clearance reports. Source axis families rebind with the
    motion model and share the original inequality/time limits. Necessary tiny
    positive zero-slot directions select a native-valid lower face in the one
    existing replacement projection; zero/outward directions remain frozen.
    Before that signed-joint replacement, an original zero slot may stay absent
    only if its zeroed proposal retains the same predicted constraint limits and
    strict maximum-merit descent. Otherwise positive-floor selection remains.
    Existing positive material is never removed and no projection is added.
    Fixed-bend cleanup uses that pass for feasibility without another runway
    minimization. Nonlinear steps and final native minimum checks remain strict.
    A positive sub-native straight found at cap closure extends to the smallest
    representable native floor instead of being deleted in coupled/reflected
    correction. Pin that length during the existing charged reclosure action;
    remaining coordinates must restore caps and pass every final certificate.
    Fixed-bend reclosure performs feasibility without restarting minimization.
    The existing replacement projection also enforces native feasibility when
    a positive slot would contract to a sub-native positive length. Choose its
    face from the target coordinate, retaining the same projection/trial limits.
    Explicit blocked-mating entry initially retains the same mating ceiling.
    Only after linear projection failure may its inherited quality ceiling become
    a reported length goal, with independent occupied hardware-member halfspaces
    rebound at the same coordinates. Every existing physical constraint and spent
    update remains; clear mating improvement never enters that release.
    An explicit continuation can retain a closed proposal at its first actual
    blocker. It receives no work allocation or clearance. Unresolved evidence
    never yields a guessed blocker; default local correction remains unchanged.
    Material return keeps its legacy parent ceiling by default. The explicit
    sequence restoration policy reports invalid-source length as a quality goal;
    all material, cap, radius and contact/hardware requirements remain strict.
    Adaptive hardware motion first minimizes travel in the straight-only domain.
    An initial projection returning no step,
    before any Newton motion and without material uncertainty, may rebind the
    same actual hardware features to the signed-joint domain. This preference
    does not prove global infeasibility. A feasible straight extension proceeds
    through unchanged nonlinear descent and final certificates; the shortest-run
    objective is a preference, not a veto on necessary travel. Model-bound caches are replaced, all original clocks and
    counters continue, and no second expansion or alternative sign is tried.
    Rejected nonlinear steps use safeguarded quadratic contraction from the
    existing linear prediction and observed merit. Inadmissible trials halve.
    The same four trials and strict nonlinear descent remain mandatory.
    Reflected/coupled angular restoration permits only already-positive guidance
    terms to trade below a strictly decreasing maximum residual. Satisfied linear
    guidance stays strict; final material, cap and physical gates are unchanged.
    Changed open-cap angular/reflected proposals receive a negative-only flat
    screen, at most32comparisons per pose and256total from the original pair
    allowance. The existing probe support ceiling is shared. Strict new witnesses
    retain complete material guidance under the same four-constraint/thirteen-row
    limits; a miss grants no clearance. Screening times are included in contact
    time and reported separately as a subset. Final certificates stay mandatory.
    An opt-in restoration callback can yield a newly screened strict material
    witness after an ordinary projection/descent stop at that unchanged pose.
    It revalidates both inverse maps and material consistency under this same
    clock, grants no cap closure, and cannot follow resource or caller failure.
    """
    if not isinstance(mode, (JointMode, IncidentGuidance, MaterialGuidance, ContactGuidance)):
        raise ValueError("Supply an explicit joint recovery mode")
    coupled_contact = isinstance(mode, ContactGuidance)
    straight_contact = isinstance(mode, ContactGuidance) and mode.motion in (
        ContactMotion.STRAIGHT_SLOTS,
        ContactMotion.ADAPTIVE_HARDWARE,
    )
    adaptive_hardware = (
        isinstance(mode, ContactGuidance) and mode.motion is ContactMotion.ADAPTIVE_HARDWARE
    )
    if adaptive_hardware and isinstance(evidence, ContactResult) and evidence.status != "separated":
        raise ValueError(
            "Adaptive hardware motion requires hardware-only or separated contact evidence"
        )
    if isinstance(evidence, ContactResult) and not coupled_contact:
        raise ValueError("Contact guidance requires an actual material measurement")
    if coupled_contact and not isinstance(evidence, (ContactResult, Report)):
        raise ValueError("Contact guidance requires measured contact or retained hardware evidence")
    if isinstance(mode, MaterialGuidance) and not isinstance(evidence, Penetration):
        raise ValueError("Material reversal requires an actual material crossing")
    validate(
        remaining_pairs=remaining_pairs,
        maximum_cpu_seconds=maximum_cpu_seconds,
        maximum_seconds=maximum_seconds,
        maximum_updates=maximum_updates,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
    )
    cpu, wall = process_time(), perf_counter()
    mating_mode = mode in (JointMode.MATING_CEILING, JointMode.BLOCKED_MATING)
    reflected = isinstance(mode, (IncidentGuidance, MaterialGuidance))
    selected: int | None = None
    model: SignedJoints
    if isinstance(mode, (IncidentGuidance, MaterialGuidance)):
        model = IncidentJoints(original, mode.selected_fold)
        selected = mode.selected_fold
    elif mode is JointMode.RADIUS_RESTORATION:
        if (
            not isinstance(evidence, Report)
            or evidence.status != "blocked"
            or evidence.witness is None
        ):
            return None
        selected = incident_fold(original, evidence.witness)
        if selected is None:
            return None
        model = RadiusJoints(original, selected)
    elif straight_contact:
        model = StraightSlots(original)
    else:
        model = SignedJoints(original)
    values = model.initial
    constraints: list[tuple[FlatSeparation | MaterialConstraint, Side]] = []
    planes: list[FeaturePlane] = []
    if isinstance(mode, (IncidentGuidance, ContactGuidance)) or (
        isinstance(mode, MaterialGuidance) and mode.evidence
    ):
        prepared = mode.planes(model, terminal.hardware, values)
        if prepared is None:
            return None
        planes = prepared
    if coupled_contact:
        if isinstance(evidence, ContactResult):
            initial = MaterialConstraint.create(model, original, evidence)
            if initial is None:
                if evidence.status != "separated" or not planes:
                    return None
            else:
                constraints.append((initial, Side.BEFORE))
        elif (
            not isinstance(evidence, Report)
            or evidence.status != "blocked"
            or evidence.witness is None
            or not planes
        ):
            return None
    elif isinstance(mode, IncidentGuidance):
        pass
    elif isinstance(evidence, Report):
        plane = FeaturePlane.create(model, original, evidence, terminal.hardware, values)
        if plane is None:
            return None
        planes.append(plane)
    elif isinstance(evidence, Penetration):
        initial = (
            MaterialConstraint.from_witness(model, original, evidence, axis_values=values)
            if isinstance(mode, MaterialGuidance)
            else FlatSeparation.create(model, original, evidence, extent=ProfileExtent.COMPLETE)
        )
        if initial is None:
            return None
        side = Side.BEFORE
        if isinstance(mode, MaterialGuidance) and initial.gap(values, Side.AFTER) > initial.gap(
            values, Side.BEFORE
        ):
            side = Side.AFTER
        constraints.append((initial, side))
    else:
        raise ValueError(
            "Initialize joint work from measured hardware or material crossing evidence"
        )
    independent_members = reflected or coupled_contact or mode is JointMode.RADIUS_RESTORATION
    independent_contacts = mating_mode or coupled_contact or isinstance(mode, MaterialGuidance)
    scalar_planes = member_planes(planes, model, values) if independent_members else planes
    protections: tuple[Protection, ...] = ()
    if (
        independent_members
        and len(scalar_planes) + len(constraints) + int(not coupled_contact) > 13
    ):
        return None
    projection_evidence = ProjectionEvidence()
    restoration_policy = GuidancePolicy.RESTORATION_MERIT
    runway_evidence = RunwayEvidence()
    project = (
        partial(shortest_run_step, evidence=runway_evidence)
        if straight_contact
        else partial(
            redistributed_step, evidence=projection_evidence, guidance_policy=restoration_policy
        )
        if reflected or coupled_contact
        else quality_step
    )
    length_released = False
    hardware_expanded = False
    bounded_length = (
        mode is not JointMode.RADIUS_RESTORATION
        and not coupled_contact
        and not (
            isinstance(mode, MaterialGuidance) and mode.length is ReturnLength.RESTORATION_GOAL
        )
    )
    length_target = (
        StraightQuality(maximum_length_mm, maximum_updates).target_mm
        if mating_mode
        else maximum_length_mm - 1e-7
        if isinstance(mode, IncidentGuidance)
        else maximum_length_mm
    )
    keys: set[tuple[Any, ...]] = (
        {(bound.pair, bound.parts) for bound, _ in constraints} if coupled_contact else set()
    )
    fixed: set[int] = set()
    native_pins: dict[int, float] = {}
    newton, pairs, contacts, contact_seconds = 0, 0, 0, 0.0
    candidate = original
    measurement: ContactResult | None = None
    accepted = False
    stop = "unattempted"
    active_pairs: int | None = None
    contact_started = 0.0
    interrupted_pairs: int | None = None
    probe = FlatProbe()
    penetration_seen = False
    native_positive_projections = 0
    native_zero_face_selections = 0
    ordered_cap_completions = 0
    screen_checks, screen_pairs, screen_seconds = 0, 0, 0.0
    screened_values: tuple[float, ...] | None = None
    restoration_witness: tuple[tuple[float, ...], ContactResult] | None = None
    flat_continuation: ClosedFlatContinuation | None = None
    straight_contact_preparations = 0
    straight_contact_fallbacks = 0
    straight_contact_decline: str | None = None
    next_return: int | None = None
    restoration_decline: str | None = None
    restoration_inverse_checks = 0
    screen_active = False

    def bounded() -> None:
        """
        Charge preparation, derivatives, motion, evidence and final proof to this one allocation.
        """
        checkpoint()
        if process_time() - cpu >= maximum_cpu_seconds or perf_counter() - wall >= maximum_seconds:
            raise _Exhausted()

    def emit(status: str, **data: Any) -> None:
        """
        Retain all actual crossings, complete region choices and unsuccessful motions.
        """
        record({"stage": "joint_flat_contact", "status": status, **data})

    def raw_equations(coordinates: tuple[float, ...]) -> tuple[float, ...]:
        """
        Reuse identical raw equations only while the actual constraint set remains fixed.
        """
        equation_terms = model.residual(coordinates) + tuple(
            1e-7 / model.scale - feature.gap(coordinates) for feature in scalar_planes
        )
        equation_terms += tuple(protection.residual(coordinates) for protection in protections)
        if bounded_length:
            equation_terms += (
                (
                    sum(p.geometry.material_length_mm for p in model.pieces(coordinates))
                    - length_target
                )
                / model.scale,
            )
        if constraints:
            flat_terms = tuple(
                1e-8 / model.scale - constraint.gap(coordinates, chosen_side)
                for constraint, chosen_side in constraints
            )
            equation_terms += flat_terms if independent_contacts else (max(flat_terms),)
        return equation_terms

    evaluation = JointEvaluation(raw_equations, model.admissible)
    equations, admissible = evaluation.equations, evaluation.admissible

    def merit(coordinates: tuple[float, ...]) -> float:
        """
        Reduce actual cap errors and only violated inequality terms.
        """
        merit_terms = equations(coordinates)
        return max(
            *(abs(term) for term in merit_terms[:6]), *(max(0.0, term) for term in merit_terms[6:])
        )

    def retain_addition(entry: Addition | None) -> str | None:
        """
        Retain complete contact guidance within the original constraint and equation ceilings.
        """
        if entry is None or len(constraints) >= 4:
            return "unsupported_or_exhausted_flat_constraints"
        if entry.key in keys:
            return "repeated_contact_witness"
        keys.add(entry.key)
        inequalities = (
            len(scalar_planes)
            + len(protections)
            + (len(constraints) + 1 + int(bounded_length) if independent_contacts else 2)
        )
        if independent_members and inequalities > 13:
            return "physical_inequality_capacity"
        constraints.append((entry.bound, entry.side))
        evaluation.constraints_changed()
        emit(
            "constraint_added",
            witness=None if entry.witness is None else asdict(entry.witness),
            pair=[asdict(tag) for tag in entry.bound.pair],
            parts=[
                {"phase": part.phase.value, "q": (part.low_q, part.high_q)}
                for part in entry.bound.parts
            ],
            side=entry.side.name,
            gap_mm=entry.bound.gap(values, entry.side) * model.scale,
        )
        return None

    addition: Addition | None = None

    def new_witness(witness: Penetration) -> bool:
        """
        Bind a new complete current-pose region without duplicating retained material.
        """
        nonlocal addition
        proposed_addition = prepare_contact_addition(
            model,
            candidate,
            ContactResult("penetration", 0, witness=witness),
            values,
            ContactPolicy.RESTORATION,
        )
        if proposed_addition is None or any(
            old.pair == proposed_addition.bound.pair and old.parts == proposed_addition.bound.parts
            for old, _ in constraints
        ):
            return False
        addition = proposed_addition
        return True

    try:
        bounded()
        if reflected or coupled_contact:
            protections = prepare_terminal_protection(
                model, terminal.hardware, scalar_planes, bounded
            )
            if len(scalar_planes) + len(protections) + len(constraints) + int(bounded_length) > 13:
                return None
        emit(
            "started",
            source=snapshot(original),
            maximum_length_mm=maximum_length_mm,
            remaining_updates=maximum_updates,
            remaining_pairs=remaining_pairs,
            initial_flat_constraints=len(constraints),
            initial_hardware_members=len(scalar_planes),
            terminal_protections=[
                {
                    "terminal": protection.plane.box.terminal.value,
                    "member": asdict(protection.plane.reference),
                    "minimum_gap_mm": protection.minimum_gap * model.scale,
                }
                for protection in protections
            ],
            material_evidence_status=evidence.status
            if isinstance(evidence, ContactResult)
            else None,
        )
        while True:
            bounded()
            proposed = model.route(values)
            assert proposed is not None
            candidate = proposed
            terms = equations(values)
            error = merit(values)
            caps_complete = error < 1e-13 or ordered_caps_complete(candidate, terms)
            if caps_complete and error >= 1e-13:
                ordered_cap_completions += 1
                emit(
                    "ordered_caps_complete",
                    normalized_error=error,
                    cap_error_mm=cap_error(candidate),
                )
            if (
                (reflected or coupled_contact)
                and not straight_contact
                and not caps_complete
                and newton > 0
                and screened_values != values
                and screen_pairs < 256
                and probe.supports < 2048
            ):
                screened_values = values
                allowed = min(32, 256 - screen_pairs, remaining_pairs - pairs)
                if allowed <= 0:
                    stop = "pair_budget"
                    break
                addition = None

                active_pairs, screen_active = allowed, True
                screen_checks += 1
                contact_started = perf_counter()
                screened = screen_restoration(
                    candidate,
                    probe,
                    allowed,
                    bounded,
                    new_witness,
                    covered_phases=represented_phases(candidate, constraints),
                )
                spent = perf_counter() - contact_started
                pairs += screened.pairs_checked
                screen_pairs += screened.pairs_checked
                screen_seconds += spent
                contact_seconds += spent
                active_pairs, screen_active = None, False
                emit("restoration_screen", contact=asdict(screened))
                if addition is not None:
                    reason = retain_addition(addition)
                    if reason is not None:
                        stop = reason
                        break
                    penetration_seen = True
                    restoration_witness = (values, screened)
                    if (
                        early_material_return is not None
                        and on_restoration_blocked is not None
                        and isinstance(mode, MaterialGuidance)
                        and mode.selected_fold in early_material_return.reflected_folds
                        and math.ceil(newton / 6) < maximum_updates
                        and pairs < remaining_pairs
                        and screened.witness is not None
                    ):
                        bounded()
                        next_return = early_material_return.select(candidate, screened.witness)
                        if next_return is not None:
                            stop = "new_material_return"
                            break
                    continue
            if caps_complete:
                if (
                    cap_error(candidate) > 1e-7
                    or material_error(candidate) > 1e-10
                    or not model.preserves(candidate)
                    or (bounded_length and candidate.material_length_mm > maximum_length_mm)
                ):
                    stop = "final_contract"
                    break
                slivers = {
                    i
                    for i in model.straight_indices
                    if 0 < values[i] * model.scale <= minimum_straight_mm
                }
                if slivers:
                    if newton >= 6 * maximum_updates:
                        stop = "native_zero_reclosure_limit"
                        break
                    if (reflected or coupled_contact) and minimum_straight_mm > 0:
                        extended = extend_native_slots(
                            model, values, frozenset(slivers), minimum_straight_mm, model.scale
                        )
                        if extended is None:
                            stop = "native_extension_infeasible"
                            break
                        native_pins.update(extended)
                        emit(
                            "native_sliver_extended",
                            original_lengths_mm={str(i): values[i] * model.scale for i in slivers},
                            pinned_lengths_mm={
                                str(i): value * model.scale for i, value in extended.items()
                            },
                        )
                    fixed.update(slivers)
                    values = tuple(
                        native_pins.get(i, 0.0) if i in fixed else value
                        for i, value in enumerate(values)
                    )
                    newton += 1
                    continue
                if any(
                    isinstance(p.geometry, Straight)
                    and p.geometry.material_length_mm <= minimum_straight_mm
                    for p in candidate.pieces
                ):
                    stop = "native_sliver"
                    break
                hardware_report = (
                    terminal.certify(candidate, "joint_flat_contact_final")
                    if coupled_contact or on_blocked is not None
                    else terminal.measure(candidate, "joint_flat_contact_final")
                )
                if hardware_report.status != "clear":
                    if (
                        on_blocked is not None
                        and hardware_report.status == "blocked"
                        and hardware_report.witness is not None
                    ):
                        on_blocked(JointHandoff(candidate, hardware_report))
                        stop = "hardware_handoff"
                        break
                    if (
                        not isinstance(evidence, Penetration)
                        and not reflected
                        and not coupled_contact
                        and mode is not JointMode.RADIUS_RESTORATION
                    ):
                        stop = "hardware_not_clear"
                        break
                    extra = FeaturePlane.create(
                        model,
                        candidate,
                        hardware_report,
                        terminal.hardware,
                        values,
                        coverage=FeatureCoverage.ADJOINING_INTERNAL
                        if reflected or coupled_contact
                        else FeatureCoverage.TERMINAL_RUNWAY,
                    )
                    if (
                        len(planes) >= (4 if reflected or coupled_contact else 2)
                        or extra is None
                        or extra in planes
                    ):
                        stop = "hardware_not_clear"
                        break
                    planes.append(extra)
                    if independent_members:
                        scalar_planes = member_planes(planes, model, values)
                        protections = uncovered_terminal_protection(protections, scalar_planes)
                        inequalities = (
                            len(scalar_planes)
                            + len(protections)
                            + (
                                len(constraints) + int(bounded_length)
                                if independent_contacts
                                else 1 + bool(constraints)
                            )
                        )
                        if inequalities > 13:
                            stop = "physical_inequality_capacity"
                            break
                    evaluation.constraints_changed()
                    emit(
                        "hardware_constraint_added",
                        terminal=extra.box.terminal.value,
                        reference=asdict(extra.reference),
                    )
                    continue
                allowed = min(1024, remaining_pairs - pairs)
                if allowed <= 0:
                    stop = "pair_budget"
                    break
                active_pairs = allowed
                contacts += 1
                contact_started = perf_counter()
                measured_contact = inspect_contact(
                    candidate,
                    maximum_pairs=allowed,
                    cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                    checkpoint=bounded,
                    witness_probe=None if penetration_seen else probe,
                    projection_reuse=ProjectionReuse.CELLS,
                )
                measurement = measured_contact
                pairs += measured_contact.pairs_checked
                contact_seconds += perf_counter() - contact_started
                active_pairs = None
                emit("certificate", contact=asdict(measured_contact), route=snapshot(candidate))
                if measured_contact.status == "separated":
                    bounded()
                    accepted, stop = True, "accepted"
                    break
                if (
                    on_blocked is not None
                    and measured_contact.status == "penetration"
                    and measured_contact.witness is not None
                ):
                    if (
                        adaptive_hardware
                        and straight_contact
                        and isinstance(mode, ContactGuidance)
                        and mode.continuation is ContactContinuation.FIRST_FLAT
                        and flat_continuation is None
                    ):
                        bounded()
                        straight_contact_preparations += 1
                        retained = ClosedFlatContinuation.prepare(
                            model, candidate, measured_contact, values
                        )
                        if retained is not None and retain_addition(retained.addition) is None:
                            flat_continuation = retained
                            penetration_seen = True
                            emit("straight_contact_retained", cap_error_mm=cap_error(candidate))
                            bounded()
                            continue
                    bounded()
                    on_blocked(JointHandoff(candidate, measured_contact))
                    stop = "material_handoff"
                    break
                if not coupled_contact and (
                    measured_contact.status != "penetration" or measured_contact.witness is None
                ):
                    stop = "contact_unresolved"
                    break
                penetration_seen = penetration_seen or measured_contact.status == "penetration"
                policy = (
                    ContactPolicy.COUPLED
                    if coupled_contact
                    else ContactPolicy.MATERIAL_RETURN
                    if isinstance(mode, MaterialGuidance)
                    else ContactPolicy.COMPLETE_FLAT
                    if mating_mode
                    else ContactPolicy.ARC_FLAT
                )
                reason = retain_addition(
                    prepare_contact_addition(model, candidate, measured_contact, values, policy)
                )
                if reason is not None:
                    stop = reason
                    break
                continue
            if newton >= 6 * maximum_updates:
                stop = "joint_update_limit"
                break
            jacobian = joint_jacobian(
                model,
                values,
                equations,
                len(terms),
                fixed,
                bounded,
                admissible=admissible,
            )
            project_step = (
                active_step
                if (straight_contact and native_pins)
                or (
                    not reflected
                    and not coupled_contact
                    and (mating_mode or independent_members)
                    and len(terms) > 10
                )
                else project
            )
            delta = project_step(model, values, jacobian, terms, bounded)
            if delta is None:
                if adaptive_hardware and straight_contact and newton == 0 and not constraints:
                    assert isinstance(mode, ContactGuidance)
                    prepared_domain = expand_hardware(original, mode, terminal.hardware, bounded)
                    if prepared_domain is None:
                        stop = "unsupported_hardware_domain"
                        break
                    model = prepared_domain.model
                    planes, scalar_planes = prepared_domain.planes, prepared_domain.members
                    values = model.initial
                    protections = prepare_terminal_protection(
                        model, terminal.hardware, scalar_planes, bounded
                    )
                    if len(scalar_planes) + len(protections) + len(constraints) > 13:
                        stop = "physical_inequality_capacity"
                        break
                    fixed.clear()
                    native_pins.clear()
                    straight_contact, hardware_expanded = False, True
                    project = partial(
                        redistributed_step,
                        evidence=projection_evidence,
                        guidance_policy=restoration_policy,
                    )
                    evaluation = JointEvaluation(raw_equations, model.admissible)
                    equations, admissible = evaluation.equations, evaluation.admissible
                    emit(
                        "hardware_motion_expanded",
                        newton_steps=newton,
                        reason="linear_projection_infeasible",
                    )
                    continue
                if mode is JointMode.BLOCKED_MATING and not length_released:
                    parts = member_planes(planes, model, values)
                    if len(parts) + len(constraints) > 13:
                        stop = "physical_inequality_capacity"
                        break
                    length_released, bounded_length, independent_members = True, False, True
                    scalar_planes = parts
                    evaluation.constraints_changed()
                    emit(
                        "blocked_length_goal_released",
                        newton_steps=newton,
                        length_goal_mm=maximum_length_mm,
                    )
                    continue
                stop = "linear_projection_infeasible"
                break
            native_candidates = {
                i
                for i in model.straight_indices
                if values[i] == 0 and abs(delta[i]) * model.scale <= minimum_straight_mm
            }
            if reflected or coupled_contact:
                native_candidates.update(
                    i
                    for i in model.straight_indices
                    if 0 < (values[i] + delta[i]) * model.scale <= minimum_straight_mm
                )
            if native_candidates:
                if (reflected or coupled_contact) and not straight_contact:
                    absent_step = zero_step(
                        values,
                        frozenset(native_candidates),
                        delta,
                        jacobian,
                        terms,
                        restoration_policy,
                    )
                    if absent_step is not None:
                        native_zero_face_selections += 1
                        emit(
                            "native_zero_faces_selected",
                            slots=sorted(i for i in native_candidates if values[i] == 0),
                        )
                        delta = absent_step
                native_domain = None
                frozen_native = native_candidates
                if (
                    (reflected or coupled_contact)
                    and minimum_straight_mm > 0
                    and any(values[index] + delta[index] > 0 for index in native_candidates)
                ):
                    native_domain = bind_native_slots(
                        model,
                        values,
                        frozenset(native_candidates),
                        delta,
                        minimum_straight_mm,
                        model.scale,
                    )
                    if native_domain is None:
                        stop = "native_projection_infeasible"
                        break
                    frozen_native = set(native_domain.frozen)
                    native_positive_projections += 1
                    emit(
                        "native_positive_slot_projection",
                        positive_slots=sorted(native_domain.positive),
                        frozen_slots=sorted(native_domain.frozen),
                        floor_mm=native_domain.minimum * model.scale,
                        original_steps_mm={
                            str(i): delta[i] * model.scale for i in native_candidates
                        },
                        original_lengths_mm={
                            str(i): values[i] * model.scale for i in native_candidates
                        },
                        proposed_lengths_mm={
                            str(i): (values[i] + delta[i]) * model.scale for i in native_candidates
                        },
                    )
                jacobian = [
                    [0.0 if i in frozen_native else value for i, value in enumerate(row)]
                    for row in jacobian
                ]
                if native_domain is None:
                    delta = project_step(model, values, jacobian, terms, bounded)
                elif straight_contact:
                    delta = active_step(native_domain, values, jacobian, terms, bounded)
                else:
                    delta = redistributed_step(
                        native_domain,
                        values,
                        jacobian,
                        terms,
                        bounded,
                        evidence=projection_evidence,
                        guidance_policy=restoration_policy,
                    )
                if delta is None:
                    stop = "native_projection_infeasible"
                    break
            if native_pins:
                delta = tuple(0.0 if i in native_pins else change for i, change in enumerate(delta))
            fraction = step_limit(model, values, delta, 1.0)
            predicted = tuple(
                term + math.fsum(a * b for a, b in zip(row, delta))
                for row, term in zip(jacobian, terms)
            )
            linear_error = max(
                tuple(abs(term) for term in predicted[:6])
                + tuple(max(0.0, term) for term in predicted[6:])
            )
            predicted_change = linear_error - error
            for _ in range(4):
                bounded()
                trial = advance(model, values, delta, fraction)
                trial_error = merit(trial) if admissible(trial) else None
                if trial_error is not None and trial_error < error:
                    values, newton = trial, newton + 1
                    break
                fraction = contracted_fraction(fraction, error, trial_error, predicted_change)
            else:
                stop = "joint_no_descent"
                break
            emit("update", newton=newton, values=values, residual=equations(values))
        if (
            on_blocked is not None
            and stop in ("linear_projection_infeasible", "joint_no_descent")
            and flat_continuation is not None
            and flat_continuation.unchanged(values, candidate)
        ):
            bounded()
            emit("straight_contact_fallback_prepared", original_stop=stop)
            bounded()
            on_blocked(flat_continuation.state)
            straight_contact_decline, stop = stop, "material_handoff"
            straight_contact_fallbacks += 1
        if (
            on_restoration_blocked is not None
            and stop in ("linear_projection_infeasible", "joint_no_descent", "new_material_return")
            and restoration_witness is not None
            and restoration_witness[0] == values
        ):
            bounded()
            state = RestorationHandoff(
                candidate,
                restoration_witness[1],
                cast(RestorationStop, stop),
            )
            restoration_inverse_checks = 2
            emit(
                "material_restoration_prepared",
                original_stop=stop,
                next_fold=next_return,
                cap_error_mm=cap_error(candidate),
                witness=asdict(state.evidence.witness),
                inverse_checks=2,
            )
            bounded()
            on_restoration_blocked(state)
            restoration_decline, stop = stop, "material_restoration_handoff"
    except _Exhausted:
        stop = "phase_budget"
        pairs += active_pairs or 0
        if active_pairs is not None:
            interrupted_pairs = active_pairs
            if screen_active:
                screen_pairs += active_pairs
                screen_seconds += perf_counter() - contact_started
            contact_seconds += perf_counter() - contact_started
    detail: dict[str, Any] = {
        "status": "separated" if accepted else "unresolved",
        "method": "complete_flat_contacts",
        "iterations": math.ceil(newton / 6),
        "newton_steps": newton,
        "contacts": contacts,
        "contact_pairs": pairs,
        "contact_seconds": contact_seconds,
        "cpu_seconds": process_time() - cpu,
        "elapsed_seconds": perf_counter() - wall,
        "length_mm": candidate.material_length_mm,
        "maximum_length_mm": maximum_length_mm,
        "stop_reason": stop,
        "flat_constraints": len(constraints),
        "probe": asdict(probe),
        "terminal_protection_constraints": len(protections),
        "native_positive_slot_projections": native_positive_projections,
        "native_zero_face_selections": native_zero_face_selections,
        "ordered_cap_completions": ordered_cap_completions,
        "straight_contact_preparations": straight_contact_preparations,
        "straight_contact_retained": int(flat_continuation is not None),
        "straight_contact_fallbacks": straight_contact_fallbacks,
        "native_sliver_extensions": len(native_pins),
        "restoration_screen_checks": screen_checks,
        "restoration_screen_pairs": screen_pairs,
        "restoration_screen_seconds": screen_seconds,
        "restoration_handoff_inverse_checks": restoration_inverse_checks,
    }
    if straight_contact_decline is not None:
        detail["straight_contact_decline"] = straight_contact_decline
    if restoration_decline is not None:
        detail["restoration_decline"] = restoration_decline
    if length_released:
        detail.update(
            length_ceiling_released=True,
            length_goal_mm=maximum_length_mm,
            length_goal_excess_mm=max(0.0, candidate.material_length_mm - maximum_length_mm),
        )
    if runway_evidence.attempts:
        detail["runway_minimization"] = asdict(runway_evidence)
    if mode is JointMode.RADIUS_RESTORATION:
        detail.update(
            radius_restoration=True,
            feature_constraints=len(planes),
            scalar_feature_constraints=len(scalar_planes),
            selected_fold=selected,
            length_goal_mm=maximum_length_mm,
            length_goal_excess_mm=max(0.0, candidate.material_length_mm - maximum_length_mm),
            radius_floor_mm=original.radius_mm,
        )
    if isinstance(mode, (IncidentGuidance, MaterialGuidance)):
        detail.update(
            method="complete_material_return"
            if isinstance(mode, MaterialGuidance)
            else "complete_incident_features",
            selected_fold=selected,
            feature_constraints=len(planes),
            scalar_feature_constraints=len(scalar_planes),
            maximum_linear_steps=16,
            linear_projection="redistributed_cap_restoration",
        )
        if isinstance(mode, MaterialGuidance):
            detail.update(
                length_policy=mode.length.value,
                length_goal_mm=maximum_length_mm,
                length_goal_excess_mm=max(0.0, candidate.material_length_mm - maximum_length_mm),
            )
    if isinstance(mode, ContactGuidance):
        detail.update(
            method="coupled_contact_refinement",
            feature_constraints=len(planes),
            scalar_feature_constraints=len(scalar_planes),
            maximum_linear_steps=16,
            linear_projection="fixed_bend_active_projection"
            if straight_contact
            else "redistributed_cap_restoration",
            length_goal_mm=maximum_length_mm,
            length_goal_excess_mm=max(0.0, candidate.material_length_mm - maximum_length_mm),
            motion_policy=mode.motion.value,
            hardware_domain_expanded=hardware_expanded,
        )
    if reflected or (coupled_contact and not straight_contact):
        detail.update(
            motion_regularization="cap_step_normalized_merit_squared",
            guidance_restoration=restoration_policy.value,
            guidance_tradeoff_proposals=projection_evidence.guidance_tradeoff_proposals,
            coordinate_seed_attempts=projection_evidence.coordinate_seed_attempts,
            coordinate_seed_faces=projection_evidence.coordinate_seed_faces,
            cap_metric_calibrations=projection_evidence.cap_metric_calibrations,
            active_face_restorations=projection_evidence.active_face_restorations,
            working_set_exhaustions=projection_evidence.exhaustions,
            raw_gate_rejected_vectors=projection_evidence.raw_gate_rejections,
            bounded_projection_proposals=projection_evidence.bounded_proposals,
            bound_clipped_proposals=projection_evidence.bound_clipped_proposals,
            halfspace_contracted_proposals=projection_evidence.halfspace_contracted_proposals,
        )
    if interrupted_pairs is not None:
        detail["interrupted_pairs_charged_as_upper_bound"] = interrupted_pairs
    emit(detail["status"], detail=detail, candidate=snapshot(candidate))
    return Result(candidate if accepted else original, measurement if accepted else None, detail)
