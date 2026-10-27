"""
Refresh full-width proximity models without retaining stale separating directions.

This sampled planning heuristic is not continuous collision detection or IPC.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from cable_bundler.routing.geometry import cross, difference, magnitude
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.edge_clearance import NearPair
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from .contact import audit
from .guidance import PlanePair, from_witness


@dataclass(frozen=True)
class ClearanceSnapshot:
    """
    Freeze eight local support models and the same path's actual distance deficits.

    A missing plane retains a constant deficit for an ambiguous exact parallel
    coincidence,or zero padding. No world-axis escape is invented for ambiguity.
    """

    planes: tuple[PlanePair | None, ...]
    deficits: tuple[float, ...]
    contacts: dict[str, Any]
    ambiguous_pairs: int

    def model(self, path: CompatiblePath) -> tuple[float, ...]:
        """
        Keep pair identities/directions fixed during one numerical linearization.
        """
        return tuple(
            deficit if plane is None else plane.violation(path)
            for plane, deficit in zip(self.planes, self.deficits)
        )


def linearize(
    pairs: tuple[NearPair, ...], thickness_mm: float
) -> tuple[tuple[PlanePair | None, ...], tuple[float, ...], int]:
    """
    Model the eight closest full-width pairs using a relative5%planning buffer.

    The buffer is a search margin,not a changed physical thickness/acceptance rule.
    Pairs come from the existing2Dspatial/3Dmaterial filters. Empty slots stay zero.
    Rebuild the tuple for each current iterate;never append historical planes.
    """
    if not math.isfinite(thickness_mm) or thickness_mm <= 0:
        raise ValueError("Width guidance requires positive finite thickness.")
    target = 1.05 * thickness_mm
    ordered = sorted(pairs, key=lambda p: (p.distance_mm, p.first.fraction, p.second.fraction))[:8]
    planes: list[PlanePair | None] = []
    deficits: list[float] = []
    ambiguous = 0
    for pair in ordered:
        direction = difference(pair.first_point, pair.second_point)
        transverse = cross(
            difference(pair.first.end, pair.first.start),
            difference(pair.second.end, pair.second.start),
        )
        if magnitude(direction) <= 1e-10 * target and magnitude(transverse) <= 1e-12:
            planes.append(None)
            ambiguous += 1
        else:
            planes.append(
                from_witness(pair.first, pair.second, (pair.first_point, pair.second_point), target)
            )
        deficits.append(max(0.0, target - pair.distance_mm) / target)
    padding = 8 - len(planes)
    return tuple(planes) + (None,) * padding, tuple(deficits) + (0.0,) * padding, ambiguous


def sample(
    case: EndpointCase, path: CompatiblePath, checkpoint: Callable[[], None]
) -> ClearanceSnapshot:
    """
    Measure actual current proximity once and freeze its corresponding local model.
    """
    pairs: list[NearPair] = []
    contacts, _ = audit(case, path, checkpoint, pair_observer=pairs.append)
    planes, deficits, ambiguous = linearize(tuple(pairs), case.diameter_mm)
    return ClearanceSnapshot(planes, deficits, contacts, ambiguous)
