"""
Close exact caps, finite connector clearance and complete measured material contact regions together.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from enum import Enum
from functools import partial
from time import perf_counter, process_time
from typing import Any, Callable, Union

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
from .check import Report
from .feature_guidance import (
    ContactGuidance,
    ContactMotion,
    IncidentGuidance,
    MaterialGuidance,
    ReturnLength,
    member_planes,
)
from .feature_plane import FeatureCoverage, FeaturePlane, SignedJoints
from .flat_separation import FlatSeparation, ProfileExtent
from .gate import Gate
from .hardware_motion import expand as expand_hardware
from .incident_model import IncidentJoints
from .joint_derivatives import jacobian as joint_jacobian
from .joint_evaluation import JointEvaluation
from .joint_handoff import JointHandoff
from .line_search import contracted_fraction
from .material_constraint import MaterialConstraint
from .quality_projection import quality_step
from .radius_model import RadiusJoints
from .recovery_limits import validate
from .redistributed_projection import ProjectionEvidence, redistributed_step
from .reversal_model import incident_fold
from .run_translation import StraightSlots
from .straight_projection import RunwayEvidence, shortest_run_step
from .straight_quality import StraightQuality


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
) -> Result | None:
    """
    Use remaining original work on caps and actual connector or flat-contact evidence.

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
    Adaptive hardware motion first uses the unchanged straight-only policy. Only
    an initial projection returning no step, before any Newton motion and without
    material uncertainty, may rebind the same actual hardware features to the
    signed-joint domain. Model-bound caches are replaced, all original clocks and
    counters continue, and no second expansion or alternative sign is tried.
    Rejected nonlinear steps use safeguarded quadratic contraction from the
    existing linear prediction and observed merit. Inadmissible trials halve.
    The same four trials and strict nonlinear descent remain mandatory.
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
    if (
        independent_members
        and len(scalar_planes) + len(constraints) + int(not coupled_contact) > 13
    ):
        return None
    projection_evidence = ProjectionEvidence()
    runway_evidence = RunwayEvidence()
    project = (
        partial(shortest_run_step, evidence=runway_evidence)
        if straight_contact
        else partial(redistributed_step, evidence=projection_evidence)
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

    try:
        emit(
            "started",
            source=snapshot(original),
            maximum_length_mm=maximum_length_mm,
            remaining_updates=maximum_updates,
            remaining_pairs=remaining_pairs,
            initial_flat_constraints=len(constraints),
            initial_hardware_members=len(scalar_planes),
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
            if error < 1e-13:
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
                    fixed.update(slivers)
                    values = tuple(0.0 if i in fixed else value for i, value in enumerate(values))
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
                        inequalities = len(scalar_planes) + (
                            len(constraints) + int(bounded_length)
                            if independent_contacts
                            else 1 + bool(constraints)
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
                    on_blocked(JointHandoff(candidate, measured_contact))
                    stop = "material_handoff"
                    break
                if not coupled_contact and (
                    measured_contact.status != "penetration" or measured_contact.witness is None
                ):
                    stop = "contact_unresolved"
                    break
                penetration_seen = penetration_seen or measured_contact.status == "penetration"
                witness = measured_contact.witness
                if coupled_contact or isinstance(mode, MaterialGuidance):
                    created_bound = MaterialConstraint.create(model, candidate, measured_contact)
                else:
                    assert witness is not None
                    created_bound = FlatSeparation.create(
                        model,
                        candidate,
                        witness,
                        extent=ProfileExtent.COMPLETE
                        if mating_mode or isinstance(mode, MaterialGuidance)
                        else ProfileExtent.ARC,
                    )
                if created_bound is None or len(constraints) >= 4:
                    stop = "unsupported_or_exhausted_flat_constraints"
                    break
                bound: FlatSeparation | MaterialConstraint = created_bound
                if coupled_contact:
                    key = (bound.pair, bound.parts)
                else:
                    assert witness is not None
                    key = (
                        bound.pair,
                        tuple(round(v, 8) for v in witness.first[:2]),
                        tuple(round(v, 8) for v in witness.second[:2]),
                    )
                if key in keys:
                    stop = "repeated_contact_witness"
                    break
                side = max(
                    Side,
                    key=lambda chosen: (
                        bound.gap(values if coupled_contact else model.initial, chosen),
                        -chosen.value,
                    ),
                )
                keys.add(key)
                inequalities = len(scalar_planes) + (
                    len(constraints) + 1 + int(bounded_length) if independent_contacts else 2
                )
                if independent_members and inequalities > 13:
                    stop = "physical_inequality_capacity"
                    break
                constraints.append((bound, side))
                evaluation.constraints_changed()
                emit(
                    "constraint_added",
                    witness=None if witness is None else asdict(witness),
                    pair=[asdict(tag) for tag in bound.pair],
                    parts=[
                        {"phase": part.phase.value, "q": (part.low_q, part.high_q)}
                        for part in bound.parts
                    ],
                    side=side.name,
                    gap_mm=bound.gap(values, side) * model.scale,
                )
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
                if not reflected
                and not coupled_contact
                and (mating_mode or independent_members)
                and len(terms) > 10
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
                    fixed.clear()
                    straight_contact, hardware_expanded = False, True
                    project = partial(redistributed_step, evidence=projection_evidence)
                    evaluation = JointEvaluation(raw_equations, model.admissible)
                    equations, admissible = evaluation.equations, evaluation.admissible
                    emit("hardware_motion_expanded", newton_steps=newton)
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
            native_zero = {
                i
                for i in model.straight_indices
                if values[i] == 0 and abs(delta[i]) * model.scale <= minimum_straight_mm
            }
            if native_zero:
                jacobian = [
                    [0.0 if i in native_zero else value for i, value in enumerate(row)]
                    for row in jacobian
                ]
                delta = project_step(model, values, jacobian, terms, bounded)
                if delta is None:
                    stop = "native_projection_infeasible"
                    break
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
    except _Exhausted:
        stop = "phase_budget"
        pairs += active_pairs or 0
        if active_pairs is not None:
            interrupted_pairs = active_pairs
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
    }
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
            motion_regularization="maximum_merit_squared",
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
