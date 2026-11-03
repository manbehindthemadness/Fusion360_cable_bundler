"""
Apply bounded total-material descent without displacing an accepted safe baseline on failure.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from time import perf_counter, process_time
from typing import Any, Callable

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_fold_relaxation.steps import advance, projected, step_limit
from experiments.experiment_ribbon_fold_route.contact import ContactResult, inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight

from .model import MovableBends, retract_active


class _PhaseExhausted(RuntimeError):
    """
    Stop only optional contraction work without masking outer hard resource exceptions.
    """


@dataclass(frozen=True)
class Result:
    """
    Return the original route or a shorter certified replacement, with complete phase accounting.
    """

    route: FoldRoute
    contact: ContactResult | None
    detail: dict[str, Any]


def contract(
    original: FoldRoute,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    minimum_straight_mm: float = 1e-5,
    maximum_seconds: float = 2.0,
) -> Result:
    """
    Shorten an already separated baseline with four deterministic movable-bend steps.

    Keep fold count/order/radii/profile and both ordered caps. Try two scalar
    halvings per step, then certify at most the two latest iterates, newest first,
    with1024pairs each. A local0.35CPU-second exhaustion or failed contact keeps
    the original route. The wall allowance may be shortened to the caller's
    remaining first-pass time. Caller cancellation/time/RSS/source errors propagate.
    Guide proximity is diagnostic, not an internal frame lock or acceptance veto.
    """
    if (
        isinstance(minimum_straight_mm, bool)
        or not math.isfinite(minimum_straight_mm)
        or minimum_straight_mm <= 0
    ):
        raise ValueError("A finite positive native straight threshold is required")
    if (
        isinstance(maximum_seconds, bool)
        or not math.isfinite(maximum_seconds)
        or maximum_seconds <= 0
    ):
        raise ValueError("A finite positive contraction wall allowance is required")
    started, cpu = perf_counter(), process_time()
    model = MovableBends(original)
    values, current = model.initial, original
    proposals: list[FoldRoute] = []
    selected, measurement = original, None
    detail: dict[str, Any] = {
        "status": "baseline_retained",
        "raw_length_mm": original.material_length_mm,
        "iterations": 0,
        "contacts": 0,
    }

    def bounded() -> None:
        """
        Check hard caller gates separately from this optional phase's CPU allowance.
        """
        checkpoint()
        if process_time() - cpu >= 0.35 or perf_counter() - started >= maximum_seconds:
            raise _PhaseExhausted("Contraction allowance exhausted")

    def emit(disposition: str, **data: Any) -> None:
        """
        Retain steps and raw contact dispositions in the normal numerical trial ledger.
        """
        record({"stage": "first_pass_contraction", "status": disposition, **data})

    try:
        emit("started", length_mm=original.material_length_mm)
        for iteration in range(4) if model.folds else ():
            bounded()
            detail["iterations"] += 1
            gradient = model.length_gradient(values)
            delta = projected(
                model, values, model.jacobian(values), [0.0] * 6, [-g for g in gradient]
            )
            if delta is None or math.fsum(a * b for a, b in zip(gradient, delta)) >= -1e-10:
                detail["stop_reason"] = "no_projected_descent"
                break
            step = step_limit(model, values, delta, 1.0)
            for halving in range(2):
                bounded()
                corrected = retract_active(model, advance(model, values, delta, step), bounded)
                candidate = model.route(corrected) if corrected is not None else None
                status = "cap_retraction_failed"
                if candidate is not None:
                    if cap_error(candidate) > 1e-7 or material_error(candidate) > 1e-10:
                        raise ArithmeticError("Contraction lost its cap/material contract")
                    folds = tuple(
                        p.geometry
                        for p in candidate.pieces
                        if isinstance(p.geometry, CylindricalFold)
                    )
                    if len(folds) != len(model.folds):
                        status = "fold_count_changed"
                    elif any(
                        isinstance(p.geometry, Straight)
                        and p.geometry.material_length_mm <= minimum_straight_mm
                        for p in candidate.pieces
                    ):
                        status = "native_straight_sliver"
                    elif candidate.material_length_mm >= current.material_length_mm - 1e-7:
                        status = "no_real_shortening"
                    else:
                        status = "shorter_contact_unmeasured"
                        assert corrected is not None
                        current, values = candidate, corrected
                        proposals.append(candidate)
                emit(
                    status,
                    iteration=iteration,
                    halving=halving,
                    step=step,
                    length_mm=candidate.material_length_mm if candidate is not None else None,
                    route=snapshot(candidate) if candidate is not None else None,
                )
                if status == "shorter_contact_unmeasured":
                    break
                step /= 2
            else:
                detail["stop_reason"] = "step_halving_limit"
                break
        for candidate in reversed(proposals[-2:]):
            bounded()
            detail["contacts"] += 1
            emit("contact_started", length_mm=candidate.material_length_mm)
            contact = inspect_contact(candidate, maximum_pairs=1024, checkpoint=bounded)
            emit(contact.status, contact=asdict(contact), route=snapshot(candidate))
            if contact.status == "separated":
                selected, measurement = candidate, contact
                detail["status"] = "shortened"
                break
    except _PhaseExhausted:
        detail["stop_reason"] = "phase_budget"
    detail.update(
        length_mm=selected.material_length_mm,
        cpu_seconds=process_time() - cpu,
        elapsed_seconds=perf_counter() - started,
    )
    emit(detail["status"], **{key: value for key, value in detail.items() if key != "status"})
    return Result(selected, measurement, detail)
