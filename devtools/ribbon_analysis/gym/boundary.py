"""
Measure the entire native output against one invisible extra layer of gym cubicles.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from cable_bundler.routing.geometry import Vector3

from .scene import Config


@dataclass(frozen=True)
class BoundaryReport:
    """
    Retain precise component-coordinate bounds and the separate diagnostic failure disposition.
    """

    half_extent_mm: float
    minimum_mm: Vector3
    maximum_mm: Vector3
    excess_mm: float

    @property
    def problem(self) -> str | None:
        """
        Fail any strict crossing of the closed outer cubicle box; touching is permitted.
        """
        return (
            f"Gym boundary failed: generated body exceeds the extra cubicle layer by {self.excess_mm:.6g} mm (limit ±{self.half_extent_mm:.6g} mm)."
            if self.excess_mm > 0
            else None
        )

    def payload(self) -> dict[str, Any]:
        """
        Serialize measured bounds and policy without adding solver inputs or graphic geometry.
        """
        return {
            "policy": "one-extra-cubicle-layer-v1",
            "status": "failed" if self.problem else "passed",
            "measurement": "native_precise_body_bounds_in_component_coordinates",
            **asdict(self),
        }


def assess(config: Config, minimum_mm: Vector3, maximum_mm: Vector3) -> BoundaryReport:
    """
    Compare precise whole-body bounds against half the visible extent plus one zone depth per side.

    Use each layout's actual void and zone dimensions. This is a gym stress-test
    rule only; it never steers route selection, alters geometry or proves physical
    feasibility. Invalid/missing native bounds raise instead of passing silently.
    """
    lows = (minimum_mm.x, minimum_mm.y, minimum_mm.z)
    highs = (maximum_mm.x, maximum_mm.y, maximum_mm.z)
    if any(not math.isfinite(value) for value in (*lows, *highs)) or any(
        low > high for low, high in zip(lows, highs)
    ):
        raise ValueError("Native boundary measurement requires finite ordered bounds")
    half = config.extent_mm / 2 + config.zone_mm
    excess = max(0.0, *(-half - value for value in lows), *(value - half for value in highs))
    return BoundaryReport(half, minimum_mm, maximum_mm, excess)
