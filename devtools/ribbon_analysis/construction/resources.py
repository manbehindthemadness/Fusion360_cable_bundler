"""
Sample actual host headroom and process RSS for bounded diagnostic capture and display work.
"""

from __future__ import annotations

import re
import subprocess

from ..budget import NativeBudget, resident_kib


def free_percent() -> int:
    """
    Read macOS's actual free percentage, declining missing or ambiguous measurements.
    """
    output = subprocess.check_output(["/usr/bin/memory_pressure", "-Q"], text=True, timeout=2)
    matches = re.findall(r"^System-wide memory free percentage: (\d+)%$", output, re.MULTILINE)
    if len(matches) != 1 or not 0 <= int(matches[0]) <= 100:
        raise RuntimeError("Actual system memory headroom is unavailable")
    return int(matches[0])


def reserve_memory() -> int:
    """
    Keep at least10%actual system memory free and return measured current process RSS.
    """
    free = free_percent()
    if free < 10:
        raise RuntimeError(f"Construction diagnostic requires10%free; actual {free}%")
    return resident_kib()


def budget(seconds: float) -> NativeBudget:
    """
    Enforce3.8GiB launch,4GiB sampled RSS and a finite caller-owned wall allowance.
    """
    guard = NativeBudget(memory=reserve_memory, maximum_seconds=seconds, maximum_rss_kib=4194304)
    if guard.memory() >= 3984588:
        raise RuntimeError("Construction diagnostic lacks3.8GiB process launch headroom")
    guard.check("construction diagnostic launch")
    return guard
