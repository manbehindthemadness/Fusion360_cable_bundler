"""
Derive one terminal-return correction from strict material evidence inside the selected recovery.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_feature_insertion.contact_recovery import Recovery
from experiments.experiment_ribbon_feature_insertion.contact_recovery import (
    recover as recover_contact,
)
from experiments.experiment_ribbon_feature_insertion.depth_evidence import screen
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .gate import Gate
from .incident_recovery import recover_return
from .recovery_limits import Work, validate


class _Exhausted(RuntimeError):
    """
    Retain interrupted preparation counters without masking caller resource errors.
    """


def recover(
    source: FoldRoute,
    measurement: ContactResult,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    remaining_pairs: int,
    maximum_cpu_seconds: float,
    maximum_seconds: float,
) -> Recovery:
    """
    Prefer a demonstrated terminal-straight return to ambiguous depth guidance.

    A supported crossing reverses only its nonadjacent incident fold. All other
    evidence keeps the existing contact correction. An unsuccessful chosen
    strategy never starts a second allocation. Every probe and correction uses
    the caller's original remaining pairs and CPU/wall time.
    """
    validate(
        remaining_pairs=remaining_pairs,
        maximum_cpu_seconds=maximum_cpu_seconds,
        maximum_seconds=maximum_seconds,
        maximum_updates=4,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
    )
    cpu, wall = process_time(), perf_counter()
    work = Work(4, remaining_pairs, maximum_cpu_seconds, maximum_seconds)
    probe = FlatProbe()
    result = Recovery(None, None, 0, 0, 0.0, {"status": "unresolved", "iterations": 0})

    def bounded() -> None:
        """
        Bound all optional preparation without catching source or cancellation failures.
        """
        checkpoint()
        if process_time() - cpu >= maximum_cpu_seconds or perf_counter() - wall >= maximum_seconds:
            raise _Exhausted()

    def remaining() -> Work:
        """
        Share the unspent preparation allowance with exactly one chosen correction.
        """
        left = work.remaining(
            updates=0,
            pairs=probe.comparisons,
            cpu_seconds=process_time() - cpu,
            wall_seconds=perf_counter() - wall,
        )
        if left is None:
            raise _Exhausted()
        return left

    try:
        bounded()
        measured = screen(source, measurement, remaining_pairs, probe, bounded, record)
        bounded()
        if probe.comparisons < remaining_pairs:
            if measured.witness is not None:
                left = remaining()
                incident = recover_return(
                    source,
                    measured.witness,
                    terminal,
                    checkpoint,
                    record,
                    maximum_length_mm=maximum_length_mm,
                    minimum_straight_mm=minimum_straight_mm,
                    remaining_pairs=left.pairs,
                    maximum_cpu_seconds=left.cpu_seconds,
                    maximum_seconds=left.wall_seconds,
                )
                if incident is not None:
                    result = incident
            else:
                incident = None
            if incident is None:
                bounded()
                left = remaining()
                result = recover_contact(
                    source,
                    measured,
                    left.pairs,
                    minimum_straight_mm,
                    checkpoint,
                    record,
                    maximum_cpu_seconds=left.cpu_seconds,
                    maximum_seconds=left.wall_seconds,
                    cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                )
        bounded()
    except _Exhausted:
        result = replace(
            result,
            route=None,
            contact=None,
            detail={**result.detail, "status": "unresolved", "stop_reason": "phase_budget"},
        )
    spent = result.pairs + probe.comparisons
    return replace(
        result,
        pairs=spent,
        detail={
            **result.detail,
            "depth_witness_probe": asdict(probe),
            "cpu_seconds": process_time() - cpu,
            "elapsed_seconds": perf_counter() - wall,
            "pairs": spent,
            "remaining_pair_budget": remaining_pairs - spent,
        },
    )
