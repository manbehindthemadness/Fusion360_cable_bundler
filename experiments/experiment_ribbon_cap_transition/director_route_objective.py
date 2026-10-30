"""
Screen retained geometry policies while fitting a regular director-routing family.

These are search penalties,not calibrated elastic energy or relaxed acceptance.
"""

from __future__ import annotations

import math
from enum import Enum

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from devtools.ribbon_analysis.pinch import BendModel, PinchLimit

from .constraint_policy import Rule, for_field
from .director_path_contracts import FramedPath
from .endpoint_first import EndpointCase


class SearchDomain(Enum):
    """
    Separate a structurally regular chart from an unconstrained search surrogate.
    """

    REGULAR = "regular-chart"
    FREE = "free-with-fold-penalty"


class ObjectiveScope(Enum):
    """
    Keep historical sphere feedback explicit and separate from general routing.
    """

    LEGACY_SPHERE = "legacy-sphere-feedback"
    ROUTING = "routing-with-independent-stress-test"


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


def routing_penalties(case: EndpointCase, path: FramedPath) -> tuple[float, ...]:
    """
    Measure material and bend margins without reading a harness sphere or pose.
    """
    return _penalties(case, path, SearchDomain.FREE, ObjectiveScope.ROUTING)


def _penalties(
    case: EndpointCase,
    path: FramedPath,
    domain: SearchDomain,
    scope: ObjectiveScope = ObjectiveScope.LEGACY_SPHERE,
) -> tuple[float, ...]:
    """
    Add33station curvature/radius/containment penalties with conservative goals.

    Hard final limits remain.8,3diameters and5width sphere. Searching for.78,
    3.1diameters and.97sphere leaves sampling margin. Full-width minimum J is
    analytical for eachstation;this function neither clips geometry nor certifies it.
    """
    field = path.field
    constraints = for_field(field)
    half = field.half_width_mm
    reach = math.hypot(half, case.diameter_mm / 2)
    midpoint = case.start.translated(difference(case.end, case.start), 0.5)
    sphere = 2.5 * case.lines * case.diameter_mm * 0.97
    penalties = []
    for i in range(33):
        u = i / 32
        k, eta, eta_s = field.sample(u)
        minimum_j = 1 - half * abs(eta_s)
        if minimum_j <= 0 and domain is SearchDomain.REGULAR:
            raise ValueError("Regular director parameterization lost its Jacobian bound.")
        pinch = constraints.bend_model is BendModel.PINCH
        circular = pinch and case.lines == 1
        if domain is SearchDomain.FREE:
            penalties.append(0.0 if circular else 0.2 * math.log1p(max(0.0, 0.1 - minimum_j)))
        if pinch:
            factor = 1.0 if circular else 1 + eta * eta
            denominator = 1.0 if circular else minimum_j
            lane_violation = (
                max(
                    0.0,
                    abs(k)
                    * case.diameter_mm
                    / 2
                    * factor
                    / denominator
                    / PinchLimit(constraints.pinch_percent).fraction
                    - 1,
                )
                if denominator > 0
                else 1 + abs(denominator)
            )
        else:
            lane_violation = (
                max(0.0, abs(k) * 3.1 * case.diameter_mm / minimum_j - 1)
                if minimum_j > 0
                else 1 + abs(minimum_j)
            )
        penalties.extend(
            (
                0.2 * math.log1p(max(0.0, abs(k) * reach / 0.78 - 1))
                if not pinch and constraints.enabled(Rule.CENTRE_BEND)
                else 0.0,
                0.2 * math.log1p(lane_violation) if constraints.enabled(Rule.LANE_BEND) else 0.0,
            )
        )
        if scope is ObjectiveScope.LEGACY_SPHERE:
            state, _ = path.pose(u)
            p, t, w = Vector3(*state[:3]), Vector3(*state[3:6]), Vector3(*state[6:9])
            extent = max(
                magnitude(difference(p.translated(w, q).translated(t, q * eta), midpoint))
                + case.diameter_mm / 2
                for q in (-half, half)
            )
            penalties.append(0.2 * math.log1p(max(0.0, extent / sphere - 1)))
    return tuple(penalties)
