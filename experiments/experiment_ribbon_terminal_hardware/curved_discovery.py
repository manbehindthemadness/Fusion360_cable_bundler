"""
Propose actual curved material points for strict negative discovery, never clearance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact import (
    Penetration,
    ProbeResult,
    validate_negative_probe,
)
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute


@dataclass
class CurvedProbe:
    """
    Count current-pose midpoint proposals independently of the unchanged flat support context.

    No result or geometry is cached. The owner charges every proposal against
    its existing contact comparison pool and retains all final physical checks.
    """

    candidates: int = 0
    inverse_tests: int = 0

    def __call__(
        self,
        route: FoldRoute,
        first: int,
        second: int,
        remaining_pairs: int,
        checkpoint: Callable[[], None],
    ) -> ProbeResult:
        """
        Try both interior width anchors and center at each actual curved phase midpoint.

        The width-dependent material coordinate follows the fold's bank, rather
        than assuming u=.5 is curved. Skip phase points outside the real material
        cut. Both unchanged strict inverses must occupy the same proposed point.
        A miss, limited sampling or absent fold supplies no clearance or axis.
        """
        validate_negative_probe(route, first, second, remaining_pairs)
        checked = 0
        reach = route.half_width_mm - route.targets.diameter_mm / 4
        for index in (first, second):
            geometry = route.pieces[index].geometry
            if not isinstance(geometry, CylindricalFold):
                continue
            c, s = math.cos(geometry.bank_radians), math.sin(geometry.bank_radians)
            for q in (-reach, reach, 0.0):
                checkpoint()
                if checked >= remaining_pairs:
                    return ProbeResult(checked)
                xi = geometry.radius_mm * abs(geometry.angle_radians) / 2
                u = (geometry.before_mm + (xi - s * q) / c) / geometry.material_length_mm
                if not math.isfinite(u) or not 0 < u < 1:
                    continue
                point = route.pieces[index].surface(u, q)[0]
                checked += 1
                self.candidates += 1
                coordinates = []
                for member in (first, second):
                    self.inverse_tests += 1
                    coordinates.append(
                        occupied_coordinates(
                            route.pieces[member],
                            point,
                            route.targets.lines,
                            route.targets.diameter_mm,
                        )
                    )
                a, b = coordinates
                if a is not None and b is not None:
                    return ProbeResult(checked, Penetration((first, second), a, b, point))
        return ProbeResult(checked)
