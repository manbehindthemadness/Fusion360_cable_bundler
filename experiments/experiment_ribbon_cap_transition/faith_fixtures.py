"""
Author six distinct curve and endpoint configurations before certificate probing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from cable_bundler.routing.geometry import CubicBezier, Vector3, cross, lerp, unit
from experiments.experiment_ribbon_diagnosis.spatial import rotate, spatial_cases
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase

from .array_fixtures import _full_turn_boundary
from .fixtures import _arc, _case
from .regression_cases import collateral_cases


@dataclass(frozen=True)
class FaithFixture:
    """
    Retain independent curve geometry, declared signed twist and provenance.
    """

    case: RibbonStressCase
    twist_degrees: float
    parent_case: str
    purpose: str


def _rolled_case(parent: RibbonStressCase, name: str, degrees: float) -> RibbonStressCase:
    """
    Author transported end width and rotate it by the fixed diagnostic prescription.
    """
    case = _full_turn_boundary(parent, name)
    return replace(
        case, end_width=rotate(case.end_width, case.route.curves[-1].derivative(1), degrees)
    )


def faith_fixtures() -> tuple[FaithFixture, ...]:
    """
    Freeze six non-copy routes with 0,+90,-90,+180,-180,-360 degree twists.

    Width and endpoints differ through route authoring, not outcome-based repairs.
    The existing arch/spatial shapes retain lineage and are development variants.
    """
    shallow_curves = _arc(-12, 8, 40, -math.pi / 3, math.pi / 4)
    shallow = _case(
        "faith_shallow", shallow_curves, lerp(shallow_curves[0].start, shallow_curves[-1].end, 0.5)
    )
    quarter_curves = _arc(6, -9, 40, -math.pi / 2, math.pi / 2)
    quarter = _case(
        "faith_quarter", quarter_curves, lerp(quarter_curves[0].start, quarter_curves[-1].end, 0.5)
    )
    arch = collateral_cases()[2]
    planar_curve = CubicBezier(
        Vector3(-75, 0, 0), Vector3(-25, 0, 75), Vector3(25, 0, -75), Vector3(75, 0, 0)
    )
    planar = _case("faith_planar_s", (planar_curve,), Vector3(0, 0, 0))
    spatial = spatial_cases(5.0)[-2]
    first = _arc(0, 0, 40, -math.pi / 2, math.pi / 2)
    join = first[-1].end

    def skew(point: Vector3) -> Vector3:
        """
        Rotate only the second bend plane about its exact shared arrival tangent.
        """
        return join.translated(
            rotate(
                Vector3(point.x - join.x, point.y - join.y, point.z - join.z), Vector3(0, 0, 1), 60
            ),
            1,
        )

    second = tuple(
        CubicBezier(*(skew(p) for p in (c.start, c.control_a, c.control_b, c.end)))
        for c in _arc(0, 0, 40, 0, math.pi / 2)
    )
    return_curve = (*first, *second)
    skewed = _case("faith_skew_return", return_curve, lerp(first[0].start, second[-1].end, 0.5))
    end_tangent = unit(second[-1].derivative(1))
    skewed = replace(skewed, end_width=unit(cross(end_tangent, Vector3(0, 0, 1))))
    specifications = (
        (
            shallow,
            "faith_shallow_0",
            0.0,
            "Shallow bend and different endpoint positions; no prescribed roll.",
        ),
        (quarter, "faith_quarter_plus90", 90.0, "Quarter reversal with positive quarter-roll."),
        (
            arch,
            "faith_arch_minus90",
            -90.0,
            "Asymmetric arch and negative roll through variable curvature.",
        ),
        (
            planar,
            "faith_planar_s_plus180",
            180.0,
            "Planar inflection and half-turn with separated termini.",
        ),
        (
            spatial,
            "faith_spatial_s_minus180",
            -180.0,
            "Nonplanar inflection and negative half-turn with oblique caps.",
        ),
        (
            skewed,
            "faith_skew_return_minus360",
            -360.0,
            "Two joined perpendicular-skew bend planes and negative full winding.",
        ),
    )
    return tuple(
        FaithFixture(_rolled_case(parent, name, degrees), degrees, parent.name, purpose)
        for parent, name, degrees, purpose in specifications
    )
