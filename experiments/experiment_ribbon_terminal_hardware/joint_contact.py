"""
Close exact caps, finite connector clearance and complete measured flat contact regions together.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from enum import Enum
from time import perf_counter, process_time
from typing import Any, Callable

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
from .feature_guidance import IncidentGuidance, member_planes
from .feature_plane import FeatureCoverage, FeaturePlane, SignedJoints
from .flat_separation import FlatSeparation, ProfileExtent
from .gate import Gate
from .incident_model import IncidentJoints
from .joint_derivatives import jacobian as joint_jacobian
from .joint_evaluation import JointEvaluation
from .quality_projection import quality_step
from .radius_model import RadiusJoints
from .recovery_limits import validate
from .reversal_model import incident_fold
from .straight_quality import StraightQuality


class JointMode(Enum):
    """
    Distinguish parent improvement, bounded mating restoration and one-radius physical restoration.
    """

    PARENT_CEILING = "parent_ceiling"
    MATING_CEILING = "mating_ceiling"
    RADIUS_RESTORATION = "radius_restoration"


class _Exhausted(RuntimeError):
    """
    Stop only this optional shared allocation without masking caller cancellation or resource errors.
    """


def recover(
    original: FoldRoute,
    evidence: Report | Penetration,
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
    mode: JointMode | IncidentGuidance = JointMode.PARENT_CEILING,
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
    Mating restoration retains each witnessed flat contact as an independent
    full-profile inequality. More than four scalar inequalities use the existing
    sixteen-step active projection; constraint, update, time and pair limits stay
    unchanged. Other modes retain their original aggregated profile-arc guidance.
    A strict material crossing can initialize complete-profile flat guidance
    without inventing hardware intrusion. Only that entry can subsequently add
    up to two demonstrated connector planes; legacy hardware entries retain
    their original single-plane stopping behavior and profile-arc guidance.
    Incident guidance retains actual prior reports, reflects their one witnessed
    event and gives occupied members independent separating planes. At most four
    features/thirteen physical inequalities use sixteen dual active-set steps,
    replacing scalar subset enumeration under the same caller work allocation.
    """
    if not isinstance(mode, (JointMode, IncidentGuidance)):
        raise ValueError("Supply an explicit joint recovery mode")
    validate(
        remaining_pairs=remaining_pairs,
        maximum_cpu_seconds=maximum_cpu_seconds,
        maximum_seconds=maximum_seconds,
        maximum_updates=maximum_updates,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
    )
    cpu, wall = process_time(), perf_counter()
    selected: int | None = None
    model: SignedJoints
    if isinstance(mode, IncidentGuidance):
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
    else:
        model = SignedJoints(original)
    values = model.initial
    constraints: list[tuple[FlatSeparation, Side]] = []
    planes: list[FeaturePlane] = []
    if isinstance(mode, IncidentGuidance):
        prepared = mode.planes(model, terminal.hardware, values)
        if prepared is None:
            return None
        planes = prepared
    elif isinstance(evidence, Report):
        plane = FeaturePlane.create(model, original, evidence, terminal.hardware, values)
        if plane is None:
            return None
        planes.append(plane)
    elif isinstance(evidence, Penetration):
        initial = FlatSeparation.create(model, original, evidence, extent=ProfileExtent.COMPLETE)
        if initial is None:
            return None
        constraints.append((initial, Side.BEFORE))
    else:
        raise ValueError(
            "Initialize joint work from measured hardware or material crossing evidence"
        )
    scalar_planes = (
        member_planes(planes, model, values) if isinstance(mode, IncidentGuidance) else planes
    )
    if isinstance(mode, IncidentGuidance) and len(scalar_planes) + 1 > 13:
        return None
    project = active_step if isinstance(mode, IncidentGuidance) else quality_step
    bounded_length = mode is not JointMode.RADIUS_RESTORATION
    length_target = (
        StraightQuality(maximum_length_mm, maximum_updates).target_mm
        if mode is JointMode.MATING_CEILING
        else maximum_length_mm - 1e-7
        if isinstance(mode, IncidentGuidance)
        else maximum_length_mm
    )
    keys: set[tuple[Any, ...]] = set()
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
            1e-7 / model.scale - plane.gap(coordinates) for plane in scalar_planes
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
            equation_terms += flat_terms if mode is JointMode.MATING_CEILING else (max(flat_terms),)
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
                hardware_report = terminal.measure(candidate, "joint_flat_contact_final")
                if hardware_report.status != "clear":
                    if not isinstance(evidence, Penetration) and not isinstance(
                        mode, IncidentGuidance
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
                        if isinstance(mode, IncidentGuidance)
                        else FeatureCoverage.TERMINAL_RUNWAY,
                    )
                    if (
                        len(planes) >= (4 if isinstance(mode, IncidentGuidance) else 2)
                        or extra is None
                        or extra in planes
                    ):
                        stop = "hardware_not_clear"
                        break
                    planes.append(extra)
                    if isinstance(mode, IncidentGuidance):
                        scalar_planes = member_planes(planes, model, values)
                        if len(scalar_planes) + 1 + bool(constraints) > 13:
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
                if measured_contact.status != "penetration" or measured_contact.witness is None:
                    stop = "contact_unresolved"
                    break
                penetration_seen = True
                created_bound = FlatSeparation.create(
                    model,
                    candidate,
                    measured_contact.witness,
                    extent=ProfileExtent.COMPLETE
                    if mode is JointMode.MATING_CEILING
                    else ProfileExtent.ARC,
                )
                if created_bound is None or len(constraints) >= 4:
                    stop = "unsupported_or_exhausted_flat_constraints"
                    break
                bound: FlatSeparation = created_bound
                witness = measured_contact.witness
                key = (
                    bound.pair,
                    tuple(round(v, 8) for v in witness.first[:2]),
                    tuple(round(v, 8) for v in witness.second[:2]),
                )
                if key in keys:
                    stop = "repeated_contact_witness"
                    break
                side = max(
                    Side, key=lambda chosen: (bound.gap(model.initial, chosen), -chosen.value)
                )
                keys.add(key)
                if isinstance(mode, IncidentGuidance) and len(scalar_planes) + 2 > 13:
                    stop = "physical_inequality_capacity"
                    break
                constraints.append((bound, side))
                evaluation.constraints_changed()
                emit(
                    "constraint_added",
                    witness=asdict(witness),
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
                active_step if mode is JointMode.MATING_CEILING and len(terms) > 10 else project
            )
            delta = project_step(model, values, jacobian, terms, bounded)
            if delta is None:
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
            for _ in range(4):
                bounded()
                trial = advance(model, values, delta, fraction)
                if admissible(trial) and merit(trial) < error:
                    values, newton = trial, newton + 1
                    break
                fraction /= 2
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
    if mode is JointMode.RADIUS_RESTORATION:
        detail.update(
            radius_restoration=True,
            selected_fold=selected,
            length_goal_mm=maximum_length_mm,
            length_goal_excess_mm=max(0.0, candidate.material_length_mm - maximum_length_mm),
            radius_floor_mm=original.radius_mm,
        )
    if isinstance(mode, IncidentGuidance):
        detail.update(
            method="complete_incident_features",
            selected_fold=selected,
            feature_constraints=len(planes),
            scalar_feature_constraints=len(scalar_planes),
            maximum_linear_steps=16,
        )
    if interrupted_pairs is not None:
        detail["interrupted_pairs_charged_as_upper_bound"] = interrupted_pairs
    emit(detail["status"], detail=detail, candidate=snapshot(candidate))
    return Result(candidate if accepted else original, measurement if accepted else None, detail)
