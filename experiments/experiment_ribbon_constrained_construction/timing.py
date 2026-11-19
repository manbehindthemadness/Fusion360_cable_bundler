"""
Record diagnostic CPU misses while enforcing a separate finite wall deadline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import perf_counter, process_time
from typing import Callable


@dataclass(frozen=True)
class Timing:
    """
    Separate measured performance from permission to finish diagnostic construction.
    """

    cpu_seconds: float
    wall_seconds: float
    cpu_target_seconds: float

    @property
    def cpu_overrun_seconds(self) -> float:
        """
        Return excess CPU without changing geometric acceptance.
        """
        return max(0.0, self.cpu_seconds - self.cpu_target_seconds)


class DiagnosticClock:
    """
    Enforce finite wall time and external guards, treating CPU solely as measured performance.
    """

    def __init__(
        self,
        checkpoint: Callable[[], None],
        *,
        maximum_wall_seconds: float,
        cpu_target_seconds: float = 0.4,
        wall_clock: Callable[[], float] = perf_counter,
        cpu_clock: Callable[[], float] = process_time,
    ) -> None:
        """
        Start one nonrenewable diagnostic clock; inject clocks only for deterministic verification.
        """
        if any(
            type(v) not in (int, float) or not math.isfinite(v) or v <= 0
            for v in (maximum_wall_seconds, cpu_target_seconds)
        ):
            raise ValueError("Diagnostic time bounds must be finite and positive")
        self._checkpoint = checkpoint
        self._wall_clock = wall_clock
        self._cpu_clock = cpu_clock
        self._wall_started = wall_clock()
        self._cpu_started = cpu_clock()
        self._maximum_wall = maximum_wall_seconds
        self._cpu_target = cpu_target_seconds

    def timing(self) -> Timing:
        """
        Report both original clocks without renewing either allocation.
        """
        return Timing(
            self._cpu_clock() - self._cpu_started,
            self._wall_clock() - self._wall_started,
            self._cpu_target,
        )

    def check(self) -> None:
        """
        Propagate host/source/cancellation failures and stop only on the wall deadline here.
        """
        self._checkpoint()
        if self._wall_clock() - self._wall_started >= self._maximum_wall:
            raise TimeoutError("Diagnostic construction wall deadline exhausted")
