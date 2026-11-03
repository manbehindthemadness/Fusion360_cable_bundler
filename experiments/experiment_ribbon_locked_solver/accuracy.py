"""
Separate native dimensional accuracy goals from the user-directed display warning ceiling.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DimensionalAccuracy:
    """
    Keep the original millimeter goal; optionally permit only strictly sub-limit warnings.

    This policy covers measured dimensional discrepancies, never topology,
    membership/identity proofs, angles, contact, material rules or resource limits.
    None retains the historical strict acceptance policy.
    """

    goal_mm: float = 1e-6
    warning_below_mm: float | None = None

    def __post_init__(self) -> None:
        """
        Reject malformed goals or ceilings that would hide the original accuracy target.
        """
        if (
            type(self.goal_mm) not in (int, float)
            or not math.isfinite(self.goal_mm)
            or self.goal_mm <= 0
        ):
            raise ValueError("Dimensional accuracy requires a positive finite goal")
        limit = self.warning_below_mm
        if limit is not None and (
            type(limit) not in (int, float) or not math.isfinite(limit) or limit <= self.goal_mm
        ):
            raise ValueError("A finite warning ceiling must exceed the original accuracy goal")

    @property
    def search_radius_mm(self) -> float:
        """
        Bound native correspondence queries consistently with the selected dimensional policy.
        """
        return self.warning_below_mm if self.warning_below_mm is not None else self.goal_mm

    def accepts(self, error_mm: float) -> bool:
        """
        Accept original accuracy or a finite nonnegative discrepancy strictly below the ceiling.
        """
        return (
            type(error_mm) in (int, float)
            and math.isfinite(error_mm)
            and error_mm >= 0
            and (
                error_mm <= self.goal_mm
                or self.warning_below_mm is not None
                and error_mm < self.warning_below_mm
            )
        )

    def meets_goal(self, error_mm: float) -> bool:
        """
        Require valid finite data before classifying a dimensional measurement as on target.
        """
        return (
            type(error_mm) in (int, float)
            and math.isfinite(error_mm)
            and 0 <= error_mm <= self.goal_mm
        )

    def observe(
        self, output: dict[str, Any], category: str, error_mm: float, **context: Any
    ) -> bool:
        """
        Retain every accepted goal miss with its original goal, ceiling and measurement context.

        Return false for a hard dimensional failure; do not turn missing/nonfinite
        data into warnings. Callers independently enforce nondimensional invariants.
        """
        if not self.accepts(error_mm):
            return False
        if error_mm > self.goal_mm:
            output.setdefault("accuracy_warnings", []).append(
                {
                    "category": category,
                    "error_mm": error_mm,
                    "goal_mm": self.goal_mm,
                    "warning_below_mm": self.warning_below_mm,
                    **context,
                }
            )
        return True


STRICT_ACCURACY = DimensionalAccuracy()
DISPLAY_ACCURACY = DimensionalAccuracy(warning_below_mm=0.01)


def warning_summary(findings: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Summarize completed dimensional warnings without erasing their original detailed records.
    """
    if not findings:
        return None
    maximum = max(float(finding["error_mm"]) for finding in findings)
    categories = sorted({finding["category"] for finding in findings})
    return {
        "measurement_count": len(findings),
        "maximum_error_mm": maximum,
        "goal_mm": DISPLAY_ACCURACY.goal_mm,
        "warning_below_mm": DISPLAY_ACCURACY.warning_below_mm,
        "categories": categories,
        "message": (
            f"Native accuracy warning: {len(findings)} dimensional measurements miss the "
            f"original {DISPLAY_ACCURACY.goal_mm:g} mm goal; maximum {maximum:.6g} mm. "
            "All are below 0.01 mm. Original accuracy findings are retained."
        ),
    }
