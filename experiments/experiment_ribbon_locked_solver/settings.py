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
    Configure first-pass optimization, aesthetic smoothing and deferred material coordinates.

    Smoothing0disables the aesthetic second pass; bounded numerical sliver cleanup
    remains active. Positive percentages cap extra
    material length relative to the first pass; they do not guarantee monotonic
    visible smoothing under finite contact bounds. Default5preserves the selected
    policy. UV metadata never creates or assigns an appearance or bitmap.
    First-pass optimization defaults on and is independent of aesthetic smoothing.
    """

    smoothing_percent: float = 5.0
    material_uv: bool = False
    first_pass_optimization: bool = True

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
        if type(self.first_pass_optimization) is not bool:
            raise ValueError("First-pass optimization requires an explicit boolean")

    @classmethod
    def parse(cls, payload: Any) -> Settings:
        """
        Read public controls, defaulting older two-control records to optimization enabled.
        """
        required = {"smoothing_percent", "material_uv"}
        if not isinstance(payload, dict) or not required <= set(payload) <= required | {
            "first_pass_optimization"
        }:
            raise ValueError(
                "Supply smoothing_percent, material_uv and optional first_pass_optimization only"
            )
        return cls(**payload)
