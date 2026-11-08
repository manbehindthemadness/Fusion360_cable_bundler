"""
Close a reflected return's actual flat crossing and caps using only unused original work.
"""

from __future__ import annotations

from dataclasses import asdict
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_feature_insertion.contact_recovery import Recovery
from experiments.experiment_ribbon_feature_insertion.depth_evidence import screen
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .gate import Gate
from .joint_contact import recover as recover_joint
from .recovery_limits import validate


class _Exhausted(RuntimeError):
    """
    Stop local preparation without consuming a fresh correction allocation.
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
    maximum_updates: int,
) -> Recovery:
    """
    Simultaneously close caps, complete witnessed flat profiles and measured connector planes.

    A negative-only screen may replace ambiguous depth guidance. Preparation,
    every comparison and the joint solver share the supplied unused allowance.
    Unsupported or missed evidence returns no accepted route. Final full thick
    contact and both hardware boxes remain mandatory in the joint solver.
    """
    validate(
        remaining_pairs=remaining_pairs,
        maximum_cpu_seconds=maximum_cpu_seconds,
        maximum_seconds=maximum_seconds,
        maximum_updates=maximum_updates,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
    )
    cpu, wall = process_time(), perf_counter()
    probe = FlatProbe()
    selected = accepted = None
    contacts, spent, contact_seconds = 0, 0, 0.0
    detail: dict[str, Any] = {"status": "unresolved", "iterations": 0, "newton_steps": 0}

    def bounded() -> None:
        """
        Charge witness preparation to this same remaining CPU/wall allocation.
        """
        checkpoint()
        if process_time() - cpu >= maximum_cpu_seconds or perf_counter() - wall >= maximum_seconds:
            raise _Exhausted()

    try:
        bounded()
        measured = screen(source, measurement, remaining_pairs, probe, bounded, record)
        bounded()
        if measured.witness is not None and probe.comparisons < remaining_pairs:
            result = recover_joint(
                source,
                measured.witness,
                terminal,
                checkpoint,
                record,
                maximum_length_mm=maximum_length_mm - 1e-7,
                minimum_straight_mm=minimum_straight_mm,
                remaining_pairs=remaining_pairs - probe.comparisons,
                maximum_cpu_seconds=maximum_cpu_seconds - (process_time() - cpu),
                maximum_seconds=maximum_seconds - (perf_counter() - wall),
                maximum_updates=maximum_updates,
            )
            if result is not None:
                detail.update(result.detail)
                spent = result.detail["contact_pairs"]
                contacts = result.detail["contacts"]
                contact_seconds = result.detail["contact_seconds"]
                if result.contact is not None and result.contact.status == "separated":
                    selected, accepted = result.route, result.contact
        bounded()
    except _Exhausted:
        selected = accepted = None
        detail.update(status="unresolved", stop_reason="phase_budget")
    spent += probe.comparisons
    detail.update(
        depth_witness_probe=asdict(probe),
        cpu_seconds=process_time() - cpu,
        elapsed_seconds=perf_counter() - wall,
        pairs=spent,
        remaining_pair_budget=remaining_pairs - spent,
    )
    return Recovery(selected, accepted, spent, contacts, contact_seconds, detail)
