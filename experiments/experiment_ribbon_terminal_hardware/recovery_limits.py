"""
Validate subdivisions of the single existing terminal/contact feasibility allocation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Work:
    """
    Keep every recovery strategy inside one immutable, nonrenewable allocation.

    A continuation receives only the remainder after all preceding work, including
    preparation and unsuccessful corrections. Exhaustion returns no allocation;
    malformed accounting raises rather than creating an enlarged child budget.
    """

    updates: int
    pairs: int
    cpu_seconds: float
    wall_seconds: float

    def __post_init__(self) -> None:
        """
        Reject disabled, malformed or enlarged allocations before any geometry work.
        """
        if type(self.updates) is not int or not 1 <= self.updates <= 4:
            raise ValueError("Use one to four genuinely remaining updates")
        if type(self.pairs) is not int or not 0 < self.pairs <= 2048:
            raise ValueError("Supply the remaining original pair pool")
        for value, ceiling in ((self.cpu_seconds, 0.35), (self.wall_seconds, 2.0)):
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not 0 < value <= ceiling
            ):
                raise ValueError("Use only remaining original feasibility time")

    def remaining(
        self,
        *,
        updates: int,
        pairs: int,
        cpu_seconds: float,
        wall_seconds: float,
    ) -> Work | None:
        """
        Deduct completed work exactly, returning None when any resource is exhausted.

        Timers are supplied by the caller so the same original clocks include all
        intervening work. Never round counters, clamp negative time or renew work.
        """
        if any(type(value) is not int or value < 0 for value in (updates, pairs)):
            raise ValueError("Completed work requires nonnegative integer counters")
        if any(
            type(value) not in (int, float) or not math.isfinite(value) or value < 0
            for value in (cpu_seconds, wall_seconds)
        ):
            raise ValueError("Completed work requires nonnegative finite times")
        left = (
            self.updates - updates,
            self.pairs - pairs,
            self.cpu_seconds - cpu_seconds,
            self.wall_seconds - wall_seconds,
        )
        if min(left) <= 0:
            return None
        return Work(*left)


def validate(
    *,
    remaining_pairs: int,
    maximum_cpu_seconds: float,
    maximum_seconds: float,
    maximum_updates: int,
    maximum_length_mm: float,
    minimum_straight_mm: float,
) -> None:
    """
    Reject malformed, disabled or enlarged work before witness preparation or joint motion.
    """
    Work(maximum_updates, remaining_pairs, maximum_cpu_seconds, maximum_seconds)
    if any(
        type(value) not in (int, float) or not math.isfinite(value) or value <= 0
        for value in (maximum_length_mm, minimum_straight_mm)
    ):
        raise ValueError("Positive finite parent ceiling and native threshold required")
