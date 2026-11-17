"""
Keep failure-target scheduling separate from complete-ribbon preparation and physical qualification.
"""

from __future__ import annotations

from typing import Any

import pytest

from artifacts.verification.resume3368.policy import category, continue_batches


@pytest.mark.parametrize(
    "failures,batches,expected",
    ((0, 0, True), (49, 12, True), (50, 12, False), (53, 12, False), (0, 100, False)),
)
def test_failure_target_is_checked_between_full_batches(
    failures: int, batches: int, expected: bool
) -> None:
    """
    Crossing the target closes future batches without deleting the current hundred's tail.
    """
    assert continue_batches(failures, batches) is expected


@pytest.mark.parametrize(
    "status,material,stop,expected",
    (
        (
            "unqualified",
            "within_planned_increment_bound",
            False,
            "prepared_with_longitudinal_bound",
        ),
        ("trunk_unresolved", "unattempted", False, "trunk_unresolved"),
        ("unqualified", "upper_unresolved", False, "material_unresolved"),
        ("planned_material_violation", "upper_unresolved", False, "material_violation"),
        ("stopped", "stopped", False, "case_exhaustion"),
        ("stopped", "stopped", True, "infrastructure_stop"),
    ),
)
def test_failure_categories_keep_missing_evidence_visible(
    status: str, material: str, stop: bool, expected: str
) -> None:
    """
    An unqualified case needs every ending and its longitudinal bound to pass this numerical scope.
    """
    row: dict[str, Any] = {
        "status": status,
        "planned_material": material,
        "stop": stop,
        "prepared_branches": 4,
        "lines": 2,
    }
    assert category(row) == expected
    if expected == "prepared_with_longitudinal_bound":
        row["prepared_branches"] = 3
        with pytest.raises(RuntimeError):
            category(row)
