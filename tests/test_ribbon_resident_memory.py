"""
Preserve current RSS semantics and fail-closed scheduling without subprocess overhead on macOS.
"""

from __future__ import annotations

import ctypes
import os
from types import SimpleNamespace
from typing import Any

import pytest

import devtools.ribbon_analysis.budget as budget
from devtools.ribbon_analysis import resident_memory


@pytest.mark.parametrize("resident,expected", ((1024, 1), (4097, 5)))
def test_current_process_is_queried_again_for_every_sample(
    monkeypatch: pytest.MonkeyPatch, resident: int, expected: int
) -> None:
    """
    Read fresh resident bytes, use the complete ABI and conservatively round to KiB.
    """
    calls: list[int] = []

    def query(pid: int, flavor: int, argument: int, output: Any, size: int) -> int:
        """
        Supply distinct live values through the same pointer contract as libproc.
        """
        assert pid == os.getpid() and flavor == 4 and argument == 0 and size == 96
        info = ctypes.cast(output, ctypes.POINTER(resident_memory._TaskInfo)).contents
        info.resident_size = resident + len(calls) * 1024
        calls.append(pid)
        return size

    monkeypatch.setattr(resident_memory, "_task_query", lambda: query)
    assert resident_memory.darwin_resident_kib() == expected
    assert resident_memory.darwin_resident_kib() == expected + 1
    assert len(calls) == 2


@pytest.mark.parametrize("received,resident", ((0, 4096), (95, 4096), (97, 4096), (96, 0)))
def test_incomplete_or_unusable_measurements_fail_closed(
    monkeypatch: pytest.MonkeyPatch, received: int, resident: int
) -> None:
    """
    Never turn a short, oversized or zero-memory query into permission for more native work.
    """

    def query(pid: int, flavor: int, argument: int, output: Any, size: int) -> int:
        """
        Return an invalid kernel measurement for the caller's complete-size guard.
        """
        assert pid == os.getpid() and flavor == 4 and argument == 0 and size == 96
        info = ctypes.cast(output, ctypes.POINTER(resident_memory._TaskInfo)).contents
        info.resident_size = resident
        return received

    monkeypatch.setattr(resident_memory, "_task_query", lambda: query)
    with pytest.raises(RuntimeError, match="RSS measurement is unavailable"):
        resident_memory.darwin_resident_kib()


def test_darwin_budget_uses_direct_reader_and_preserves_memory_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep every guard query and the original ceiling while excluding subprocess launches.
    """
    monkeypatch.setattr("devtools.ribbon_analysis.budget.sys", SimpleNamespace(platform="darwin"))
    values = iter((100, 4194304))
    monkeypatch.setattr("devtools.ribbon_analysis.budget.darwin_resident_kib", lambda: next(values))

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        """
        Fail if a macOS checkpoint falls back to a process launch.
        """
        pytest.fail("macOS memory checkpoints must not launch ps")

    monkeypatch.setattr(budget.subprocess, "run", forbidden)
    guard = budget.NativeBudget(memory=budget.resident_kib, maximum_rss_kib=4194304)
    guard.check("first")
    with pytest.raises(RuntimeError, match="Scheduling limit"):
        guard.check("second")
    assert [sample["rss_kib"] for sample in guard.samples] == [100, 4194304]


def test_other_platforms_keep_existing_ps_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Preserve the existing external reader on systems without the macOS libproc API.
    """
    monkeypatch.setattr("devtools.ribbon_analysis.budget.sys", SimpleNamespace(platform="linux"))

    def run(command: list[str], **kwargs: Any) -> SimpleNamespace:
        """
        Validate that the retained fallback measures this process in RSS units.
        """
        assert command == ["/bin/ps", "-o", "rss=", "-p", str(os.getpid())]
        assert kwargs == {"check": True, "capture_output": True, "text": True}
        return SimpleNamespace(stdout=" 1024\n")

    monkeypatch.setattr(budget.subprocess, "run", run)
    assert budget.resident_kib() == 1024
