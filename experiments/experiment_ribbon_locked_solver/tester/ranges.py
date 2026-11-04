"""
Validate finite stepped input ranges without materializing their Cartesian product.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any


@dataclass(frozen=True)
class NumericRange:
    """
    Retain exact decimal range endpoints and a positive step, with at most one million values.
    """

    minimum: Decimal
    maximum: Decimal
    step: Decimal

    @classmethod
    def parse(cls, payload: Any) -> NumericRange:
        """
        Reject malformed, nonfinite, reversed or unreasonably dense external ranges.
        """
        if not isinstance(payload, dict) or set(payload) != {"min", "max", "step"}:
            raise ValueError("Each range needs min, max and step.")
        values = []
        for key in ("min", "max", "step"):
            raw = payload[key]
            if type(raw) not in (str, int, float) or not 0 < len(str(raw)) <= 64:
                raise ValueError("Range values must be finite decimal numbers.")
            try:
                value = Decimal(str(raw))
            except InvalidOperation as error:
                raise ValueError("Range values must be decimal numbers.") from error
            if (
                not value.is_finite()
                or not math.isfinite(float(value))
                or (value and not float(value))
            ):
                raise ValueError("Range values must be finite representable numbers.")
            values.append(value)
        result = cls(*values)
        if result.minimum > result.maximum or result.step <= 0:
            raise ValueError("Range min must not exceed max; step must be positive.")
        if result.count > 1_000_000:
            raise ValueError("Use at most 1,000,000 values in one range.")
        return result

    @property
    def count(self) -> int:
        """
        Count reachable values inclusively, avoiding decimal or binary accumulation drift.
        """
        return int((Fraction(self.maximum) - Fraction(self.minimum)) // Fraction(self.step)) + 1

    def value(self, index: int) -> int | float:
        """
        Evaluate one indexed value without allocating a potentially large range.
        """
        if not 0 <= index < self.count:
            raise ValueError("Range index is outside its declared values.")
        value = Fraction(self.minimum) + index * Fraction(self.step)
        return int(value) if value.denominator == 1 else float(value)

    def payload(self) -> dict[str, str]:
        """
        Preserve original decimal values in plans and reconnecting form controls.
        """
        return {
            "min": self.minimum.to_eng_string(),
            "max": self.maximum.to_eng_string(),
            "step": self.step.to_eng_string(),
        }


@dataclass(frozen=True)
class Field:
    """
    Describe one existing gym input's limits and user-facing units.
    """

    name: str
    label: str
    minimum: int
    maximum: int | None = None
    integer: bool = True
    positive: bool = False

    def validate(self, values: NumericRange) -> None:
        """
        Enforce gym bounds before any test plan, drawing or worker is created.
        """
        if values.minimum < self.minimum or (
            self.maximum is not None and values.maximum > self.maximum
        ):
            raise ValueError(f"{self.label} is outside its supported gym bounds.")
        if self.positive and values.minimum <= 0:
            raise ValueError(f"{self.label} must be positive.")
        if self.integer and any(
            value != value.to_integral_value()
            for value in (values.minimum, values.maximum, values.step)
        ):
            raise ValueError(f"{self.label} requires integer min, max and step.")


FIELDS = (
    Field("lines", "Conductors", 1, 128),
    Field("diameter_mm", "Diameter (mm)", 0, integer=False, positive=True),
    Field("void_percent", "Central void (%)", 300, integer=False),
    Field("zone_percent", "Zone depth (%)", 0, integer=False, positive=True),
    Field("a_zone", "A zone (1–26)", 1, 26),
    Field("a_face", "A face (1–12)", 1, 12),
    Field("a_roll", "A roll (degrees)", 0, 359),
    Field("b_zone", "B zone (1–26)", 1, 26),
    Field("b_face", "B face (1–12)", 1, 12),
    Field("b_roll", "B roll (degrees)", 0, 359),
)
