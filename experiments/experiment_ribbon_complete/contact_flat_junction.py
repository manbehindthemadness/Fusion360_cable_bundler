"""
Bound unresolved overlap collars between two affine material caps without accepting contact.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .flat_chart import FlatChart
from .global_chart import cross
from .volume_field import Point


@dataclass(frozen=True)
class FlatCapCollar:
    """
    Keep both original charts and the remaining cap-collar uncertainty explicit.

    The caller establishes actual route adjacency and conductor ownership. This
    receipt binds first.high to second.low on identical q/b labels, but does not
    sew native caps, accept collar contact or establish junction flow.
    """

    first: FlatChart
    second: FlatChart
    cap_position_upper_mm: Fraction
    projection_rates: tuple[Fraction, Fraction]
    collars_mm: tuple[Fraction, Fraction] | None
    status: str
    half_mm: Fraction
    half_thickness_mm: Fraction


def certify_flat_cap(
    first: FlatChart,
    second: FlatChart,
    half_mm: Fraction,
    half_thickness_mm: Fraction,
    checkpoint: Callable[[], None],
) -> FlatCapCollar:
    """
    Confine any coincident points to both original affine material cap collars.

    Exact corner bounds enclose the complete q/b cap rectangle and hence every
    contained filled profile. A reciprocal first-cap axis removes its transverse
    variation. Positive longitudinal rates and the second cap's projection
    offsets bound both distances. The inclusive0.01mm rule qualifies only these
    dimensional bounds; remaining collar contact and valid native gluing stay open.
    """
    checkpoint()
    if any(type(x) is not Fraction or x <= 0 for x in (half_mm, half_thickness_mm)):
        raise ValueError("Explicit exact positive physical section bounds required")
    along, transverse, thickness = first.columns
    cap_q = tuple(q + a * first.high.slope for q, a in zip(transverse, along))
    axis = cross((cap_q[0], cap_q[1], cap_q[2]), (thickness[0], thickness[1], thickness[2]))
    first_rate = sum((a * b for a, b in zip(axis, along)), Fraction(0))
    if first_rate < 0:
        axis, first_rate = tuple(-x for x in axis), -first_rate
    second_rate = sum((a * b for a, b in zip(axis, second.columns[0])), Fraction(0))
    offsets = []
    cap_error = Fraction(0)
    for q in (-half_mm, half_mm):
        for b in (-half_thickness_mm, half_thickness_mm):
            checkpoint()
            left = first.point(first.high.at(q), q, b)
            right = second.point(second.low.at(q), q, b)
            delta: Point = tuple(z - a for a, z in zip(left, right))
            cap_error = max(cap_error, sum(map(abs, delta), Fraction(0)))
            offsets.append(sum((a * b for a, b in zip(axis, delta)), Fraction(0)))
    rates = first_rate, second_rate
    if min(rates) <= 0:
        return FlatCapCollar(
            first,
            second,
            cap_error,
            rates,
            None,
            "unresolved_flat_cap_progress",
            half_mm,
            half_thickness_mm,
        )
    if cap_error > Fraction(1, 100):
        return FlatCapCollar(
            first,
            second,
            cap_error,
            rates,
            None,
            "unresolved_cap_correspondence",
            half_mm,
            half_thickness_mm,
        )
    overlap = max(Fraction(0), -min(offsets))
    collars = overlap / first_rate, overlap / second_rate
    status = (
        "certified_material_cap_collar"
        if max(collars) <= Fraction(1, 100)
        else "unresolved_material_cap_collar"
    )
    return FlatCapCollar(
        first, second, cap_error, rates, collars, status, half_mm, half_thickness_mm
    )
