"""
Describe immutable analysis inputs without importing an experiment or Fusion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from cable_bundler.routing.geometry import Vector3, dot, magnitude

from .provenance import mark_loaded


class RibbonField(Protocol):
    """
    Supply dimensions and intrinsic k,eta,eta_s reference measurements.
    """

    @property
    def lines(self) -> int:
        """
        Return the ordered conductor count.
        """
        ...

    @property
    def diameter_mm(self) -> float:
        """
        Return the circular conductor diameter in millimeters.
        """
        ...

    @property
    def half_width_mm(self) -> float:
        """
        Return the actual outer material-guide offset including declared padding.
        """
        ...

    def sample(self, u: float) -> tuple[float, float, float]:
        """
        Return curvature per millimeter,eta,and eta's material-length derivative.
        """
        ...


class RibbonPath(Protocol):
    """
    Supply stable lane positions and actual normalized-parameter derivatives.
    """

    @property
    def field(self) -> RibbonField:
        """
        Return the dimensions and intrinsic reference-field evaluator.
        """
        ...

    def lane(self, u: float, offset_mm: float) -> tuple[Vector3, Vector3]:
        """
        Return the lane's millimeter position and derivative with respect to u.
        """
        ...


class TargetPose(Protocol):
    """
    Expose fixed ordered endpoints without prescribing a solver implementation.
    """

    @property
    def name(self) -> str:
        """
        Return the fixture or user input identity.
        """
        ...

    @property
    def start(self) -> Vector3:
        """
        Return the fixed start center.
        """
        ...

    @property
    def end(self) -> Vector3:
        """
        Return the fixed end center.
        """
        ...

    @property
    def start_tangent(self) -> Vector3:
        """
        Return the fixed unit start tangent.
        """
        ...

    @property
    def end_tangent(self) -> Vector3:
        """
        Return the fixed unit end tangent.
        """
        ...

    @property
    def start_width(self) -> Vector3:
        """
        Return the fixed unit start width direction preserving conductor order.
        """
        ...

    @property
    def end_width(self) -> Vector3:
        """
        Return the fixed unit end width direction preserving conductor order.
        """
        ...

    @property
    def lines(self) -> int:
        """
        Return the fixed conductor count.
        """
        ...

    @property
    def diameter_mm(self) -> float:
        """
        Return the fixed conductor diameter.
        """
        ...


@dataclass(frozen=True)
class Targets:
    """
    Copy endpoint inputs so later solver edits cannot alter recorded evidence.
    """

    name: str
    start: Vector3
    end: Vector3
    start_tangent: Vector3
    end_tangent: Vector3
    start_width: Vector3
    end_width: Vector3
    lines: int
    diameter_mm: float

    @classmethod
    def capture(cls, source: TargetPose) -> Targets:
        """
        Validate finite dimensions and perpendicular unit endpoint frames.
        """
        captured = cls(
            source.name,
            source.start,
            source.end,
            source.start_tangent,
            source.end_tangent,
            source.start_width,
            source.end_width,
            source.lines,
            source.diameter_mm,
        )
        if not isinstance(captured.name, str) or not captured.name.strip():
            raise ValueError("Targets need a nonempty identity.")
        if (
            isinstance(captured.lines, bool)
            or not isinstance(captured.lines, int)
            or not 1 <= captured.lines <= 128
        ):
            raise ValueError("Analysis supports1..128ordered conductors.")
        if not math.isfinite(captured.diameter_mm) or captured.diameter_mm <= 0:
            raise ValueError("Targets need a positive finite diameter.")
        vectors = (
            captured.start,
            captured.end,
            captured.start_tangent,
            captured.end_tangent,
            captured.start_width,
            captured.end_width,
        )
        if any(not all(math.isfinite(v) for v in (p.x, p.y, p.z)) for p in vectors):
            raise ValueError("Target coordinates must be finite.")
        for tangent, width in (
            (captured.start_tangent, captured.start_width),
            (captured.end_tangent, captured.end_width),
        ):
            if (
                max(
                    abs(magnitude(tangent) - 1), abs(magnitude(width) - 1), abs(dot(tangent, width))
                )
                > 1e-8
            ):
                raise ValueError("Target frames must be perpendicular unit vectors.")
        return captured


mark_loaded(__file__)
