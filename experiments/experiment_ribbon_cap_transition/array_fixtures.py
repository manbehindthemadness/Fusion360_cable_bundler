"""
Author three distinct bend families for the approved four-width full-turn array.

The U-turn is a repeated development reference; S and perpendicular-plane bends
inherit existing centerlines with new full-turn boundary roll. No radius search,
shape solve, outcome-dependent repair or production change occurs here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from uuid import NAMESPACE_URL, uuid5

from cable_bundler.routing.geometry import Vector3, cross, unit
from experiments.experiment_ribbon_diagnosis.spatial import spatial_cases
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.end_boundary import EndBoundary

from .fixtures import certificate_limit_case
from .master_frames import master_scaffold
from .regression_cases import collateral_cases


@dataclass(frozen=True)
class ArrayFixture:
    """
    Preserve a complete configuration's parent and collateral-mechanics purpose.
    """

    case: RibbonStressCase
    parent_case: str
    purpose: str


def _full_turn_boundary(parent: RibbonStressCase, name: str) -> RibbonStressCase:
    """
    Author B width to match unrolled node transport BEFORE solving the ribbon.

    A single unchanged scaffold computes the signed correction to the parent's
    B width. Undo that correction to obtain transported B width, then freeze it.
    This is boundary authoring, not a full ribbon solve or adjusted native target.
    The native solver independently prescribes/measures the explicit full turn.
    """
    scaffold = master_scaffold(
        parent.route, parent.start_width, parent.end_width, parent.lines * parent.diameter_mm
    )
    angle = scaffold.bank_angles_radians[-1]
    target = unit(parent.end_width)
    side = cross(scaffold.frames[-1].tangent, target)
    transported = unit(
        Vector3(
            target.x * math.cos(angle) - side.x * math.sin(angle),
            target.y * math.cos(angle) - side.y * math.sin(angle),
            target.z * math.cos(angle) - side.z * math.sin(angle),
        )
    )
    return replace(
        parent,
        name=name,
        family=name,
        route=replace(parent.route, cable_id=uuid5(NAMESPACE_URL, name), cable_number=name),
        end_width=transported,
        end_boundary=EndBoundary(parent.end_boundary.center, 114.0),
    )


def array_fixtures() -> tuple[ArrayFixture, ...]:
    """
    Freeze one repeated tight reference and two new roll variants without tuning.

    Radius comes from the retained 24-check authoring report, not a new search.
    Two scaffold-only B-roll authoring calls are not complete-ribbon solves.
    Each case retains 19x1.5 mm conductors, a 114 mm sphere and short split targets.
    """
    u_turn = certificate_limit_case(18.16887617111206)
    spatial = spatial_cases(4.0)[-2]
    compound = collateral_cases()[1]
    return (
        ArrayFixture(
            u_turn, "sphere4_reversal180_twist360_gap40", "Repeated tight full-turn reference."
        ),
        ArrayFixture(
            _full_turn_boundary(spatial, "array4_spatial_s_twist360"),
            spatial.name,
            "Nonplanar S curvature and inflection with full winding and complete endings.",
        ),
        ArrayFixture(
            _full_turn_boundary(compound, "array4_orthogonal_bends_twist360"),
            compound.name,
            "Width/thickness transport through perpendicular bend planes and their join.",
        ),
    )
