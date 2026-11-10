"""
Route measured self-contact returns into one existing incident reversal before local separation.
"""

from __future__ import annotations

from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_feature_insertion.contact_recovery import Recovery
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_terminal_hardware.deviation_sequence import (
    recover as recover_sequence,
)
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.material_return import select_fold
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work


def before_contact_motion(
    source: FoldRoute,
    measurement: ContactResult,
    terminal: Gate | None,
    threshold_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> Callable[[Work], Recovery | None] | None:
    """
    Replace the first local correction for a witnessed return anywhere in the material chain.

    Select the largest accumulated fold turn inside the actual contact bracket,
    without requiring adjacent folds or terminal membership. No alternative is tried.
    Unsupported evidence keeps ordinary separation. Once a supported reflection
    is attempted, failure consumes that action; no fresh separation attempt follows.
    Both caps, radii, other signs and material order stay fixed. The same shared
    sequence used after spatial deviation follows actual hardware/material
    blockers without renewing work. Invalid-source length is a reported goal;
    full thick self-contact and both hardware certificates remain mandatory.
    All preparation and child work debit the caller's remaining original allowance.
    """
    if terminal is None or measurement.status != "penetration" or measurement.witness is None:
        return None

    def prepare(work: Work) -> Recovery | None:
        """
        Pass only genuinely remaining updates, pairs and time to the one evidence-derived action.
        """
        cpu, wall = process_time(), perf_counter()
        checkpoint()
        assert terminal is not None and measurement.witness is not None
        if select_fold(source, measurement.witness) is None:
            return None
        left = work.remaining(
            updates=0,
            pairs=0,
            cpu_seconds=process_time() - cpu,
            wall_seconds=perf_counter() - wall,
        )
        if left is None:
            return Recovery(
                None,
                None,
                0,
                0,
                0.0,
                {"status": "unresolved", "iterations": 0, "stop_reason": "local_budget"},
            )
        result = recover_sequence(
            source,
            measurement,
            terminal,
            checkpoint,
            record,
            maximum_length_mm=source.material_length_mm,
            minimum_straight_mm=threshold_mm,
            work=left,
        )
        detail: dict[str, Any] = {
            **result.detail,
            "purpose": "construction_loop_reversal",
            "cpu_seconds": process_time() - cpu,
            "elapsed_seconds": perf_counter() - wall,
        }
        route = result.route if result.contact is not None else None
        contact = result.contact
        record(
            {
                "stage": "construction_loop_reversal",
                "source": snapshot(source),
                "detail": detail,
            }
        )
        detail.update(cpu_seconds=process_time() - cpu, elapsed_seconds=perf_counter() - wall)
        if (
            detail["cpu_seconds"] >= work.cpu_seconds
            or detail["elapsed_seconds"] >= work.wall_seconds
        ):
            detail.update(status="unresolved", stop_reason="local_budget")
            route, contact = None, None
            record(
                {"stage": "construction_loop_reversal", "status": "unresolved", "detail": detail}
            )
        return Recovery(
            route,
            contact,
            detail["contact_pairs"],
            detail["contacts"],
            detail["contact_seconds"],
            detail,
        )

    return prepare
