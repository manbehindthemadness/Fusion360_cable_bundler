"""
Host-independent settings and geometry for routing controls.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AutoTransitionPreset(str, Enum):
    """
    Select the preferred span share used by automatic interpolation distances.
    """

    TIGHT = "tight"
    COMPACT = "compact"
    BALANCED = "balanced"
    RELAXED = "relaxed"
    LOOSE = "loose"

    @property
    def span_fraction(self) -> float:
        """
        Return the per-side share of a route span requested before safety limiting.
        """
        return {
            AutoTransitionPreset.TIGHT: 0.25,
            AutoTransitionPreset.COMPACT: 0.3125,
            AutoTransitionPreset.BALANCED: 0.375,
            AutoTransitionPreset.RELAXED: 0.4375,
            AutoTransitionPreset.LOOSE: 0.5,
        }[self]


@dataclass(frozen=True)
class InterpolationSettings:
    """
    Bound each profile's orientation influence; None selects a quarter-span length.

    End sections interpret approach/departure in terminal-to-pathway stack order.
    """

    approach_mm: Optional[float] = None
    departure_mm: Optional[float] = None

    def __post_init__(self) -> None:
        """
        Reject malformed or non-finite distances at the domain boundary.
        """
        for value in (self.approach_mm, self.departure_mm):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(
                    "Transition distances must be finite nonnegative millimeters or Auto."
                )


@dataclass(frozen=True)
class RefineGeometry:
    """
    Store an unconstrained oriented pathway point independently of Fusion.

    The two unit directions span the marker plane. Their cross product is the
    route tangent; the display radius affects only the persistent marker.
    """

    origin_mm: tuple[float, float, float]
    u_direction: tuple[float, float, float]
    v_direction: tuple[float, float, float]
    display_radius_mm: float

    def __post_init__(self) -> None:
        """
        Require a finite origin, orthonormal frame, and positive marker radius.
        """
        vectors = (self.origin_mm, self.u_direction, self.v_direction)
        if any(not isinstance(vector, tuple) or len(vector) != 3 for vector in vectors):
            raise ValueError("Refine geometry requires three-dimensional vectors.")
        values = (*self.origin_mm, *self.u_direction, *self.v_direction)
        if not all(
            not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
            for value in values
        ):
            raise ValueError("Refine geometry requires finite vectors.")
        u_length = math.sqrt(sum(value * value for value in self.u_direction))
        v_length = math.sqrt(sum(value * value for value in self.v_direction))
        frame_dot = sum(left * right for left, right in zip(self.u_direction, self.v_direction))
        if not math.isclose(u_length, 1.0, abs_tol=1e-6):
            raise ValueError("Refine U direction must be a unit vector.")
        if not math.isclose(v_length, 1.0, abs_tol=1e-6):
            raise ValueError("Refine V direction must be a unit vector.")
        if not math.isclose(frame_dot, 0.0, abs_tol=1e-6):
            raise ValueError("Refine directions must be orthogonal.")
        if (
            isinstance(self.display_radius_mm, bool)
            or not isinstance(self.display_radius_mm, (int, float))
            or not math.isfinite(self.display_radius_mm)
            or self.display_radius_mm <= 0.0
        ):
            raise ValueError("Refine display radius must be finite and positive.")
