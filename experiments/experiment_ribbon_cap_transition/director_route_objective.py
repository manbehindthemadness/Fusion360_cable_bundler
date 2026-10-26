"""
Screen retained geometry policies while fitting a regular director-routing family.

These are search penalties,not calibrated elastic energy or relaxed acceptance.
"""

from __future__ import annotations

import math
from enum import Enum

from cable_bundler.routing.geometry import Vector3, difference, magnitude

from .director_path_contracts import FramedPath
from .endpoint_first import EndpointCase


class SearchDomain(Enum):
    """
    Separate a structurally regular chart from an unconstrained search surrogate.
    """

    REGULAR = "regular-chart"
    FREE = "free-with-fold-penalty"


def regular_penalties(case: EndpointCase, path: FramedPath) -> tuple[float, ...]:
    """
    Keep the existing regular-chart search entry point and its rejection contract.
    """
    return _penalties(case, path, SearchDomain.REGULAR)


def free_penalties(case: EndpointCase, path: FramedPath) -> tuple[float, ...]:
    """
    Penalize invalid search iterates without certifying or drawing them as ribbons.
    """
    return _penalties(case, path, SearchDomain.FREE)


def _penalties(case: EndpointCase, path: FramedPath, domain: SearchDomain) -> tuple[float, ...]:
    """
    Add33station curvature/radius/containment penalties with conservative goals.

    Hard final limits remain.8,3diameters and5width sphere. Searching for.78,
    3.1diameters and.97sphere leaves sampling margin. Full-width minimum J is
    analytical for eachstation;this function neither clips geometry nor certifies it.
    """
    field = path.field
    half = field.half_width_mm
    reach = math.hypot(half, case.diameter_mm / 2)
    midpoint = case.start.translated(difference(case.end, case.start), 0.5)
    sphere = 2.5 * case.lines * case.diameter_mm * 0.97
    penalties = []
    for i in range(33):
        u = i / 32
        state, _ = path.pose(u)
        k, eta, eta_s = field.sample(u)
        minimum_j = 1 - half * abs(eta_s)
        if minimum_j <= 0 and domain is SearchDomain.REGULAR:
            raise ValueError("Regular director parameterization lost its Jacobian bound.")
        p, t, w = Vector3(*state[:3]), Vector3(*state[3:6]), Vector3(*state[6:9])
        extent = max(
            magnitude(difference(p.translated(w, q).translated(t, q * eta), midpoint))
            + case.diameter_mm / 2
            for q in (-half, half)
        )
        if domain is SearchDomain.FREE:
            penalties.append(0.2 * math.log1p(max(0.0, 0.1 - minimum_j)))
        lane_violation = (
            max(0.0, abs(k) * 3.1 * case.diameter_mm / minimum_j - 1)
            if minimum_j > 0
            else 1 + abs(minimum_j)
        )
        penalties.extend(
            (
                0.2 * math.log1p(max(0.0, abs(k) * reach / 0.78 - 1)),
                0.2 * math.log1p(lane_violation),
                0.2 * math.log1p(max(0.0, extent / sphere - 1)),
            )
        )
    return tuple(penalties)
