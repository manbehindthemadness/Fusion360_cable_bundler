"""
Add a smooth spatial offset and return while retaining exact endpoint positions and tangents.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_spline_guide.guide import Guide


@dataclass(frozen=True)
class DeviationGuide(Guide):
    """
    Displace the interior cubic by16u²(1-u)² times one explicit world offset.

    This is a reference for isometric material construction, not a deformable
    ribbon or physical acceptance certificate. Both the bump and its first
    derivative vanish at each cap. Its two slope extrema supply exactly one
    three-stage steering sequence without heading or waypoint search.
    """

    offset_mm: Vector3

    @classmethod
    def deviated(cls, targets: Targets, offset_mm: Vector3) -> DeviationGuide:
        """
        Rebuild only the interior samples and arc lookup for a finite nonzero offset.
        """
        if (
            any(not math.isfinite(v) for v in (offset_mm.x, offset_mm.y, offset_mm.z))
            or magnitude(offset_mm) <= 0
        ):
            raise ValueError("A spatial deviation requires a finite nonzero world offset")
        base = Guide.create(targets)
        provisional = cls(base.controls, base.parameters, (), offset_mm)
        points = tuple(provisional.sample(u)[0] for u in base.parameters)
        distances = [0.0]
        for first, last in zip(points, points[1:]):
            distances.append(distances[-1] + magnitude(difference(last, first)))
        return cls(base.controls, base.parameters, tuple(distances), offset_mm)

    @staticmethod
    def stations() -> tuple[float, float]:
        """
        Return the analytically derived extrema of the bump's slope, in material order.
        """
        return (3 - math.sqrt(3)) / 6, (3 + math.sqrt(3)) / 6

    def sample(self, u: float) -> tuple[Vector3, Vector3]:
        """
        Evaluate the same endpoint cubic plus its exact smooth offset and derivative.
        """
        point, velocity = super().sample(u)
        bump = 16 * u**2 * (1 - u) ** 2
        slope = 32 * u * (1 - u) * (1 - 2 * u)
        return point.translated(self.offset_mm, bump), velocity.translated(self.offset_mm, slope)
