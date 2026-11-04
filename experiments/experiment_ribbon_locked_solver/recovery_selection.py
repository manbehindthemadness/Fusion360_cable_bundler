"""
Choose one failed construction by its predicted bounded joint correction, not length alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_feature_insertion.contact_recovery import (
    MAXIMUM_CPU_SECONDS,
    MAXIMUM_WALL_SECONDS,
)
from experiments.experiment_ribbon_feature_insertion.selection import Branch
from experiments.experiment_ribbon_feature_insertion.separation import Separation, TopologyChanged
from experiments.experiment_ribbon_feature_insertion.separation_step import plan_step
from experiments.experiment_ribbon_fold_route.contact import ContactResult


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


def select_recovery(
    candidates: tuple[tuple[Branch, ContactResult], ...],
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> Selection:
    """
    Rank existing failed branches by how much of their correction fits one bounded step.

    Reuse the exact initial separation plan used by recovery, without executing
    candidate updates or contact certificates. Prefer a larger permitted fraction,
    then the existing material/guide/root priority. Prediction is not acceptance.
    Selection and the later single recovery share the original.35CPU/2wall limits.
    Unsupported predictions are logged; caller errors propagate.
    """
    started, cpu = perf_counter(), process_time()
    choices: list[tuple[float, tuple[Any, ...], Branch, ContactResult]] = []
    rows: list[dict[str, Any]] = []
    stopped = None

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
            try:
                bound = Separation.from_measurement(model, branch.route, measurement)
                planned = plan_step(model, model.initial, bound, None, bounded) if bound else None
            except TopologyChanged:
                planned = None
            if planned is not None and planned.fraction > 0:
                row.update(status="predicted", fraction=planned.fraction, side=planned.side.value)
                choices.append((-planned.fraction, branch.priority, branch, measurement))
            rows.append(row)
        bounded()
    except _Exhausted:
        stopped = "selection_budget"
    spent_cpu, spent_wall = process_time() - cpu, perf_counter() - started
    remaining_cpu = max(0.0, MAXIMUM_CPU_SECONDS - spent_cpu)
    remaining_wall = max(0.0, MAXIMUM_WALL_SECONDS - spent_wall)
    choice = None
    if choices and stopped is None and remaining_cpu > 0 and remaining_wall > 0:
        _, _, branch, measurement = min(choices, key=lambda item: (item[0], item[1]))
        choice = branch, measurement
    detail = {
        "status": stopped or ("selected" if choice else "no_supported_separation_step"),
        "predictions": rows,
        "roots": choice[0].roots if choice else None,
        "cpu_seconds": spent_cpu,
        "elapsed_seconds": spent_wall,
    }
    record({"stage": "recovery_selection", **detail})
    return Selection(choice, remaining_cpu, remaining_wall, detail)
