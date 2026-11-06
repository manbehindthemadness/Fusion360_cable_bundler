"""
Choose one failed construction by its predicted bounded joint correction, not length alone.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_feature_insertion.contact_recovery import (
    MAXIMUM_CPU_SECONDS,
    MAXIMUM_WALL_SECONDS,
)
from experiments.experiment_ribbon_feature_insertion.selection import Branch
from experiments.experiment_ribbon_feature_insertion.separation import Separation, TopologyChanged
from experiments.experiment_ribbon_feature_insertion.separation_step import InitialStep, plan_step
from experiments.experiment_ribbon_fold_route.contact import ContactResult

from .recovery_evidence import adjacent_straight_contact
from .recovery_prediction import PredictionPolicy, first_gap, verified_sheets


class _Exhausted(RuntimeError):
    """
    Stop optional selection without masking caller cancellation or hard resource failures.
    """


@dataclass(frozen=True)
class Selection:
    """
    Retain one existing branch and the original recovery work left after prediction.
    """

    choice: tuple[Branch, ContactResult] | None
    maximum_cpu_seconds: float
    maximum_seconds: float
    detail: dict[str, Any]
    alternatives: tuple[tuple[Branch, ContactResult], ...] = ()
    initial_steps: tuple[InitialStep, ...] = ()


def select_recovery(
    candidates: tuple[tuple[Branch, ContactResult], ...],
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    prediction_policy: PredictionPolicy = PredictionPolicy.LINEAR,
) -> Selection:
    """
    Rank failed branches by the initial number of bounded trust steps they require.

    Reuse the exact initial separation plan used by recovery, without executing
    candidate updates or contact certificates. Prefer fewer required trust steps,
    then material/guide/root priority. Fractions needing the same whole number of
    steps do not favor a long excursion for a small clipping difference. Values
    needing more than four steps retain their original fraction order. These are
    initial linear predictions, not an acceptance or nonlinear convergence promise.
    Selection and the later single recovery share the original.35CPU/2wall limits.
    Unsupported predictions are logged; caller errors propagate.
    """
    started, cpu = perf_counter(), process_time()
    if not isinstance(prediction_policy, PredictionPolicy):
        raise ValueError("Supply an explicit recovery prediction policy")
    choices: list[tuple[int, float, tuple[Any, ...], Branch, ContactResult]] = []
    rows: list[dict[str, Any]] = []
    initial_steps: list[InitialStep] = []
    stopped = None
    verified: tuple[Branch, ContactResult] | None = None

    def bounded() -> None:
        """
        Charge prediction work to the existing recovery allowance.
        """
        checkpoint()
        if (
            process_time() - cpu >= MAXIMUM_CPU_SECONDS
            or perf_counter() - started >= MAXIMUM_WALL_SECONDS
        ):
            raise _Exhausted("Recovery selection allowance exhausted")

    try:
        for branch, measurement in candidates:
            bounded()
            model = MovableBends(branch.route)
            row: dict[str, Any] = {"roots": branch.roots, "status": "unsupported"}
            plane = None
            try:
                bound = Separation.from_measurement(model, branch.route, measurement)
                if bound is not None:
                    measurement, plane = adjacent_straight_contact(
                        branch.route, measurement, bounded, record
                    )
                    if plane is not None:
                        bound = Separation.from_measurement(model, branch.route, measurement)
                        assert bound is not None
                        bound = replace(bound, plane=plane)
                planned = plan_step(model, model.initial, bound, None, bounded) if bound else None
            except TopologyChanged:
                planned = None
            if planned is not None and planned.fraction > 0:
                steps = math.ceil(1 / planned.fraction) if planned.fraction >= 0.25 else 5
                overflow_priority = -planned.fraction if steps > 4 else 0.0
                row.update(
                    status="predicted",
                    fraction=planned.fraction,
                    side=planned.side.value,
                    initial_trust_steps=steps,
                )
                choices.append((steps, overflow_priority, branch.priority, branch, measurement))
                initial_steps.append(InitialStep(branch.route, measurement, planned, plane))
            rows.append(row)
        if choices and prediction_policy is PredictionPolicy.VERIFIED_SHEETS:
            original = min(choices, key=lambda item: item[:3])
            cached = next(item for item in initial_steps if item.source is original[3].route)
            if cached.step.fraction == 1.0:
                actual_gap = first_gap(cached, bounded)
                record(
                    {
                        "stage": "recovery_prediction_check",
                        "roots": original[3].roots,
                        "actual_gap_mm": actual_gap,
                        "status": "verified"
                        if actual_gap is not None and actual_gap > 0
                        else "inconsistent",
                    }
                )
                if actual_gap is None or actual_gap <= 0:
                    prepared = verified_sheets(candidates, bounded, record)
                    if prepared is not None:
                        branch, measurement, initial, gap = prepared
                        choices = [item for item in choices if item[3].roots != branch.roots]
                        choices.append((1, 0.0, branch.priority, branch, measurement))
                        verified = branch, measurement
                        initial_steps.append(initial)
                        record(
                            {
                                "stage": "recovery_prediction_replaced",
                                "roots": branch.roots,
                                "original_roots": original[3].roots,
                                "actual_gap_mm": gap,
                                "status": "verified_first_gap",
                            }
                        )
        bounded()
    except _Exhausted:
        stopped = "selection_budget"
    spent_cpu, spent_wall = process_time() - cpu, perf_counter() - started
    remaining_cpu = max(0.0, MAXIMUM_CPU_SECONDS - spent_cpu)
    remaining_wall = max(0.0, MAXIMUM_WALL_SECONDS - spent_wall)
    choice = None
    alternatives: tuple[tuple[Branch, ContactResult], ...] = ()
    if choices and stopped is None and remaining_cpu > 0 and remaining_wall > 0:
        ordered = sorted(choices, key=lambda item: item[:3])
        if verified is not None:
            ordered = [
                item for item in ordered if item[3] is verified[0] and item[4] is verified[1]
            ] + [
                item for item in ordered if item[3] is not verified[0] or item[4] is not verified[1]
            ]
        _, _, _, branch, measurement = ordered[0]
        choice = branch, measurement
        alternatives = tuple((branch, measurement) for _, _, _, branch, measurement in ordered[1:])
    detail = {
        "status": stopped or ("selected" if choice else "no_supported_separation_step"),
        "predictions": rows,
        "roots": choice[0].roots if choice else None,
        "cpu_seconds": spent_cpu,
        "elapsed_seconds": spent_wall,
    }
    record({"stage": "recovery_selection", **detail})
    return Selection(
        choice, remaining_cpu, remaining_wall, detail, alternatives, tuple(initial_steps)
    )
