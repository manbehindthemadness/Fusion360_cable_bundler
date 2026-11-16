"""
Bound full-profile flat/control and shared-cap correspondence without native or contact promotion.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import multiply
from artifacts.verification.resume3217.extraction import Net
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc

from .flat_chart import FlatChart, FlatRegion, MaterialCut
from .volume_boundary import boundary
from .volume_field import BendVolume


def controls(
    chart: FlatChart, cut: MaterialCut, arc: MaterialArc
) -> tuple[tuple[Fraction, ...], ...]:
    """
    Restrict the affine material chart at one original q-dependent longitudinal cut.
    """
    if len(arc.controls) != 3 or len(arc.weights) != 3 or any(w <= 0 for w in arc.weights):
        raise ValueError("An original positive-weight rational profile required")
    return tuple(
        chart.point(cut.at(Fraction(q)), Fraction(q), Fraction(b)) for q, b in arc.controls
    )


def outgoing_bound(chart: FlatChart, arc: MaterialArc, outgoing: Net) -> Fraction:
    """
    Enclose all original U/V flat positions from exact physical outgoing-control differences.

    Both surfaces have linear U, the same positive rational profile weights and
    affine q/b endpoint expressions. Positive-basis convexity therefore bounds
    their whole rectangle by the largest control L1 distance. This is an input
    representation bound, not a native image or complete material-flow proof.
    """
    if len(outgoing) != 2 or any(
        len(row) != 3 or any(len(p) != 3 or any(type(x) is not Fraction for x in p) for p in row)
        for row in outgoing
    ):
        raise ValueError("Complete exact linear-U outgoing flat controls required")
    expected = (controls(chart, chart.low, arc), controls(chart, chart.high, arc))
    return max(
        sum((abs(a - b) for a, b in zip(p, q)), Fraction(0))
        for row, actual in zip(expected, outgoing)
        for p, q in zip(row, actual)
    )


def bend_cap_bound(chart: FlatChart, arc: MaterialArc, checkpoint: Callable[[], None]) -> Fraction:
    """
    Compare unchanged q/b labels on the SAME bend/flat interface over the complete rational profile.

    World roundoff differences are measured to the dimensional policy; exact
    coefficient equality is not demanded. Corresponding labels remain discrete
    invariants. Adjacent piece interiors, tangent flow and curvature are not
    exempted or certified by this positional cap correspondence.
    """
    checkpoint()
    if not isinstance(chart.source, BendVolume) or chart.region is FlatRegion.STRAIGHT:
        raise ValueError("An original crease-side flat chart is required")
    start = chart.region is FlatRegion.BEFORE
    index = 0 if start else len(chart.source.source.spans) - 1
    net = boundary(chart.source.span(index), arc)[0 if start else -1]
    flat = controls(chart, chart.high if start else chart.low, arc)
    w = tuple(Fraction(x) for x in arc.weights)
    axes = tuple(multiply(tuple(p[k] * weight for p, weight in zip(flat, w)), w) for k in range(3))
    denominator = min(multiply(w, w))
    return (
        max(sum((abs(p[k] - axes[k][v]) for k in range(3)), Fraction(0)) for v, p in enumerate(net))
        / denominator
    )


def consecutive_cap_bound(left: FlatChart, right: FlatChart, arc: MaterialArc) -> Fraction:
    """
    Retain ordered profile labels between consecutive source pieces, measuring only their shared cap.

    The caller establishes original adjacency/source provenance. Position alone
    cannot certify that the two interiors avoid penetration or preserve flow.
    """
    first, last = controls(left, left.high, arc), controls(right, right.low, arc)
    return max(sum((abs(a - b) for a, b in zip(p, q)), Fraction(0)) for p, q in zip(first, last))
