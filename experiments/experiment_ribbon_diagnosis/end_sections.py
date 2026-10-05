"""
Limit authored split-end route lengths without weakening curvature certification.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from cable_bundler.routing.geometry import CubicBezier, Vector3
from cable_bundler.routing.parallel import RoutePreview
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.transitions import connection_turn

from .compact import length_bounds


@dataclass
class CappedConnectionTurns:
    """
    Apply a six-percent cap to every lane at each end of the diagnostic trunk.

    Use a trunk-length lower bound and branch-length upper bound so numerical
    integration error cannot enlarge the allowance. The shared harness still
    certifies each resulting branch; an infeasible turn is never enlarged or
    replaced with a different topology in response to a failure.
    """

    case: RibbonStressCase
    turn_degrees: float = 90.0
    observations: list[dict[str, object]] = field(default_factory=list)

    def _turn(
        self, center: Vector3, inward: Vector3, bend: Vector3, radius: float, name: str
    ) -> RoutePreview:
        """
        Author the declared angle independently of solver success or failure.
        """
        if not 0 < self.turn_degrees <= 90:
            raise ValueError("Connection turn must be in (0, 90] degrees.")
        if self.turn_degrees == 90:
            return connection_turn(center, inward, bend, radius, name)
        angle = math.radians(self.turn_degrees)
        handle = 4 / 3 * math.tan(angle / 4) * radius
        start = center.translated(inward, -radius * math.sin(angle)).translated(
            bend, radius * (1 - math.cos(angle))
        )
        control = start.translated(inward, handle * math.cos(angle)).translated(
            bend, -handle * math.sin(angle)
        )
        curve = CubicBezier(start, control, center.translated(inward, -handle), center)
        template = connection_turn(center, inward, bend, radius, name)
        return RoutePreview(template.cable_id, name, (start, center), (curve,))

    def __call__(
        self, center: Vector3, inward: Vector3, bend: Vector3, radius_mm: float, name: str
    ) -> RoutePreview:
        """
        Retain the declared circular-turn angle but bound its full arc length.
        """
        trunk_lower, _ = length_bounds(self.case.route.curves)
        maximum = 0.06 * trunk_lower
        unit_route = self._turn(Vector3(0, 0, 0), inward, bend, 1.0, name)
        _, unit_upper = length_bounds(unit_route.curves)
        radius = min(radius_mm, maximum / unit_upper)
        route = self._turn(center, inward, bend, radius, name)
        lower, upper = length_bounds(route.curves)
        if upper > maximum + 1e-9:
            raise ValueError("Split-end route exceeds its six-percent length cap.")
        self.observations.append(
            {
                "name": name,
                "trunk_length_lower_mm": trunk_lower,
                "maximum_length_mm": maximum,
                "length_lower_mm": lower,
                "length_upper_mm": upper,
                "radius_mm": radius,
                "fraction_limit": 0.06,
                "turn_degrees": self.turn_degrees,
            }
        )
        return route
