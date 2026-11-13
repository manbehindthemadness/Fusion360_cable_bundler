"""
Discover competing material crossings near a current connector intrusion without claiming clearance.
"""

from __future__ import annotations

import math
from typing import Callable

from cable_bundler.routing.geometry import difference, dot
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.contact_phase_core import ProfileProbe
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .check import Report
from .restoration_order import MaterialFocus
from .restoration_screen import screen


def focus(route: FoldRoute, report: Report, checkpoint: Callable[[], None]) -> MaterialFocus | None:
    """
    Order nonadjacent pairs involving the occupied carrier or its immediate material neighbours.

    Three center samples per piece rank proximity to the actual occupied point.
    They supply ordering only, never an exclusion, witness or separation result.
    A stale member point declines discovery rather than transferring old identity.
    """
    if report.status != "blocked" or report.witness is None:
        return None
    witness = report.witness
    if type(witness.piece) is not int or not 0 <= witness.piece < len(route.pieces):
        raise ValueError("Hardware discovery needs an existing current material member")
    point = witness.point
    if any(not math.isfinite(value) for value in (point.x, point.y, point.z)):
        raise ValueError("Hardware discovery needs a finite occupied point")
    checkpoint()
    if (
        occupied_coordinates(
            route.pieces[witness.piece], point, route.targets.lines, route.targets.diameter_mm
        )
        is None
    ):
        return None
    incident = {
        index
        for index in (witness.piece - 1, witness.piece, witness.piece + 1)
        if 0 <= index < len(route.pieces)
    }
    distances = []
    for piece in route.pieces:
        checkpoint()
        squared = []
        for parameter in (0.0, 0.5, 1.0):
            delta = difference(piece.surface(parameter, 0.0)[0], point)
            squared.append(dot(delta, delta))
        distances.append(min(squared))
    pairs = [
        (first, second)
        for first in range(len(route.pieces))
        for second in range(first + 2, len(route.pieces))
        if first in incident or second in incident
    ]
    pairs.sort(key=lambda pair: (distances[pair[0]] + distances[pair[1]], pair))
    return MaterialFocus(route, tuple(pairs[:32])) if pairs else None


class HardwareContacts:
    """
    Own negative discovery for at most four changed candidates inside one adaptive allocation.

    Each exact route is visited once, with at most32comparisons and128in total;
    all queries also share the parent's original pair/CPU allowance. One probe
    context retains the original2048support ceiling and bounded preparations.
    Profile-prism proposals still require both original strict material inverses.
    A miss or skipped query cannot supply clearance or renew any correction work.
    """

    def __init__(self) -> None:
        """
        Start bounded route ownership and pure proposal preparation with no retained result certificates.
        """
        self._seen: dict[int, FoldRoute] = {}
        self._probe = FlatProbe()
        self._profile = ProfileProbe()
        self._pairs = 0

    def inspect(
        self,
        route: FoldRoute,
        report: Report,
        maximum_pairs: int,
        checkpoint: Callable[[], None],
    ) -> ContactResult | None:
        """
        Run one negative screen within the supplied remaining pool, declining stale or repeated owners.
        """
        if type(maximum_pairs) is not int or maximum_pairs < 0:
            raise ValueError("Use nonnegative remaining material comparisons")
        checkpoint()
        if not maximum_pairs or id(route) in self._seen or len(self._seen) == 4:
            return None
        self._seen[id(route)] = route
        priority = focus(route, report, checkpoint)
        if priority is None:
            return None
        allowance = min(32, maximum_pairs)
        result = screen(
            route,
            self._probe,
            allowance,
            checkpoint,
            lambda _: True,
            focus=priority,
            flat_core_probe=self._profile,
        )
        if (
            result.status not in ("penetration", "unresolved")
            or type(result.pairs_checked) is not int
            or not 0 <= result.pairs_checked <= allowance
            or (
                result.status == "penetration"
                and (result.witness is None or result.limit is not None)
            )
        ):
            raise ArithmeticError(
                "Negative hardware discovery cannot supply clearance or renew work"
            )
        self._pairs += result.pairs_checked
        return result

    def statistics(self) -> dict[str, int]:
        """
        Report completed negative work separately from full certificates and interrupted upper bounds.
        """
        return {
            "routes": len(self._seen),
            "completed_pairs": self._pairs,
            "supports": self._probe.supports,
            "maximum_routes": 4,
            "maximum_pairs_per_route": 32,
        }
