"""
Carry genuinely unused work from a completed self-contact recovery into late terminal clearance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import perf_counter
from typing import Any, cast

from experiments.experiment_ribbon_terminal_hardware.recovery_limits import MAXIMUM_CPU_SECONDS


@dataclass(frozen=True)
class TerminalAllowance:
    """
    Describe a reduced allocation inside the shared four-update/.4CPU/two-wall-second phase.
    """

    updates: int
    cpu_seconds: float
    wall_seconds: float
    newton_steps: int = 0
    used_newton_steps: int | None = None


def defer_unentered(
    prior: dict[str, Any] | None, preparation_cpu: float, elapsed_seconds: float
) -> dict[str, Any]:
    """
    Charge selection-only preparation without consuming or renewing geometry work.

    Only no prior recovery or an untouched deferred reservation is eligible.
    The caller must independently establish that no strategy was entered. Keep
    exhausted CPU in the ledger so ordinary allowance checks decline more work;
    elapsed time uses the caller's original phase origin rather than a new clock.
    """
    if (
        type(preparation_cpu) not in (int, float)
        or type(elapsed_seconds) not in (int, float)
        or not math.isfinite(preparation_cpu)
        or preparation_cpu < 0
        or not math.isfinite(elapsed_seconds)
        or elapsed_seconds < 0
    ):
        raise ValueError("Preparation accounting must be finite and nonnegative")
    if prior is not None and (
        prior.get("status") != "deferred"
        or (
            prior.get("newton_steps") is not None
            and (type(prior["newton_steps"]) is not int or prior["newton_steps"] != 0)
        )
        or any(
            type(prior.get(key)) is not int or prior[key] != 0
            for key in ("iterations", "contacts", "pairs")
        )
    ):
        raise ValueError("Only untouched recovery work can be deferred")
    raw_previous_cpu = 0.0 if prior is None else prior.get("cpu_seconds")
    if type(raw_previous_cpu) not in (int, float):
        raise ValueError("Prior preparation CPU must be finite and nonnegative")
    previous_cpu = cast(float, raw_previous_cpu)
    if not math.isfinite(previous_cpu) or previous_cpu < 0:
        raise ValueError("Prior preparation CPU must be finite and nonnegative")
    return {
        **(prior or {}),
        "status": "deferred",
        "iterations": 0,
        "contacts": 0,
        "pairs": 0,
        "newton_steps": 0,
        "cpu_seconds": previous_cpu + preparation_cpu,
        "elapsed_seconds": elapsed_seconds,
        "contraction_selection_only": True,
    }


def remaining_completed(
    detail: dict[str, Any] | None, started: float, first_pass_remaining: float
) -> TerminalAllowance | None:
    """
    Deduct completed recovery updates, all its CPU and the entire intervening wall span.

    Only a completed separated result with one to three recorded updates grants
    unused work. Failed, deferred, malformed or exhausted histories grant none.
    The caller must separately exclude an entered contraction strategy and share
    the original remaining contact-pair pool. This does not restart either phase.
    """
    if detail is None or detail.get("status") != "separated":
        return None
    raw_updates, raw_cpu = detail.get("iterations"), detail.get("cpu_seconds")
    contacts, pairs = detail.get("contacts"), detail.get("pairs")
    if (
        type(raw_updates) is not int
        or type(raw_cpu) not in (int, float)
        or type(contacts) is not int
        or type(pairs) is not int
    ):
        return None
    updates, cpu = cast(int, raw_updates), cast(float, raw_cpu)
    if (
        not 1 <= updates < 4
        or not math.isfinite(cpu)
        or not 0 <= cpu < MAXIMUM_CPU_SECONDS
        or cast(int, contacts) < 1
        or not 0 <= cast(int, pairs) <= 2048
    ):
        return None
    raw_newton = detail.get("newton_steps")
    if raw_newton is not None and (
        type(raw_newton) is not int or not 0 <= cast(int, raw_newton) <= min(24, 6 * updates)
    ):
        return None
    used_newton = cast(int, raw_newton) if raw_newton is not None else None
    if detail.get("newton_steps_scope") not in (None, "whole_recovery"):
        used_newton = None
    left_newton = min(24 - used_newton, 6 * (4 - updates)) if used_newton is not None else 0
    wall = min(first_pass_remaining, 2.0 - (perf_counter() - started))
    return (
        TerminalAllowance(4 - updates, MAXIMUM_CPU_SECONDS - cpu, wall, left_newton, used_newton)
        if wall > 0
        else None
    )
