"""
Transfer unused terminal recovery work after an explicitly identified constrained-model limit.
"""

from __future__ import annotations

from enum import Enum
from time import perf_counter, process_time
from typing import Any, Callable, cast

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .check import Report
from .gate import Gate
from .joint_contact import JointMode, recover
from .recovery_limits import Work


class RadiusTrigger(Enum):
    """
    Identify measured limits of fixed-radius correction before releasing one incident radius.
    """

    FOLD_DOMAIN = "fold_boundary"
    REFLECTED_CLOSURE = "linear_closure_infeasible"
    RELEASED_QUALITY = "joint_no_descent"


def continue_after_boundary(
    original: FoldRoute,
    evidence: Report,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    previous: Result,
    *,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    remaining_pairs: int,
    maximum_cpu_seconds: float,
    maximum_seconds: float,
    maximum_updates: int,
    cpu_started: float,
    started: float,
    trigger: RadiusTrigger = RadiusTrigger.FOLD_DOMAIN,
) -> Result | None:
    """
    Grow one incident radius only after the caller's explicit constrained-model limit.

    Deduct completed updates, all elapsed CPU/wall time and every spent contact
    comparison from the caller's original allocation and clocks. Keep the
    immutable source and actual witness, with no guessed angles or starting
    geometry. Source length is a quality goal only during physical restoration.
    Return None when ineligible or exhausted; otherwise combine all counters and
    retain the preceding failure. Hard caller errors propagate.
    Default callers retain the signed fold-domain trigger. Reflected-closure
    callers must identify their separate linear infeasibility explicitly; the
    unchanged source signs and only its witnessed radius are then free to move.
    A released-quality trigger additionally requires an actual declined fixed
    reflection and a stalled straight-quality correction whose length ceiling
    was already released. A generic no-descent stop grants no radius action.
    """
    if not isinstance(trigger, RadiusTrigger):
        raise ValueError("Supply an explicit radius continuation trigger")
    if (
        previous.contact is not None
        or previous.detail.get("status") != "unresolved"
        or previous.detail.get("stop_reason") != trigger.value
    ):
        return None
    if trigger is RadiusTrigger.RELEASED_QUALITY:
        declined = previous.detail.get("fixed_reversal_declined")
        if (
            previous.detail.get("method") != "constrained_straight_feature"
            or previous.detail.get("length_ceiling_released") is not True
            or not isinstance(declined, dict)
            or declined.get("stop_reason")
            not in (
                "construction_length_ceiling",
                "linear_trust_budget",
                "initial_linear_length_declined",
            )
        ):
            return None
    raw_updates = previous.detail.get("iterations")
    raw_pairs = previous.detail.get("contact_pairs")
    if type(raw_updates) is not int or type(raw_pairs) is not int:
        return None
    used_updates, used_pairs = cast(int, raw_updates), cast(int, raw_pairs)
    if not 0 <= used_updates < maximum_updates or not 0 <= used_pairs < remaining_pairs:
        return None
    checkpoint()
    left = Work(maximum_updates, remaining_pairs, maximum_cpu_seconds, maximum_seconds).remaining(
        updates=used_updates,
        pairs=used_pairs,
        cpu_seconds=process_time() - cpu_started,
        wall_seconds=perf_counter() - started,
    )
    if left is None:
        return None
    record(
        {
            "stage": "radius_boundary_continuation",
            "status": "started",
            "trigger": trigger.value,
            "limits": {
                "updates": left.updates,
                "cpu_seconds": left.cpu_seconds,
                "wall_seconds": left.wall_seconds,
                "pairs": left.pairs,
            },
            "before_radius": dict(previous.detail),
        }
    )
    restored = recover(
        original,
        evidence,
        terminal,
        checkpoint,
        record,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
        remaining_pairs=left.pairs,
        maximum_cpu_seconds=left.cpu_seconds,
        maximum_seconds=left.wall_seconds,
        maximum_updates=left.updates,
        mode=JointMode.RADIUS_RESTORATION,
    )
    if restored is None:
        return None
    detail = dict(restored.detail)
    detail["before_radius"] = dict(previous.detail)
    for field in ("iterations", "newton_steps", "contacts", "contact_pairs", "contact_seconds"):
        detail[field] += previous.detail[field]
    checkpoint()
    elapsed_cpu = process_time() - cpu_started
    elapsed_wall = perf_counter() - started
    detail.update(cpu_seconds=elapsed_cpu, elapsed_seconds=elapsed_wall)
    if elapsed_cpu >= maximum_cpu_seconds or elapsed_wall >= maximum_seconds:
        detail.update(status="unresolved", stop_reason="phase_budget")
        restored = Result(original, None, detail)
    else:
        restored = Result(restored.route, restored.contact, detail)
    record(
        {
            "stage": "radius_boundary_continuation",
            "status": detail["status"],
            "detail": detail,
        }
    )
    return restored
