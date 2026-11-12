"""
Spend only residual adaptive work on the existing fixed-topology correction sequence.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from math import ceil
from time import perf_counter, process_time
from typing import Any, Callable, cast

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight

from .check import Report
from .deviation_sequence import recover as recover_sequence
from .gate import Gate
from .recovery_limits import Work, validate


def _radii(route: FoldRoute) -> tuple[float, ...]:
    """
    Retain every ordered bend radius, so no new or removed event can hide in a continuation.
    """
    return tuple(
        p.geometry.radius_mm for p in route.pieces if isinstance(p.geometry, CylindricalFold)
    )


def recover(
    source: FoldRoute,
    evidence: ContactResult | Report,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    work: Work,
    maximum_length_mm: float,
    minimum_straight_mm: float,
) -> Result:
    """
    Enter one existing correction sequence without fitting another local root.

    The caller owns current witness/route identity and the original phase clocks.
    Helper preparation is deducted before the child starts its reduced clocks.
    Source/cancellation checks propagate; the caller merges completed counters
    before testing its original clocks again. Only explicit hardware preparation
    without any motion trial can leave topology work eligible. Final certificates are bound to the returned route,
    not the earlier adaptive piece IDs or undo domains.
    """
    cpu, wall = process_time(), perf_counter()
    validate(
        remaining_pairs=work.pairs,
        maximum_cpu_seconds=work.cpu_seconds,
        maximum_seconds=work.wall_seconds,
        maximum_updates=work.updates,
        maximum_newton_steps=work.newton_steps,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
    )
    if evidence.witness is None or evidence.status != (
        "blocked" if isinstance(evidence, Report) else "penetration"
    ):
        raise ValueError("Continue only an actual current blocker")
    record(
        {
            "stage": "adaptive_continuation",
            "status": "started",
            "route": snapshot(source),
            "evidence": asdict(evidence),
            "remaining_before_preparation": asdict(work),
        }
    )
    checkpoint()
    left = work.remaining(
        updates=0,
        pairs=0,
        newton_steps=0,
        cpu_seconds=process_time() - cpu,
        wall_seconds=perf_counter() - wall,
    )
    if left is None:
        return Result(
            source,
            None,
            {
                "iterations": 0,
                "newton_steps": 0,
                "motion_attempted": False,
                "hardware_preparation_only": False,
                "contacts": 0,
                "contact_pairs": 0,
                "contact_seconds": 0.0,
                "status": "unresolved",
                "stop_reason": "preparation_exhausted",
                "cpu_seconds": process_time() - cpu,
                "elapsed_seconds": perf_counter() - wall,
            },
        )
    result = recover_sequence(
        source,
        evidence,
        terminal,
        checkpoint,
        record,
        work=left,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
    )
    detail = dict(result.detail)
    for key, ceiling in (
        ("iterations", left.updates),
        ("newton_steps", left.newton_steps),
        ("contact_pairs", left.pairs),
    ):
        value = detail.get(key)
        if type(value) is not int or not 0 <= cast(int, value) <= ceiling:
            raise ArithmeticError("Fixed-topology continuation exceeded its original allocation")
    if ceil(detail["newton_steps"] / 6) > detail["iterations"]:
        raise ArithmeticError("Fixed-topology corrections must charge logical updates")
    if type(detail.get("contacts")) is not int or detail["contacts"] < 0:
        raise ArithmeticError("Continuation must retain actual contact counts")
    for key in ("contact_seconds", "cpu_seconds", "elapsed_seconds"):
        value = detail.get(key)
        if (
            type(value) not in (int, float)
            or not math.isfinite(cast(float, value))
            or cast(float, value) < 0
        ):
            raise ArithmeticError("Continuation must retain finite nonnegative timings")
    accepted = result.contact
    if accepted is not None:
        if (
            accepted.status != "separated"
            or accepted.limit is not None
            or detail.get("status") != "separated"
            or type(accepted.pairs_checked) is not int
            or not 0 <= accepted.pairs_checked <= detail["contact_pairs"]
            or detail["contacts"] < 1
            or result.route.targets != source.targets
            or result.route.radius_mm != source.radius_mm
            or _radii(result.route) != _radii(source)
            or not cap_error(result.route) <= 1e-7
            or not material_error(result.route) <= 1e-10
            or any(
                isinstance(p.geometry, Straight)
                and 0 < p.geometry.material_length_mm <= minimum_straight_mm
                for p in result.route.pieces
            )
        ):
            raise ArithmeticError(
                "Continuation lost its fixed material or complete contact contract"
            )
        if terminal.certify(result.route, "adaptive_continuation_final").status != "clear":
            accepted = None
            detail.update(status="unresolved", stop_reason="final_hardware_not_clear")
    checkpoint()
    detail.update(cpu_seconds=process_time() - cpu, elapsed_seconds=perf_counter() - wall)
    if detail["cpu_seconds"] >= work.cpu_seconds or detail["elapsed_seconds"] >= work.wall_seconds:
        accepted = None
        detail.update(
            status="unresolved", stop_reason="phase_budget", hardware_preparation_only=False
        )
    return Result(result.route if accepted is not None else source, accepted, detail)
