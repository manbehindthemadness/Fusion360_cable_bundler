"""
Enclose actual ending-side increment discrepancies without assuming a zero trunk contribution.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction
from typing import TypedDict

from artifacts.verification.resume3204.polynomial import multiply

from .branch_plan import SpatialBranchPlan
from .ending_pair import bound as pair_bound
from .ending_pair import derivative_data, frame_metrics
from .execution import RibbonPlan
from .material_paths import square_root_lower
from .material_traces import traces
from .spatial_transition import SpatialPatch
from .topology import terminal_chains


class EndingReport(TypedDict):
    """
    Report ending-only scope without granting complete-ribbon material acceptance.
    """

    scope: str
    upper_mm: str | None
    within_allowance: bool


def bound(
    patch: SpatialPatch, coordinate: Fraction, checkpoint: Callable[[], None]
) -> Fraction | None:
    """
    Bound the absolute speed discrepancy of a monotone midplane trace on fixed width axes.

    For X=C+W*q and constant W, the speed-square residual is
    2*q'*dot(C',W)+q'^2*|W|². Both supported timing polynomials are monotone:
    quintic beta'=30*u²*(1-u)²; septic beta'=105*u²*(1-u)²*
    (1-10*u*(1-u)/3), whose last factor is at least1/6. Thus integral|q'|
    equals its endpoint change. Integrating q'^2 exactly avoids cancellation
    losses in a coefficient absolute-value bound. Frame roundoff contributes
    explicitly through the cross term; axes are never normalized or projected.

    Actual axis motion is bounded as a separate additive derivative remainder;
    it is never projected away. Rational trace derivatives retain their exact
    homogeneous numerator and a positive weight lower bound. Unresolved positive
    speed bounds return no certificate. This certifies endings only.
    """
    checkpoint()
    data = derivative_data(patch, coordinate, checkpoint)
    if data is None:
        return None
    q = data.positions
    derivative_numerator = data.numerator
    weight_min = min(data.weights)
    derivative_bound = max(abs(value) for value in derivative_numerator) / weight_min**2
    reference_squared, cross_bound, width_squared = frame_metrics(patch)
    boundary_squared = reference_squared - 2 * derivative_bound * cross_bound
    if min(reference_squared, boundary_squared) <= 0:
        return None
    denominator = square_root_lower(reference_squared) + square_root_lower(boundary_squared)
    if denominator <= 0:
        return None
    square = multiply(derivative_numerator, derivative_numerator)
    energy = sum(square) / len(square) / weight_min**4
    checkpoint()
    return (
        2 * cross_bound * abs(q[-1] - q[0]) + width_squared * energy
    ) / denominator + data.remainder


def branch_bound(branch: SpatialBranchPlan, checkpoint: Callable[[], None]) -> Fraction | None:
    """
    Bound all three pairwise increments over every original span without signed cancellation.

    Keep both center-relative bounds and the tighter of the direct side comparison
    and its triangle enclosure. Sum each span's worst comparison once; no allowance
    is assigned to an individual span and no opposite distortions are canceled.
    """
    sides = traces(tuple(patch.section for patch in branch.patches[0]))
    result = Fraction(0)
    for span in branch.patches:
        values: list[Fraction] = []
        for trace in sides:
            value = bound(span[trace.edge_index], trace.coordinate, checkpoint)
            if value is None:
                return None
            values.append(value)
        left, right = sides
        direct = pair_bound(
            span[left.edge_index],
            left.coordinate,
            span[right.edge_index],
            right.coordinate,
            checkpoint,
        )
        triangle = sum(values, Fraction(0))
        comparison = triangle if direct is None else min(triangle, direct)
        result += max([*values, comparison])
    return result


def audit(plan: RibbonPlan, checkpoint: Callable[[], None]) -> EndingReport:
    """
    Sum actual serial ending bounds over both ends once, with siblings as alternatives.

    No trunk, native/junction, transverse/interior, contact or curvature gate is
    cleared. Missing complete geometry cannot receive a partial certificate.
    """
    checkpoint()
    if plan.trunk.route is None or plan.unattempted_route_ids:
        return {"scope": "endings only", "upper_mm": None, "within_allowance": False}
    values = {}
    for branch in plan.branches:
        value = branch_bound(branch, checkpoint)
        if value is None:
            return {"scope": "endings only", "upper_mm": None, "within_allowance": False}
        values[branch.source.source.leg.route_id] = value
    chains = terminal_chains(plan.captured.branches, checkpoint)
    upper = Fraction(0)
    for conductor in plan.captured.conductors:
        total = Fraction(0)
        for connection in plan.captured.group.connection_ids:
            choices = [
                sum((values[b.source.leg.route_id] for b in chain), Fraction(0))
                for chain in chains
                if chain[0].conductor == conductor
                and chain[0].source.leg.start_connection_id == connection
            ]
            if not choices:
                raise ValueError("Complete ending certificate needs both terminal chains")
            total += max(choices)
        upper = max(upper, total)
    return {
        "scope": "both ending chains only; trunk and native correspondence unqualified",
        "upper_mm": str(upper),
        "within_allowance": upper <= Fraction(1, 100),
    }
