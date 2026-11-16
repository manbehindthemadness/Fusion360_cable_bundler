"""
Carry persistent root fan labels through the unchanged boundary morph with an identity center collar.

This is a proposed piecewise material transport, not certified isometry, global
material regularity, fan-interface metric continuity, contact or native compliance.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from uuid import UUID

from artifacts.verification.resume3204.polynomial import derivative

from .branch_plan import SpatialBranchPlan
from .branch_reference import validate_patches
from .contracts import ConductorKey
from .profile_transition import Row, TransitionEdge
from .spatial_frame import split_at
from .spatial_transition import compose

Pair = tuple[Fraction, Fraction]
Triple = tuple[Fraction, Fraction, Fraction]
INNER_FRACTION = Fraction(1, 4)
OUTER_CUBIC = (Fraction(0), Fraction(0), Fraction(0), Fraction(1))
OUTER_RADIAL_POSITION = (INNER_FRACTION, Fraction(1))
OUTER_RADIAL_RATE = tuple(value / (1 - INNER_FRACTION) for value in derivative(OUTER_CUBIC))


def evaluate(values: tuple[Fraction, ...], parameter: Fraction) -> Fraction:
    """
    Evaluate exact original Bernstein controls without floating conversion.
    """
    return split_at(values, parameter)[0][-1]


def boundary(section: TransitionEdge, u: Fraction, v: Fraction) -> Pair:
    """
    Evaluate the same frozen rational section boundary used by spatial authoring.
    """
    values = tuple(
        evaluate(tuple(evaluate(tuple(p[k] for p in row), v) for row in section.rows), u)
        for k in range(3)
    )
    return values[0] / values[2], values[1] / values[2]


def collar(s: Fraction) -> Fraction:
    """
    Keep the inner source quarter exactly fixed and join the outer cubic with zero first/second collar jets.
    """
    return (
        Fraction(0)
        if s <= INNER_FRACTION
        else evaluate(OUTER_CUBIC, (s - INNER_FRACTION) / (1 - INNER_FRACTION))
    )


@dataclass(frozen=True)
class RootReference:
    """
    Preserve conductor, route, attachment, root edge order and exact local root geometry.
    """

    conductor: ConductorKey
    route_id: UUID
    attachment_id: UUID
    root_attachment_id: UUID
    parent_attachment_id: UUID | None
    association_ids: tuple[UUID, ...]
    edge_labels: tuple[str, ...]
    root_rows: tuple[Row, ...]


def reference(plan: SpatialBranchPlan) -> RootReference:
    """
    Bind labels to original root material data while permitting explicit changes to spatial fields.
    """
    sections = tuple(p.section for p in plan.patches[0])
    return RootReference(
        plan.source.conductor,
        plan.source.source.leg.route_id,
        plan.source.attachment.attachment_id,
        plan.source.root_attachment_id,
        plan.source.attachment.parent_attachment_id,
        plan.source.association_ids,
        tuple(s.source.geometry.label for s in sections),
        tuple(s.rows[0] for s in sections),
    )


@dataclass(frozen=True)
class MaterialLabel:
    """
    Retain a root-chart point; common fan seams and the center use canonical representatives.
    """

    source: RootReference
    edge_index: int
    edge_coordinate: Fraction
    radial_fraction: Fraction


def label(plan: SpatialBranchPlan, edge: int, v: Fraction, s: Fraction) -> MaterialLabel:
    """
    Canonicalize shared edge endpoints and the center without changing their root physical points.
    """
    source = reference(plan)
    if (
        type(edge) is not int
        or not 0 <= edge < len(source.root_rows)
        or any(type(x) is not Fraction or not Fraction(0) <= x <= Fraction(1) for x in (v, s))
    ):
        raise ValueError("A valid original edge and exact unit material coordinates are required")
    if s == Fraction(0):
        edge, v = 0, Fraction(0)
    elif v == Fraction(1):
        edge, v = (edge + 1) % len(source.root_rows), Fraction(0)
    return MaterialLabel(source, edge, v, s)


def transverse(plan: SpatialBranchPlan, point: MaterialLabel, u: Fraction) -> Pair:
    """
    Evaluate T=s*R+chi(s)*(P(u)-R), preserving the exact root, collar and inherited boundary.

    Source Cartesian position is x0=s*R(v), not a polar chart asserted regular
    at its center. The whole inner quarter is the identity in x0; source fan
    seams outside that collar remain piecewise and need their own metric checks.
    """
    if point.source != reference(plan):
        raise ValueError("Material label differs from the original root identity or geometry")
    if type(u) is not Fraction or not Fraction(0) <= u <= Fraction(1):
        raise ValueError("An exact unit global branch coordinate is required")
    canonical = label(plan, point.edge_index, point.edge_coordinate, point.radial_fraction)
    if canonical != point:
        raise ValueError("Material label is not the canonical source representative")
    section = plan.patches[0][point.edge_index].section
    root = boundary(section, Fraction(0), point.edge_coordinate)
    current = boundary(section, u, point.edge_coordinate)
    s = point.radial_fraction
    weight = collar(s)
    return s * root[0] + weight * (current[0] - root[0]), s * root[1] + weight * (
        current[1] - root[1]
    )


def world(
    plan: SpatialBranchPlan, point: MaterialLabel, u: Fraction, checkpoint: Callable[[], None]
) -> Triple:
    """
    Compose the proposed transport with unchanged spatial fields, without claiming qualified material coordinates.
    """
    checkpoint()
    validate_patches(plan.patches, checkpoint)
    q, b = transverse(plan, point, u)
    frame = next(
        span[0].frame for span in plan.patches if span[0].frame.low <= u <= span[0].frame.high
    )
    span = next(values for values in plan.patches if values[0].frame is frame)
    for patch in span:
        expected = compose(patch.section, frame, checkpoint)
        if expected.rows != patch.rows or expected.section_rows != patch.section_rows:
            raise ValueError(
                "Material coordinates cannot transfer to changed world control geometry"
            )
    t = (u - frame.low) / (frame.high - frame.low)
    center, width, normal = frame.fields()
    values = tuple(
        evaluate(center[k], t) + q * evaluate(width[k], t) + b * evaluate(normal[k], t)
        for k in range(3)
    )
    checkpoint()
    return values[0], values[1], values[2]
