"""
Use idle feasibility work on actual late terminal evidence without renewing any solver allowance.
"""

from __future__ import annotations

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

from .feature_recovery import recover as recover_fold
from .gate import Gate
from .joint_contact import recover as recover_joints
from .radius_recovery import RadiusTrigger, continue_after_boundary
from .recovery_limits import Work, validate
from .reversal import _same_folds, close_update
from .reversal_model import NativeReversal, ReversalModel, incident_fold
from .reversal_quality import decline_initial_length
from .sheet import Sheet
from .straight_quality import StraightQuality


class _Exhausted(RuntimeError):
    """
    Stop only this optional phase, preserving caller source/cancellation/resource failures.
    """


def recover(
    original: FoldRoute,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    remaining_pairs: int,
    maximum_cpu_seconds: float,
    maximum_seconds: float,
    maximum_updates: int = 4,
) -> Result | None:
    """
    Use only idle feasibility work to clear an actual first-pass terminal intrusion.

    Caller must reserve unused feasibility work, never a second contraction budget.
    Four total updates include reflection closure and subsequent sheet separation;
    all certificates share remaining construction pairs and at most1024per call.
    Actual late evidence drives the event and plane; no alternative angles/events
    are searched. Radii, other fold signs, profile/order and exact poses stay fixed.
    Feasibility may grow the invalid input up to the original construction length.
    If a straight-witness fixed reversal closes above that ceiling, only its
    unused updates/time/pairs may move the original signed joints instead. Solve
    ordered caps, complete-feature clearance and the original length ceiling
    together; no reflected candidate or extra work is inherited by that action.
    Fold evidence retains the separate overlap-bounded feature-recovery policy.
    Accept only full strict self-contact and both terminal boxes. Failed action
    retains the unresolved source; no certificate or accepted status transfers.
    A caller may supply fewer genuinely unused original updates after completed
    self-contact recovery; CPU, wall and pair sublimits must also be reduced.
    A fixed reflection whose linear angular correction exceeds all remaining
    trust travel may yield to the same existing signed-joint fallback. Its
    completed counters and original clocks still reduce every child allowance.
    A demonstrated sub-native runway may become an exact mathematical zero
    before cap reclosure. Newly measured terminal intrusion then enters coupled
    joint work using only the remaining allocation; no independent sheet
    correction may discard that new clearance constraint.
    If fixed reflected closure is linearly infeasible, the same unused work may
    instead grow the actual witness-incident radius on the original signed route.
    Every other radius and the material floor remain fixed; this continuation
    uses the existing physical-restoration policy and reports source-length excess.
    Initial bounded cap motion with a declined length projection may hand off
    before reflection updates; this local prediction retains the same clocks
    and does not assert global nonlinear infeasibility.
    If the declined reflection's signed-quality fallback also stalls after
    releasing its length ceiling, only unused work may restore the original
    witness-incident radius. Both failed actions remain charged and recorded.
    """
    validate(
        remaining_pairs=remaining_pairs,
        maximum_cpu_seconds=maximum_cpu_seconds,
        maximum_seconds=maximum_seconds,
        maximum_updates=maximum_updates,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
    )
    work = Work(maximum_updates, remaining_pairs, maximum_cpu_seconds, maximum_seconds)
    started, cpu = perf_counter(), process_time()
    evidence = terminal.measure(original, "deferred_recovery_source")
    if evidence.status != "blocked" or evidence.witness is None:
        return None
    if not isinstance(original.pieces[evidence.witness.piece].geometry, Straight):
        cpu_left = maximum_cpu_seconds - (process_time() - cpu)
        wall_left = maximum_seconds - (perf_counter() - started)
        if cpu_left <= 0 or wall_left <= 0:
            return None
        recovered = recover_fold(
            original,
            evidence,
            terminal,
            checkpoint,
            record,
            maximum_length_mm=maximum_length_mm,
            minimum_straight_mm=minimum_straight_mm,
            remaining_pairs=remaining_pairs,
            maximum_cpu_seconds=cpu_left,
            maximum_seconds=wall_left,
            maximum_updates=maximum_updates,
        )
        if recovered is not None:
            recovered.detail.update(
                cpu_seconds=process_time() - cpu, elapsed_seconds=perf_counter() - started
            )
            continued = continue_after_boundary(
                original,
                evidence,
                terminal,
                checkpoint,
                record,
                recovered,
                maximum_length_mm=maximum_length_mm,
                minimum_straight_mm=minimum_straight_mm,
                remaining_pairs=remaining_pairs,
                maximum_cpu_seconds=maximum_cpu_seconds,
                maximum_seconds=maximum_seconds,
                maximum_updates=maximum_updates,
                cpu_started=cpu,
                started=started,
            )
            if continued is not None:
                recovered = continued
        return recovered
    selected = incident_fold(original, evidence.witness)
    if selected is None:
        return None
    model = ReversalModel(original, selected)
    values, sheet = model.initial, None
    candidate, accepted, measurement = original, False, None
    active_pairs: int | None = None
    active_contact_started = 0.0
    detail: dict[str, Any] = {
        "status": "unresolved",
        "purpose": "terminal_clearance",
        "selected_fold": selected,
        "iterations": 0,
        "newton_steps": 0,
        "contacts": 0,
        "contact_pairs": 0,
        "contact_seconds": 0.0,
        "maximum_length_mm": maximum_length_mm,
    }

    def bounded() -> None:
        """
        Charge closure, preparation, certification and terminal checking to this one allowance.
        """
        checkpoint()
        if (
            process_time() - cpu >= maximum_cpu_seconds
            or perf_counter() - started >= maximum_seconds
        ):
            raise _Exhausted("Deferred terminal feasibility allowance exhausted")

    def emit(status: str, **data: Any) -> None:
        """
        Retain every action and its actual geometric evidence without acceptance substitution.
        """
        record({"stage": "deferred_terminal_recovery", "status": status, **data})

    try:
        emit(
            "started",
            source=snapshot(original),
            evidence=asdict(evidence),
            limits={
                "cpu_seconds": maximum_cpu_seconds,
                "wall_seconds": maximum_seconds,
                "pairs": remaining_pairs,
            },
        )
        early_decline = decline_initial_length(model, maximum_length_mm, bounded)
        if early_decline:
            detail["stop_reason"] = "initial_linear_length_declined"
            emit("initial_linear_length_declined", detail=dict(detail))
        for update in range(0 if early_decline else maximum_updates):
            bounded()
            detail["iterations"] += 1
            if sheet is not None:
                gap = sheet.gap(values)
                rows = model.jacobian(values) + [sheet.gradient(values, bounded)]
                right = [-v for v in model.residual(values)] + [1e-7 / model.scale - gap]
                delta = projected(model, values, rows, right, [0.0] * len(values))
                if delta is None:
                    detail["stop_reason"] = "sheet_projection_infeasible"
                    break
                values = advance(model, values, delta, step_limit(model, values, delta, 1.0))
            values, steps, reason = close_update(
                model,
                values,
                bounded,
                remaining_steps=6 * maximum_updates - detail["newton_steps"],
                minimum_straight_mm=minimum_straight_mm,
            )
            detail["newton_steps"] += steps
            proposed = model.route(values)
            assert proposed is not None
            candidate = proposed
            emit(
                "joint_update",
                update=update,
                route=snapshot(candidate),
                residual=model.residual(values),
                sheet_gap_mm=sheet.gap(values) * model.scale if sheet else None,
            )
            if reason is not None:
                detail["stop_reason"] = reason
                break
            if max(map(abs, model.residual(values))) >= 1e-13 or (
                sheet is not None and sheet.gap(values) <= 0
            ):
                continue
            if cap_error(candidate) > 1e-7 or material_error(candidate) > 1e-10:
                raise ArithmeticError("Deferred terminal recovery lost its cap/material contract")
            tiny_slots = frozenset(
                i
                for i in model.straight_indices
                if 0 < values[i] * model.scale <= minimum_straight_mm
            )
            if (
                tiny_slots
                and sheet is None
                and _same_folds(model, candidate)
                and detail["iterations"] < maximum_updates
                and detail["newton_steps"] < 6 * maximum_updates
            ):
                fixed = model.fixed_slots if isinstance(model, NativeReversal) else frozenset()
                fixed = fixed | tiny_slots
                model = NativeReversal(original, selected, fixed)
                values = tuple(0.0 if i in fixed else value for i, value in enumerate(values))
                emit("native_slots_zeroed", indices=sorted(tiny_slots))
                continue
            if not _same_folds(model, candidate) or any(
                isinstance(p.geometry, Straight)
                and p.geometry.material_length_mm <= minimum_straight_mm
                for p in candidate.pieces
            ):
                detail["stop_reason"] = "fold_identity_or_native_sliver"
                break
            if candidate.material_length_mm > maximum_length_mm:
                detail["stop_reason"] = "construction_length_ceiling"
                break
            pairs = min(1024, remaining_pairs - detail["contact_pairs"])
            if pairs <= 0:
                detail["stop_reason"] = "construction_pair_budget"
                break
            contact_started = perf_counter()
            active_pairs, active_contact_started = pairs, contact_started
            detail["contacts"] += 1
            measurement = inspect_contact(
                candidate,
                maximum_pairs=pairs,
                cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                checkpoint=bounded,
            )
            detail["contact_seconds"] += perf_counter() - contact_started
            detail["contact_pairs"] += measurement.pairs_checked
            active_pairs = None
            emit("contact", route=snapshot(candidate), contact=asdict(measurement))
            if measurement.status != "separated":
                detail["stop_reason"] = "self_contact_not_separated"
                break
            report = terminal.measure(candidate, "deferred_recovery_candidate")
            if report.status == "clear":
                bounded()
                accepted = True
                detail["status"] = "separated"
                break
            if isinstance(model, NativeReversal):
                left = work.remaining(
                    updates=detail["iterations"],
                    pairs=detail["contact_pairs"],
                    cpu_seconds=process_time() - cpu,
                    wall_seconds=perf_counter() - started,
                )
                if left is not None:
                    continued = recover_joints(
                        candidate,
                        report,
                        terminal,
                        checkpoint,
                        record,
                        maximum_length_mm=maximum_length_mm,
                        minimum_straight_mm=minimum_straight_mm,
                        remaining_pairs=left.pairs,
                        maximum_cpu_seconds=left.cpu_seconds,
                        maximum_seconds=left.wall_seconds,
                        maximum_updates=left.updates,
                    )
                    if continued is not None:
                        continued.detail["native_zero_before_joint"] = dict(detail)
                        for field in (
                            "iterations",
                            "newton_steps",
                            "contacts",
                            "contact_pairs",
                            "contact_seconds",
                        ):
                            continued.detail[field] += detail[field]
                        continued.detail.update(
                            cpu_seconds=process_time() - cpu,
                            elapsed_seconds=perf_counter() - started,
                        )
                        return continued
                detail["stop_reason"] = "native_zero_joint_unavailable"
                break
            if sheet is not None:
                detail["stop_reason"] = "new_terminal_constraint"
                break
            sheet = Sheet.create(model, candidate, report, terminal.hardware)
            if sheet is None:
                detail["stop_reason"] = "unsupported_terminal_evidence"
                break
            emit(
                "sheet_constraint",
                region=asdict(sheet.region),
                axis=asdict(sheet.axis),
                side=sheet.side.name,
                gap_mm=sheet.gap(values) * model.scale,
            )
    except _Exhausted:
        detail["stop_reason"] = "phase_budget"
        if active_pairs is not None:
            detail["contact_pairs"] += active_pairs
            detail["contact_seconds"] += perf_counter() - active_contact_started
            detail["interrupted_pairs_charged_as_upper_bound"] = active_pairs
    detail.update(
        cpu_seconds=process_time() - cpu,
        elapsed_seconds=perf_counter() - started,
        length_mm=candidate.material_length_mm if accepted else original.material_length_mm,
    )
    if not accepted and detail.get("stop_reason") == "linear_closure_infeasible":
        continued = continue_after_boundary(
            original,
            evidence,
            terminal,
            checkpoint,
            record,
            Result(original, None, detail),
            maximum_length_mm=maximum_length_mm,
            minimum_straight_mm=minimum_straight_mm,
            remaining_pairs=remaining_pairs,
            maximum_cpu_seconds=maximum_cpu_seconds,
            maximum_seconds=maximum_seconds,
            maximum_updates=maximum_updates,
            cpu_started=cpu,
            started=started,
            trigger=RadiusTrigger.REFLECTED_CLOSURE,
        )
        if continued is not None:
            return continued
    if (
        not accepted
        and detail.get("stop_reason")
        in ("construction_length_ceiling", "linear_trust_budget", "initial_linear_length_declined")
        and detail["iterations"] < maximum_updates
    ):
        left = work.remaining(
            updates=detail["iterations"],
            pairs=detail["contact_pairs"],
            cpu_seconds=process_time() - cpu,
            wall_seconds=perf_counter() - started,
        )
        if left is not None:
            emit("fixed_reversal_declined", detail=dict(detail), candidate=snapshot(candidate))
            recovered = recover_fold(
                original,
                evidence,
                terminal,
                checkpoint,
                record,
                maximum_length_mm=maximum_length_mm,
                minimum_straight_mm=minimum_straight_mm,
                remaining_pairs=left.pairs,
                maximum_cpu_seconds=left.cpu_seconds,
                maximum_seconds=left.wall_seconds,
                quality=StraightQuality(maximum_length_mm, left.updates),
                maximum_updates=left.updates,
            )
            if recovered is not None:
                recovered.detail["fixed_reversal_declined"] = dict(detail)
                for field in (
                    "iterations",
                    "newton_steps",
                    "contacts",
                    "contact_pairs",
                    "contact_seconds",
                ):
                    recovered.detail[field] += detail[field]
                recovered.detail.update(
                    cpu_seconds=process_time() - cpu,
                    elapsed_seconds=perf_counter() - started,
                )
                continued = continue_after_boundary(
                    original,
                    evidence,
                    terminal,
                    checkpoint,
                    record,
                    recovered,
                    maximum_length_mm=maximum_length_mm,
                    minimum_straight_mm=minimum_straight_mm,
                    remaining_pairs=remaining_pairs,
                    maximum_cpu_seconds=maximum_cpu_seconds,
                    maximum_seconds=maximum_seconds,
                    maximum_updates=maximum_updates,
                    cpu_started=cpu,
                    started=started,
                    trigger=RadiusTrigger.RELEASED_QUALITY
                    if recovered.detail.get("stop_reason") == "joint_no_descent"
                    else RadiusTrigger.FOLD_DOMAIN,
                )
                return continued if continued is not None else recovered
            detail.update(
                cpu_seconds=process_time() - cpu,
                elapsed_seconds=perf_counter() - started,
                straight_preparation_declined=True,
            )
    emit(detail["status"], detail=detail, candidate=snapshot(candidate))
    return Result(candidate if accepted else original, measurement if accepted else None, detail)
