"""
Spend the original recovery pool on one witnessed hardware blocker before source contact proof.
"""

from __future__ import annotations

from dataclasses import replace
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_feature_insertion.contact_recovery import (
    MAXIMUM_CPU_SECONDS,
    MAXIMUM_WALL_SECONDS,
)
from experiments.experiment_ribbon_feature_insertion.solve import CONTACT_PAIR_BUDGET, Result
from experiments.experiment_ribbon_terminal_hardware.deviation import recover as recover_terminal
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work


def recover(
    result: Result,
    terminal: Gate,
    threshold_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> tuple[Result, dict[str, Any]]:
    """
    Substitute one existing terminal action for proof of an actually obstructed source.

    Deferred sources have no contact certificate and cannot become accepted
    fallbacks. Use only the first candidate in the constructor's original
    selection order. All preparation and final checks reduce the original
    four-update/.35CPU/2wall/unspent-pair pool. Failure returns immediately,
    without another source or ordinary material-recovery action. A child can
    return accepted geometry only with its real separated contact measurement,
    unchanged ordered targets, exact caps/material and shared hardware clearance.
    """
    if result.route is not None or not result.deferred:
        raise ValueError("Early terminal recovery requires an unaccepted deferred construction")
    cpu, wall = process_time(), perf_counter()
    source = result.deferred[0].route
    pairs = CONTACT_PAIR_BUDGET - result.contact_pairs
    detail: dict[str, Any] = {
        "status": "unresolved",
        "method": "early_terminal_feasibility",
        "source_roots": result.deferred[0].chain.roots,
        "source_contact": "unmeasured",
        "iterations": 0,
        "newton_steps": 0,
        "contacts": 0,
        "contact_pairs": 0,
        "contact_seconds": 0.0,
        "stop_reason": "pair_budget",
    }
    child = None
    checkpoint()
    if pairs > 0:
        work = Work(4, pairs, MAXIMUM_CPU_SECONDS, MAXIMUM_WALL_SECONDS)
        evidence = terminal.measure(source, "deferred_construction_source")
        detail["stop_reason"] = "hardware_evidence_unavailable"
        if evidence.status == "blocked" and evidence.witness is not None:
            left = work.remaining(
                updates=0,
                pairs=0,
                cpu_seconds=process_time() - cpu,
                wall_seconds=perf_counter() - wall,
            )
            detail["stop_reason"] = "phase_budget"
            if left is not None:
                child = recover_terminal(
                    source,
                    terminal,
                    checkpoint,
                    record,
                    maximum_length_mm=source.material_length_mm,
                    minimum_straight_mm=threshold_mm,
                    remaining_pairs=left.pairs,
                    maximum_cpu_seconds=left.cpu_seconds,
                    maximum_seconds=left.wall_seconds,
                    maximum_updates=left.updates,
                )
                if child is None:
                    detail["stop_reason"] = "unsupported_terminal_deviation"
                else:
                    detail.update(child.detail)
    accepted = False
    if child is not None:
        for key in ("iterations", "newton_steps", "contacts", "contact_pairs"):
            if type(detail[key]) is not int or detail[key] < 0:
                raise ArithmeticError(
                    "Deferred terminal recovery requires measured nonnegative work"
                )
        if (
            detail["iterations"] > 4
            or detail["newton_steps"] > 24
            or detail["contact_pairs"] > pairs
        ):
            raise ArithmeticError("Deferred terminal recovery exceeded its original work pool")
        if child.contact is not None and child.contact.status == "separated":
            if (
                child.route.targets != source.targets
                or cap_error(child.route) > 1e-7
                or material_error(child.route) > 1e-10
            ):
                raise ArithmeticError("Deferred terminal recovery lost ordered caps/material")
            accepted = (
                terminal.certify(child.route, "deferred_construction_final").status == "clear"
            )
            detail["stop_reason"] = "accepted" if accepted else "final_hardware_not_clear"
    detail.update(
        method="early_terminal_feasibility",
        source_contact="unmeasured",
        cpu_seconds=process_time() - cpu,
        elapsed_seconds=perf_counter() - wall,
    )
    if (
        detail["cpu_seconds"] >= MAXIMUM_CPU_SECONDS
        or detail["elapsed_seconds"] >= MAXIMUM_WALL_SECONDS
    ):
        accepted = False
        detail["stop_reason"] = "phase_budget"
    detail["status"] = "separated" if accepted else "unresolved"
    detail["pairs"] = detail["contact_pairs"]
    record({"stage": "deferred_construction", "status": detail["status"], "detail": detail})
    return (
        replace(
            result,
            route=child.route if accepted and child is not None else None,
            allocation=None,
            contact=child.contact if accepted and child is not None else None,
            status="separated" if accepted else "deferred_terminal_unresolved",
            contacts=result.contacts + detail["contacts"],
            contact_pairs=result.contact_pairs + detail["contact_pairs"],
            contact_seconds=result.contact_seconds + detail["contact_seconds"],
        ),
        detail,
    )
