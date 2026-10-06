"""
Enforce scheduling limits between native operations without cancelling a kernel.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any


def resident_kib() -> int:
    """
    Read this Fusion process's RSS; fail closed if it cannot be measured.

    RSS excludes compressed and other physical-footprint accounting. It is
    the explicitly agreed observable ceiling, not total host-memory usage.
    """
    result = subprocess.run(
        ["/bin/ps", "-o", "rss=", "-p", str(os.getpid())],
        check=True,
        capture_output=True,
        text=True,
    )
    value = int(result.stdout.strip())
    if value <= 0:
        raise RuntimeError("Fusion RSS measurement is unavailable.")
    return value


@dataclass
class NativeBudget:
    """
    Stop scheduling at 120 seconds or 2 GiB RSS and preserve nested stage timings.
    """

    clock: Callable[[], float] = perf_counter
    memory: Callable[[], int] = resident_kib
    maximum_seconds: float = 120.0
    maximum_rss_kib: int = 2 * 1024 * 1024
    timings: dict[str, float] = field(default_factory=dict)
    samples: list[dict[str, object]] = field(default_factory=list)
    stopped: str | None = None
    started: float = field(init=False)

    def __post_init__(self) -> None:
        """
        Start the overall timer before document retention and construction work.
        """
        self.started = self.clock()

    def check(self, stage: str) -> None:
        """
        Measure before a launch, latching a stop so no further kernels are started.
        """
        if self.stopped is not None:
            raise RuntimeError(self.stopped)
        rss = self.memory()
        elapsed = self.clock() - self.started
        self.samples.append({"stage": stage, "elapsed_seconds": elapsed, "rss_kib": rss})
        if elapsed >= self.maximum_seconds or rss >= self.maximum_rss_kib:
            self.stopped = (
                f"Scheduling limit reached before {stage}: {elapsed:.3f}s, {rss} KiB RSS."
            )
            raise RuntimeError(self.stopped)

    def measure(
        self, stage: str, operation: Callable[..., Any], *, native: bool = False
    ) -> Callable[..., Any]:
        """
        Wrap one private binding, accumulating failed as well as successful time.
        """

        def measured(*args: Any, **kwargs: Any) -> Any:
            """
            Forward arguments unchanged, checking only before native operations.
            """
            if native:
                self.check(stage)
            started = self.clock()
            try:
                return operation(*args, **kwargs)
            finally:
                self.timings[stage] = self.timings.get(stage, 0.0) + self.clock() - started

        return measured
