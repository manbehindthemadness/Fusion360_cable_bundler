"""
Validate finite JSON primitives shared by archives and optional run settings.
"""

from __future__ import annotations

import math
from typing import Any


def json_object(value: Any) -> dict[str, Any]:
    """
    Require an object at a structured JSON boundary.
    """
    if not isinstance(value, dict):
        raise ValueError("Expected an inspection JSON object.")
    return value


def finite_number(value: Any) -> float:
    """
    Reject boolean, null and nonfinite values before numerical conversion.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Inspection numbers must be finite.")
    return float(value)


def integer_value(value: Any) -> int:
    """
    Require an actual integer without silently truncating control or archive data.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Inspection counts must be integers.")
    return value
