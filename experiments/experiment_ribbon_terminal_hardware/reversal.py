"""
Spend the existing contraction allowance on one measured, shorter terminal-fold correction.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from time import perf_counter, process_time
from typing import Any, Callable

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_fold_relaxation.steps import advance, projected, step_limit
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight

from .gate import Gate
from .reversal_model import ReversalModel, incident_fold


class _Exhausted(RuntimeError):
    """
    Stop optional correction without masking a caller's cancellation or hard resource error.
    """


def correct(
    original: FoldRoute,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    minimum_straight_mm: float,
    maximum_seconds: float,
) -> Result | None:
    """
    Substitute for contraction only on demonstrated hardware intrusion with a supported fold.

    Reflect one witness-incident fold, hold its bank and every radius fixed, then
    close all other joints together. Use four updates of at most six Newton/four
    halving corrections, with the existing0.2radian free-angle trust bound and
    0.35CPU/2wall-second contraction allowance. No alternate fold index, radius,
    feature, sign branch or target is tried. Zero runway slots are free to grow.
    Accept only strict shortening, unchanged fold order/radii, accurate caps and
    material, a full1024pair self-contact certificate and both finite proxy checks.
    Every unsuccessful action retains the original route for ordinary smoothing.
    None means no demonstrated supported action, so ordinary contraction may run.
    Caller checkpoint failures propagate; optional phase exhaustion stays recorded.
    """
    if (
        type(minimum_straight_mm) not in (int, float)
        or not math.isfinite(minimum_straight_mm)
        or minimum_straight_mm <= 0
        or type(maximum_seconds) not in (int, float)
        or not math.isfinite(maximum_seconds)
        or not 0 < maximum_seconds <= 2
    ):
        raise ValueError("Use a positive native threshold and at most two wall seconds")
    started, cpu = perf_counter(), process_time()
    evidence = terminal.probe(original, "before_contraction")
    if evidence.status != "blocked" or evidence.witness is None:
        return None
    selected = incident_fold(original, evidence.witness)
    if selected is None:
        return None
    model = ReversalModel(original, selected)
    values = model.initial
    detail: dict[str, Any] = {
        "status": "baseline_retained",
        "method": "witness_incident_fold_reversal",
        "selected_fold": selected,
        "terminal": evidence.witness.terminal,
        "raw_length_mm": original.material_length_mm,
        "iterations": 0,
        "newton_steps": 0,
        "contacts": 0,
        "contact_pairs": 0,
    }
    candidate = None
    measurement = None

    def bounded() -> None:
        """
        Charge all correction work to its substituted contraction phase.
        """
        checkpoint()
        if process_time() - cpu >= 0.35 or perf_counter() - started >= maximum_seconds:
            raise _Exhausted("Terminal reversal contraction allowance exhausted")

    def emit(status: str, **data: Any) -> None:
        """
        Preserve the selected action and every nonlinear update in the numerical ledger.
        """
        record({"stage": "terminal_fold_reversal", "status": status, **data})

    try:
        emit(
            "started", selected_fold=selected, source=snapshot(original), evidence=asdict(evidence)
        )
        for update in range(4):
            detail["iterations"] += 1
            values, steps, reason = close_update(model, values, bounded)
            detail["newton_steps"] += steps
            if reason is not None:
                detail["stop_reason"] = reason
            emit("closure_update", update=update, values=values, residual=model.residual(values))
            if max(map(abs, model.residual(values))) < 1e-13 or "stop_reason" in detail:
                break
        candidate = model.route(values)
        assert candidate is not None
        if max(map(abs, model.residual(values))) >= 1e-13:
            detail.setdefault("stop_reason", "closure_update_limit")
        elif cap_error(candidate) > 1e-7 or material_error(candidate) > 1e-10:
            raise ArithmeticError("Terminal reversal lost its fixed-cap/material contract")
        elif not _same_folds(model, candidate):
            detail["stop_reason"] = "fold_identity_changed"
        elif any(
            isinstance(p.geometry, Straight)
            and p.geometry.material_length_mm <= minimum_straight_mm
            for p in candidate.pieces
        ):
            detail["stop_reason"] = "native_straight_sliver"
        elif candidate.material_length_mm >= original.material_length_mm - 1e-7:
            detail["stop_reason"] = "no_real_shortening"
        else:
            bounded()
            detail["contacts"] += 1
            measurement = inspect_contact(
                candidate,
                maximum_pairs=1024,
                cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                checkpoint=bounded,
            )
            detail["contact_pairs"] = measurement.pairs_checked
            emit("contact", route=snapshot(candidate), contact=asdict(measurement))
            if measurement.status != "separated":
                detail["stop_reason"] = "self_contact_not_separated"
            elif not terminal.permits(candidate, "coupled_reversal"):
                detail["stop_reason"] = "terminal_clearance_not_established"
            else:
                bounded()
                detail["status"] = "shortened"
    except _Exhausted:
        detail["stop_reason"] = "phase_budget"
    accepted = detail["status"] == "shortened"
    result = candidate if accepted else original
    assert result is not None
    detail.update(
        length_mm=result.material_length_mm,
        cpu_seconds=process_time() - cpu,
        elapsed_seconds=perf_counter() - started,
    )
    emit(detail["status"], detail=detail, candidate=snapshot(candidate) if candidate else None)
    return Result(result, measurement if accepted else None, detail)


def close_update(
    model: MovableBends, initial: tuple[float, ...], checkpoint: Callable[[], None]
) -> tuple[tuple[float, ...], int, str | None]:
    """
    Perform one shared six-Newton/four-halving ordered-cap correction without fixing zero runways.

    Return the last bounded coordinates, motion count and any nonconvergence cause.
    A missing cause does not itself certify closure; callers test the residual.
    """
    values, steps = initial, 0
    for _ in range(6):
        checkpoint()
        residual = model.residual(values)
        error = max(map(abs, residual))
        if error < 1e-13:
            return values, steps, None
        delta = projected(
            model, values, model.jacobian(values), [-v for v in residual], [0.0] * len(values)
        )
        if delta is None:
            return values, steps, "linear_closure_infeasible"
        step = step_limit(model, values, delta, 1.0)
        for _ in range(4):
            checkpoint()
            trial = advance(model, values, delta, step)
            if max(map(abs, model.residual(trial))) < error:
                values = trial
                steps += 1
                break
            step /= 2
        else:
            return values, steps, "closure_no_descent"
    return values, steps, None


def _same_folds(model: ReversalModel, route: FoldRoute) -> bool:
    """
    Require the same ordered radii and exactly the selected fold's changed sign.
    """
    folds = tuple(p.geometry for p in route.pieces if isinstance(p.geometry, CylindricalFold))
    return len(folds) == len(model.folds) and all(
        actual.radius_mm == source.radius_mm
        and actual.width_mm == source.width_mm
        and math.copysign(1, actual.angle_radians)
        == math.copysign(1, source.angle_radians) * (-1 if i == model.selected else 1)
        for i, (source, actual) in enumerate(zip(model.folds, folds))
    )
