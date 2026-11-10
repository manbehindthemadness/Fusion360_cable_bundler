"""
Close measured fold-feature clearance and endpoint equations in one bounded nonlinear system.
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
from experiments.experiment_ribbon_fold_relaxation.steps import advance, projected, step_limit
from experiments.experiment_ribbon_fold_route.contact import ProjectionReuse, inspect_contact
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight

from .active_projection import active_step
from .check import Report
from .feature_guidance import FeatureGate, RetainedFeatures, member_planes
from .feature_plane import FeaturePlane, SignedJoints
from .joint_derivatives import jacobian as joint_jacobian
from .joint_evaluation import JointEvaluation
from .native_projection import native_slot_step
from .quality_projection import quality_step
from .recovery_limits import validate
from .straight_quality import StraightQuality
from .workspace import redistribution


class FeatureProjection(Enum):
    """
    Preserve grouped legacy closure or continue measured failure with independent member bounds.
    """

    GROUPED = "grouped"
    MEMBERS = "members"


class _Exhausted(RuntimeError):
    """
    Stop only the allocated optional recovery work, never caller resource/source failures.
    """


def recover(
    original: FoldRoute,
    evidence: Report,
    terminal: FeatureGate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    remaining_pairs: int,
    maximum_cpu_seconds: float,
    maximum_seconds: float,
    quality: StraightQuality | None = None,
    maximum_updates: int = 4,
    continuation: RetainedFeatures | None = None,
    projection: FeatureProjection = FeatureProjection.GROUPED,
) -> Result | None:
    """
    Preserve signs/radii while solving caps and measured feature planes inside original work limits.

    Caller validates and reserves the same idle feasibility allowance. Up to 24
    Newton steps represent four six-correction updates, with 0.2 radian trust and
    four scalar halvings. Every new constraint requires a demonstrated intrusion;
    previous constraints stay active. No angle/event/axis-family candidates are
    searched after selection. Full contact and both boxes remain mandatory.
    Grouped corrections may prefer transferring existing interior straight travel
    into a blocked terminal fold's neighbouring gap while sharing its turn. This
    changes only the projection reference, not the cap/feature equations, quality
    ceiling or work allowance; uniform feature spacing is not required. Apply
    that preference once per measured feature set, then reclose without injecting
    another nullspace displacement on every Newton correction.
    Local quality growth is bounded by original construction length plus the
    initial complete-feature projected penetration; it is not a physical tolerance.
    Closed proposals with sub-native runways fix those slots at zero and reclose
    all equations before hardware and self-contact certification, without renewing
    any allowance. A tiny terminal runway must not strand the following fold
    outside the analytic mating proof while consuming clearance subdivision work.
    Straight-quality recovery additionally closes the original length ceiling as
    an active equation and uses only the caller's remaining update count. Ordinary
    fold recovery retains its overlap-based ceiling. Only if its closed proposal
    exceeds that ceiling, use the same coordinates and genuinely remaining work
    to solve clearance/length inequalities alongside the cap equalities. No
    successful legacy proposal enters that additional action.
    A reduced caller allocation retains six corrections per remaining update;
    absent sub-native slots are excluded from each linear correction before
    cap reclosure, rather than creating numerical dust and cleaning it afterward.
    A trial that would erase a fold ends this action with a measured domain
    boundary and completed counters. It cannot be evaluated as the original
    material region or consume a fresh recovery allowance.
    Final contact certificates reuse at most512identical cell projections;
    arithmetic, material traversal, comparison counts and limits stay unchanged.
    If a length-constrained correction stalls, release that quality restriction
    once and continue from the same coordinates with unused corrections only.
    Physical caps, material, feature clearance and contact remain mandatory.
    Member projection uses independent complete-member clearance inequalities only
    for a measured failed continuation; grouped legacy successes remain unchanged.
    The same bounded active projection handles more than four scalar inequalities.
    An explicit quality policy with retained member projection activates its
    unchanged ceiling inequality immediately. Other quality entries retain their
    original grouped equations; no allocation or preceding ceiling is renewed.
    A typed continuation may rebind three earlier actual reports after an
    incident reflection failed without motion. Ordinary entry retains its
    two-feature handoff. This continuation receives only genuinely unused work
    and the preceding ceiling, without adding a new overlap allowance.
    """
    validate(
        remaining_pairs=remaining_pairs,
        maximum_cpu_seconds=maximum_cpu_seconds,
        maximum_seconds=maximum_seconds,
        maximum_updates=maximum_updates,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
    )
    if quality is not None and quality.remaining_updates > maximum_updates:
        raise ValueError("Quality policy cannot renew the remaining update allocation")
    if quality is not None and quality.ceiling_mm != maximum_length_mm:
        raise ValueError("Straight recovery must retain the caller's original quality ceiling")
    if continuation is not None and (
        not isinstance(continuation, RetainedFeatures)
        or quality is not None
        and projection is not FeatureProjection.MEMBERS
    ):
        raise ValueError("Use retained evidence with its preceding ceiling and unused allocation")
    if not isinstance(projection, FeatureProjection):
        raise ValueError("Use an explicit feature projection policy")
    if projection is FeatureProjection.MEMBERS and continuation is None:
        raise ValueError(
            "Member projection requires measured continuation and unused physical work"
        )
    started, cpu = perf_counter(), process_time()
    model = SignedJoints(original)
    values = model.initial
    fixed_zero: set[int] = set()
    growth_quality = projection is FeatureProjection.MEMBERS and quality is not None
    length_released = False
    if continuation is None:
        initial = FeaturePlane.create(model, original, evidence, terminal.hardware, values)
        if initial is None:
            return None
        planes = [initial]
    else:
        prepared = continuation.planes(model, terminal.hardware, values)
        if not prepared:
            return None
        planes, initial = prepared, prepared[0]
    member_guidance = projection is FeatureProjection.MEMBERS
    scalar_planes = member_planes(planes, model, values) if member_guidance else planes
    allowance = max(0.0, -initial.gap(values) * model.scale)
    ceiling = (
        maximum_length_mm
        if continuation is not None
        else quality.ceiling_mm
        if quality is not None
        else maximum_length_mm + allowance
    )
    maximum_newton_steps = quality.newton_steps if quality is not None else 6 * maximum_updates
    candidate, accepted, measurement = original, False, None
    detail: dict[str, Any] = {
        "status": "unresolved",
        "purpose": "terminal_clearance",
        "method": "constrained_straight_feature"
        if quality is not None
        else "coupled_feature_planes",
        "iterations": 0,
        "newton_steps": 0,
        "contacts": 0,
        "contact_pairs": 0,
        "contact_seconds": 0.0,
        "maximum_length_mm": ceiling,
        "local_growth_allowance_mm": allowance if quality is None and continuation is None else 0.0,
    }
    active_pairs: int | None = None
    contact_started = 0.0
    workspace_constraints = 0

    def bounded() -> None:
        """
        Keep all preparation, closure and certificates inside the original caller sublimits.
        """
        checkpoint()
        if (
            process_time() - cpu >= maximum_cpu_seconds
            or perf_counter() - started >= maximum_seconds
        ):
            raise _Exhausted("Coupled feature recovery allowance exhausted")

    def emit(status: str, **data: Any) -> None:
        """
        Preserve every constraint, motion and actual certificate in the numerical ledger.
        """
        record({"stage": "coupled_feature_recovery", "status": status, **data})

    def release_length(trigger: str) -> bool:
        """
        Release a stalled quality limit once without resetting coordinates or the work allocation.
        """
        nonlocal length_released
        if quality is None or length_released or detail["newton_steps"] >= maximum_newton_steps:
            return False
        length_released = True
        evaluation.constraints_changed()
        detail["length_ceiling_released"] = True
        detail["length_release_trigger"] = trigger
        emit(
            "length_released",
            trigger=trigger,
            values=values,
            newton_steps=detail["newton_steps"],
            remaining_newton=maximum_newton_steps - detail["newton_steps"],
        )
        return True

    def raw_equations(coordinates: tuple[float, ...]) -> tuple[float, ...]:
        """
        Retain raw derivatives at cleared inequality boundaries instead of differentiating a clip.
        """
        if growth_quality or member_guidance:
            limits = tuple(1e-7 / model.scale - p.gap(coordinates) for p in scalar_planes)
            if quality is not None and not length_released:
                route_for_limits = model.route(coordinates)
                assert route_for_limits is not None
                limits += ((route_for_limits.material_length_mm - quality.target_mm) / model.scale,)
            return model.residual(coordinates) + limits
        residual_terms = model.residual(coordinates) + tuple(
            p.gap(coordinates) - 1e-7 / model.scale for p in scalar_planes
        )
        if quality is not None and not length_released:
            evaluated_route = model.route(coordinates)
            assert evaluated_route is not None
            residual_terms += (
                (evaluated_route.material_length_mm - quality.target_mm) / model.scale,
            )
        return residual_terms

    evaluation = JointEvaluation(raw_equations, model.admissible)
    equations, admissible = evaluation.equations, evaluation.admissible

    def residual(coordinates: tuple[float, ...]) -> tuple[float, ...]:
        """
        Measure cap errors and only violated bounds during growth-constrained closure.
        """
        terms = equations(coordinates)
        return (
            terms[:6] + tuple(max(0.0, term) for term in terms[6:])
            if growth_quality or member_guidance
            else terms
        )

    try:
        emit(
            "started",
            source=snapshot(original),
            evidence=asdict(evidence),
            length_ceiling_mm=ceiling,
        )
        while True:
            bounded()
            equation = residual(values)
            error = max(map(abs, equation))
            if error < 1e-13:
                proposed = model.route(values)
                assert proposed is not None
                candidate = proposed
                if cap_error(candidate) > 1e-7 or material_error(candidate) > 1e-10:
                    raise ArithmeticError("Coupled feature recovery lost cap/material closure")
                if not model.preserves(candidate):
                    detail["stop_reason"] = "fold_identity"
                    break
                if not length_released and candidate.material_length_mm > ceiling:
                    remaining_updates = maximum_updates - math.ceil(detail["newton_steps"] / 6)
                    if quality is None and remaining_updates > 0:
                        quality = StraightQuality(ceiling, remaining_updates)
                        growth_quality = True
                        evaluation.constraints_changed()
                        maximum_newton_steps = min(
                            maximum_newton_steps, detail["newton_steps"] + quality.newton_steps
                        )
                        detail["method"] = "constrained_fold_feature"
                        emit(
                            "quality_activated",
                            route=snapshot(candidate),
                            remaining_updates=remaining_updates,
                            length_ceiling_mm=ceiling,
                        )
                        continue
                    detail["stop_reason"] = "local_growth_ceiling"
                    break
                slivers = {
                    i
                    for i in model.straight_indices
                    if 0 < values[i] * model.scale <= minimum_straight_mm
                }
                if slivers:
                    fixed_zero.update(slivers)
                    values = tuple(0.0 if i in fixed_zero else v for i, v in enumerate(values))
                    emit("native_slots_zeroed", indices=sorted(slivers))
                    continue
                if any(
                    isinstance(p.geometry, Straight)
                    and p.geometry.material_length_mm <= minimum_straight_mm
                    for p in candidate.pieces
                ):
                    detail["stop_reason"] = "native_sliver"
                    break
                report = terminal.certify(candidate, "coupled_feature_candidate")
                if report.status == "clear":
                    pairs = min(1024, remaining_pairs - detail["contact_pairs"])
                    if pairs <= 0:
                        detail["stop_reason"] = "construction_pair_budget"
                        break
                    active_pairs, contact_started = pairs, perf_counter()
                    detail["contacts"] += 1
                    measurement = inspect_contact(
                        candidate,
                        maximum_pairs=pairs,
                        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                        checkpoint=bounded,
                        projection_reuse=ProjectionReuse.CELLS,
                    )
                    detail["contact_pairs"] += measurement.pairs_checked
                    detail["contact_seconds"] += perf_counter() - contact_started
                    active_pairs = None
                    emit("contact", route=snapshot(candidate), contact=asdict(measurement))
                    if measurement.status != "separated":
                        detail["stop_reason"] = "self_contact_not_separated"
                        break
                    bounded()
                    accepted = True
                    detail["status"] = "separated"
                    break
                if len(planes) >= (3 if continuation is not None else 2):
                    detail["stop_reason"] = "feature_constraint_limit"
                    break
                extra = FeaturePlane.create(model, candidate, report, terminal.hardware, values)
                if extra is None:
                    detail["stop_reason"] = "unsupported_terminal_evidence"
                    break
                planes.append(extra)
                evaluation.constraints_changed()
                if member_guidance:
                    scalar_planes = member_planes(planes, model, values)
                if growth_quality or member_guidance:
                    fixed_zero.clear()
                emit(
                    "constraint_added",
                    reference=asdict(extra.reference),
                    members=[asdict(m) for m in extra.members],
                    terminal=extra.box.terminal.value,
                    axis_family=extra.family,
                )
                continue
            if detail["newton_steps"] >= maximum_newton_steps:
                detail["stop_reason"] = "joint_update_limit"
                break
            jacobian = joint_jacobian(
                model,
                values,
                equations,
                len(equation),
                fixed_zero,
                bounded,
                admissible=admissible,
            )
            workspace = None
            if not (growth_quality or member_guidance) and len(planes) > workspace_constraints:
                workspace = redistribution(model, values, planes)
                workspace_constraints = len(planes)
            if workspace is not None:
                emit(
                    "workspace_direction",
                    donor_slot=workspace.donor_slot,
                    receiving_slots=workspace.receiving_slots,
                    terminal_folds=workspace.terminal_folds,
                    reference=workspace.reference,
                )
            delta = (
                (active_step if len(equations(values)) > 10 else quality_step)(
                    model, values, jacobian, equations(values), bounded
                )
                if growth_quality or member_guidance
                else projected(
                    model,
                    values,
                    jacobian,
                    [-v for v in equation],
                    list(workspace.reference) if workspace is not None else [0.0] * len(values),
                )
            )
            if delta is None:
                if release_length("joint_projection_infeasible"):
                    continue
                detail["stop_reason"] = "joint_projection_infeasible"
                break
            if maximum_updates < 4 and quality is None:
                delta = native_slot_step(
                    model, values, jacobian, equation, delta, minimum_straight_mm
                )
                if delta is None:
                    detail["stop_reason"] = "native_active_projection_infeasible"
                    break
            blocked = {
                i
                for i in model.straight_indices
                if growth_quality and delta[i] < 0 <= values[i] * model.scale <= minimum_straight_mm
            }
            if blocked:
                fixed_zero.update(blocked)
                values = tuple(0.0 if i in fixed_zero else v for i, v in enumerate(values))
                detail["newton_steps"] += 1
                detail["iterations"] = math.ceil(detail["newton_steps"] / 6)
                emit("active_native_slots_zeroed", indices=sorted(blocked))
                continue
            step = step_limit(model, values, delta, 1.0)
            for _ in range(4):
                bounded()
                trial = advance(model, values, delta, step)
                if not admissible(trial):
                    detail["stop_reason"] = "fold_boundary"
                    emit("fold_boundary", values=values, trial=trial)
                    break
                if max(map(abs, residual(trial))) < error:
                    values = trial
                    detail["newton_steps"] += 1
                    detail["iterations"] = math.ceil(detail["newton_steps"] / 6)
                    break
                step /= 2
            else:
                if release_length("joint_no_descent"):
                    continue
                detail["stop_reason"] = "joint_no_descent"
                break
            if detail.get("stop_reason") == "fold_boundary":
                break
            emit("joint_update", values=values, residual=residual(values), constraints=len(planes))
    except _Exhausted:
        detail["stop_reason"] = "phase_budget"
        if active_pairs is not None:
            detail["contact_pairs"] += active_pairs
            detail["contact_seconds"] += perf_counter() - contact_started
            detail["interrupted_pairs_charged_as_upper_bound"] = active_pairs
    detail.update(
        cpu_seconds=process_time() - cpu,
        elapsed_seconds=perf_counter() - started,
        length_mm=candidate.material_length_mm if accepted else original.material_length_mm,
        constraints=len(planes),
        length_goal_mm=ceiling,
        length_goal_excess_mm=max(0.0, candidate.material_length_mm - ceiling)
        if accepted
        else None,
    )
    emit(detail["status"], detail=detail, candidate=snapshot(candidate))
    return Result(candidate if accepted else original, measurement if accepted else None, detail)
