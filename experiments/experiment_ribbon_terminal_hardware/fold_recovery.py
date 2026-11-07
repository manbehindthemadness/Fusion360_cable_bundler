"""
Close measured fold-feature clearance and endpoint equations in one bounded nonlinear system.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_fold_relaxation.steps import advance, projected, step_limit
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight

from .check import Report
from .feature_plane import FeaturePlane, SignedJoints
from .gate import Gate
from .native_projection import native_slot_step
from .quality_projection import quality_step
from .straight_quality import StraightQuality


class _Exhausted(RuntimeError):
    """
    Stop only the allocated optional recovery work, never caller resource/source failures.
    """


def recover(
    original: FoldRoute,
    evidence: Report,
    terminal: Gate,
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
) -> Result | None:
    """
    Preserve all signs/radii while solving caps and at most two measured feature planes.

    Caller validates and reserves the same idle feasibility allowance. Up to 24
    Newton steps represent four six-correction updates, with 0.2 radian trust and
    four scalar halvings. Every new constraint requires a demonstrated intrusion;
    previous constraints stay active. No angle/event/axis-family candidates are
    searched after selection. Full contact and both boxes remain mandatory.
    Local quality growth is bounded by original construction length plus the
    initial complete-feature projected penetration; it is not a physical tolerance.
    Hardware-clear proposals with sub-native runways fix those slots at zero and
    reclose all equations before final self-contact, without renewing any allowance.
    Straight-quality recovery additionally closes the original length ceiling as
    an active equation and uses only the caller's remaining update count. Ordinary
    fold recovery retains its overlap-based ceiling. Only if its closed proposal
    exceeds that ceiling, use the same coordinates and genuinely remaining work
    to solve clearance/length inequalities alongside the cap equalities. No
    successful legacy proposal enters that additional action.
    A reduced caller allocation retains six corrections per remaining update;
    absent sub-native slots are excluded from each linear correction before
    cap reclosure, rather than creating numerical dust and cleaning it afterward.
    """
    if type(maximum_updates) is not int or not 1 <= maximum_updates <= 4:
        raise ValueError("Use one to four remaining original updates")
    if quality is not None and quality.remaining_updates > maximum_updates:
        raise ValueError("Quality policy cannot renew the remaining update allocation")
    if quality is not None and quality.ceiling_mm != maximum_length_mm:
        raise ValueError("Straight recovery must retain the caller's original quality ceiling")
    started, cpu = perf_counter(), process_time()
    model = SignedJoints(original)
    values = model.initial
    fixed_zero: set[int] = set()
    growth_quality = False
    initial = FeaturePlane.create(model, original, evidence, terminal.hardware, values)
    if initial is None:
        return None
    planes = [initial]
    allowance = max(0.0, -initial.gap(values) * model.scale)
    ceiling = quality.ceiling_mm if quality is not None else maximum_length_mm + allowance
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
        "local_growth_allowance_mm": allowance if quality is None else 0.0,
    }
    active_pairs: int | None = None
    contact_started = 0.0

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

    def equations(coordinates: tuple[float, ...]) -> tuple[float, ...]:
        """
        Retain raw derivatives at cleared inequality boundaries instead of differentiating a clip.
        """
        if growth_quality:
            limits = tuple(1e-7 / model.scale - p.gap(coordinates) for p in planes)
            route_for_limits = model.route(coordinates)
            assert route_for_limits is not None and quality is not None
            limits += ((route_for_limits.material_length_mm - quality.target_mm) / model.scale,)
            return model.residual(coordinates) + limits
        residual_terms = model.residual(coordinates) + tuple(
            p.gap(coordinates) - 1e-7 / model.scale for p in planes
        )
        if quality is not None:
            evaluated_route = model.route(coordinates)
            assert evaluated_route is not None
            residual_terms += (
                (evaluated_route.material_length_mm - quality.target_mm) / model.scale,
            )
        return residual_terms

    def residual(coordinates: tuple[float, ...]) -> tuple[float, ...]:
        """
        Measure cap errors and only violated bounds during growth-constrained closure.
        """
        terms = equations(coordinates)
        return terms[:6] + tuple(max(0.0, term) for term in terms[6:]) if growth_quality else terms

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
                if candidate.material_length_mm > ceiling:
                    remaining_updates = maximum_updates - math.ceil(detail["newton_steps"] / 6)
                    if quality is None and remaining_updates > 0:
                        quality = StraightQuality(ceiling, remaining_updates)
                        growth_quality = True
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
                report = terminal.measure(candidate, "coupled_feature_candidate")
                if report.status == "clear":
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
                if len(planes) >= 2:
                    detail["stop_reason"] = "feature_constraint_limit"
                    break
                extra = FeaturePlane.create(model, candidate, report, terminal.hardware, values)
                if extra is None:
                    detail["stop_reason"] = "unsupported_terminal_evidence"
                    break
                planes.append(extra)
                if growth_quality:
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
            columns = []
            for index, value in enumerate(values):
                bounded()
                if index in fixed_zero:
                    columns.append([0.0] * len(equation))
                    continue
                low, high = model.bounds(index)
                a, b = list(values), list(values)
                a[index], b[index] = max(low, value - 1e-5), min(high, value + 1e-5)
                first, last = equations(tuple(a)), equations(tuple(b))
                columns.append([(y - x) / (b[index] - a[index]) for x, y in zip(first, last)])
            jacobian = [[column[row] for column in columns] for row in range(len(equation))]
            delta = (
                quality_step(model, values, jacobian, equations(values), bounded)
                if growth_quality
                else projected(model, values, jacobian, [-v for v in equation], [0.0] * len(values))
            )
            if delta is None:
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
                if max(map(abs, residual(trial))) < error:
                    values = trial
                    detail["newton_steps"] += 1
                    detail["iterations"] = math.ceil(detail["newton_steps"] / 6)
                    break
                step /= 2
            else:
                detail["stop_reason"] = "joint_no_descent"
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
    )
    emit(detail["status"], detail=detail, candidate=snapshot(candidate))
    return Result(candidate if accepted else original, measurement if accepted else None, detail)
