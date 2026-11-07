"""
Carry genuinely unused work from a completed self-contact recovery into late terminal clearance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import perf_counter
from typing import Any, cast


@dataclass(frozen=True)
class TerminalAllowance:
    """
    Describe a reduced allocation inside the original four-update/.35CPU/two-wall-second phase.
    """

    updates: int
    cpu_seconds: float
    wall_seconds: float


def remaining_completed(
    detail: dict[str, Any] | None, started: float, first_pass_remaining: float
) -> TerminalAllowance | None:
    """
    Deduct completed recovery updates, all its CPU and the entire intervening wall span.

    Only a completed separated result with one to three recorded updates grants
    unused work. Failed, deferred, malformed or exhausted histories grant none.
    The caller must separately exclude a consulted contraction recovery and share
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
        or not 0 <= cpu < 0.35
        or cast(int, contacts) < 1
        or not 0 <= cast(int, pairs) <= 2048
    ):
        return None
    wall = min(first_pass_remaining, 2.0 - (perf_counter() - started))
    return TerminalAllowance(4 - updates, 0.35 - cpu, wall) if wall > 0 else None
