"""
Reserve the selected shorter branch's existing work for physical feasibility when its fallback hits hardware.
"""

from __future__ import annotations

from dataclasses import replace
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_feature_insertion.contact_recovery import Recovery
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_terminal_hardware.flat_separation import paired_return_fold
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.incident_recovery import recover_paired_return
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work

from .mating_feasibility import recover as recover_mating
from .mating_feasibility import supported as mating_supported


def before_optional_motion(
    baseline: FoldRoute,
    source: FoldRoute,
    measurement: ContactResult,
    terminal: Gate | None,
    threshold_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> Callable[[Work], Recovery | None] | None:
    """
    Bind one actual selected branch; no action or eligibility measurement occurs before its first motion.

    A measured paired-fold return or supported mating-runway crossing can select
    a different first motion. Other contact topologies retain their original
    action without measuring baseline hardware. A blocked baseline prioritizes
    its selected physical correction
    using the remaining original work. Cleared or unresolved eligibility also
    preserves the original contact action.
    """
    if terminal is None:
        return None

    def prepare(work: Work) -> Recovery | None:
        """
        Charge eligibility, preparation and every child correction to this one original allocation.
        """
        cpu, wall = process_time(), perf_counter()
        if measurement.status != "penetration" or measurement.witness is None:
            return None
        paired = paired_return_fold(source, measurement.witness)
        if paired is None and not mating_supported(source, measurement, checkpoint, record):
            return None
        report = terminal.measure(baseline, "fallback_feasibility")
        if report.status != "blocked":
            return None
        left = work.remaining(
            updates=0,
            pairs=0,
            cpu_seconds=process_time() - cpu,
            wall_seconds=perf_counter() - wall,
        )
        child = None
        if (
            left is not None
            and measurement.status == "penetration"
            and measurement.witness is not None
        ):
            if paired is None:
                child = recover_mating(
                    baseline, source, measurement, terminal, threshold_mm, left, checkpoint, record
                )
                if child is None:
                    return None
                detail = dict(child.detail)
                detail.update(
                    method="fallback_mating_feasibility",
                    pairs=child.pairs,
                    cpu_seconds=process_time() - cpu,
                    elapsed_seconds=perf_counter() - wall,
                )
                return replace(child, detail=detail)
            child = recover_paired_return(
                source,
                measurement.witness,
                terminal,
                checkpoint,
                record,
                maximum_length_mm=baseline.material_length_mm,
                minimum_straight_mm=threshold_mm,
                remaining_pairs=left.pairs,
                maximum_cpu_seconds=left.cpu_seconds,
                maximum_seconds=left.wall_seconds,
                maximum_updates=left.updates,
            )
        if child is None:
            return Recovery(
                None,
                None,
                0,
                0,
                0.0,
                {
                    "status": "deferred" if left is not None else "unresolved",
                    "iterations": 0,
                    "contacts": 0,
                    "pairs": 0,
                    "cpu_seconds": process_time() - cpu,
                    "elapsed_seconds": perf_counter() - wall,
                    "stop_reason": "terminal_feasibility_priority"
                    if left is not None
                    else "priority_budget",
                },
            )
        detail = dict(child.detail)
        detail.update(
            method="fallback_coupled_feasibility",
            pairs=child.pairs,
            cpu_seconds=process_time() - cpu,
            elapsed_seconds=perf_counter() - wall,
        )
        return Recovery(
            child.route, child.contact, child.pairs, child.contacts, child.contact_seconds, detail
        )

    return prepare
