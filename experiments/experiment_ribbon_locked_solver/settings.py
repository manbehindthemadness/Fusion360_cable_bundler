"""
Validate the small user-facing configuration of the selected material solver.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

VERSION = "joint-material-v1"


@dataclass(frozen=True)
class Settings:
    """
    Configure optional smoothing allowance and deferred material coordinates.

    Smoothing0disables the complete second pass. Positive percentages cap extra
    material length relative to the first pass; they do not guarantee monotonic
    visible smoothing under finite contact bounds. Default5preserves the selected
    policy. UV metadata never creates or assigns an appearance or bitmap.
    """

    smoothing_percent: float = 5.0
    material_uv: bool = False

    def __post_init__(self) -> None:
        """
        Reject malformed values rather than silently changing an experiment's policy.
        """
        if (
            isinstance(self.smoothing_percent, bool)
            or not isinstance(self.smoothing_percent, (int, float))
            or not math.isfinite(self.smoothing_percent)
            or not 0 <= self.smoothing_percent <= 10
        ):
            raise ValueError("Smoothing allowance must be a finite percentage from0to10")
        if type(self.material_uv) is not bool:
            raise ValueError("Material UV coordinates require an explicit boolean")

    @classmethod
    def parse(cls, payload: Any) -> Settings:
        """
        Read exactly the public settings contract at palette and worker boundaries.
        """
        if not isinstance(payload, dict) or set(payload) != {"smoothing_percent", "material_uv"}:
            raise ValueError("Supply smoothing_percent and material_uv only")
        return cls(**payload)
