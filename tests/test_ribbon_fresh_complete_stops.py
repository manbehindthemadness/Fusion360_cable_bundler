"""
Keep broad numerical sampling from continuing after unsafe or unknown worker failures.
"""

from __future__ import annotations

from typing import Any

import pytest

from artifacts.verification.resume3366.stops import hard_stop


@pytest.mark.parametrize(
    "error,resource,free,peak,expected",
    (
        ("RuntimeError: Shared trunk metric span allocation exhausted", None, 40, 200000, False),
        ("RuntimeError: Shared material witness allocation exhausted", None, 40, 200000, False),
        ("TimeoutError: V2 first construction exceeded four seconds", None, 40, 200000, False),
        (
            "RuntimeError: timeout",
            "Scheduling limit reached before complete gym numerical diagnostic: 10.001s, 200000 KiB RSS.",
            40,
            200000,
            False,
        ),
        (
            "RuntimeError: timeout",
            "Scheduling limit reached before complete gym numerical diagnostic: 9.001s, 200000 KiB RSS.",
            40,
            200000,
            True,
        ),
        ("RuntimeError: Shared trunk metric span allocation exhausted", None, 9, 200000, True),
        ("RuntimeError: Shared trunk metric span allocation exhausted", None, 40, 4194304, True),
        ("ValueError: malformed ownership", None, 40, 200000, True),
        ("RuntimeError: Source drift", None, 40, 200000, True),
        ("OSError: disk failure", None, 40, 200000, True),
        ("RuntimeError: cancelled", None, 40, 200000, True),
    ),
)
def test_expected_exhaustion_only(
    error: str, resource: str | None, free: int, peak: int, expected: bool
) -> None:
    """
    Explicit known case exhaustion cannot mask memory loss, source drift or an unknown exception.
    """
    result: dict[str, Any] = {
        "status": "stopped",
        "error": error,
        "resource_stop": resource,
        "minimum_system_free_percent": free,
    }
    assert hard_stop(result, peak) is expected
