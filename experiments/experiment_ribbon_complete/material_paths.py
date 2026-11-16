"""
Bound corresponding longitudinal path discrepancies over complete rational branch boundaries.

Full-boundary uniformity is a diagnostic stronger than the required mid-thickness
left/center/right equality. Through-thickness path differences can be physical.
This is not a transverse metric, interior map, curvature, contact or native certificate.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import elevate
from artifacts.verification.resume3217.metric import Polynomial, product

from .branch_plan import SpatialBranchPlan
from .branch_reference import validate_patches
from .curve_lengths import distance
from .spatial_frame import differentiated, restrict, split_at
from .spatial_transition import SpatialPatch, compose, derive


def combine(left: Polynomial, right: Polynomial, scale: Fraction = Fraction(1)) -> Polynomial:
    """
    Add exact rectangular tensors after elevating both axes to a common basis.
    """
    u, v = max(len(left), len(right)), max(len(left[0]), len(right[0]))

    def elevated(values: Polynomial) -> Polynomial:
        """
        Preserve a scalar polynomial under exact degree elevation on both axes.
        """
        rows = tuple(elevate(row, v - 1) for row in values)
        columns = tuple(elevate(tuple(row[j] for row in rows), u - 1) for j in range(v))
        return tuple(tuple(columns[j][i] for j in range(v)) for i in range(u))

    a, b = elevated(left), elevated(right)
    return tuple(tuple(a[i][j] + scale * b[i][j] for j in range(v)) for i in range(u))


def square_root_lower(value: Fraction) -> Fraction:
    """
    Bound a positive squared speed using fixed forty-bit dyadic arithmetic, not a physical gate.
    """
    scale = 1 << 40
    return Fraction(math.isqrt(value.numerator * scale**2 // value.denominator), scale)


@dataclass(frozen=True)
class SpanPathBound:
    """
    Retain a whole-span absolute speed-discrepancy integral upper bound for every edge coordinate.

    None means the reference speed denominator could not be bounded positive.
    The numerator range remains evidence, never a witnessed geometric violation.
    """

    patch: SpatialPatch
    residual_lower: Fraction
    residual_upper: Fraction
    discrepancy_upper_mm: Fraction | None
    edge_coordinate: Fraction | None


def enclose(
    patch: SpatialPatch,
    checkpoint: Callable[[], None],
    *,
    edge_coordinate: Fraction | None = None,
) -> SpanPathBound:
    """
    Bound integral abs(|X_t|-|C_t|) over the local span at every or one exact source edge v.

    For homogeneous X=H/w, A=H_t*w-H*w_t and R=A dot A-|C_t|²*w⁴.
    Rationalization gives abs(speed difference)=abs(R)/(w²*(|A|+w²*|C_t|)).
    Positive lower bounds on both speed numerators strengthen the denominator;
    an inconclusive |A| lower bound contributes zero and preserves the original
    reference-only enclosure. Each degree-n Bernstein basis is nonnegative and
    integrates to1/(n+1). This bounds the residual's absolute integral by the
    average of the per-row maximum absolute coefficients. Absolute values
    precede averaging, so local extension/compression cannot cancel. This covers
    every fixed transverse coordinate over the entire rectangle. Local derivatives
    integrate over one local unit interval, so no global-span scale is lost.
    No automatic subdivision or independent time/work allocation is introduced.
    An explicit edge coordinate restricts the same tensor exactly before measuring;
    omitting it measures stronger full-boundary uniformity as a diagnostic only.
    """
    checkpoint()
    if compose(patch.section, patch.frame, checkpoint).rows != patch.rows:
        raise ValueError("Material proof cannot transfer to changed world controls")
    net = patch.rows
    if edge_coordinate is not None:
        if type(edge_coordinate) is not Fraction or not Fraction(0) <= edge_coordinate <= Fraction(
            1
        ):
            raise ValueError("An exact unit source edge coordinate is required")
        net = tuple(
            (tuple(split_at(tuple(p[k] for p in row), edge_coordinate)[0][-1] for k in range(4)),)
            for row in net
        )
    weight = tuple(tuple(p[3] for p in row) for row in net)
    first = derive(net, 0)
    weight_first = tuple(tuple(p[3] for p in row) for row in first)
    squared: Polynomial = ((Fraction(0),),)
    for axis in range(3):
        checkpoint()
        position = tuple(tuple(p[axis] for p in row) for row in net)
        velocity = tuple(tuple(p[axis] for p in row) for row in first)
        numerator = combine(
            product(velocity, weight), product(position, weight_first), Fraction(-1)
        )
        squared = combine(squared, product(numerator, numerator))
    center_velocity = differentiated(patch.frame.fields()[0])
    reference: Polynomial = ((Fraction(0),),)
    for field in center_velocity:
        polynomial = tuple((x,) for x in field)
        reference = combine(reference, product(polynomial, polynomial))
    checkpoint()
    weight_squared = product(weight, weight)
    weight_fourth = product(weight_squared, weight_squared)
    residual = combine(squared, product(reference, weight_fourth), Fraction(-1))
    values = tuple(x for row in residual for x in row)
    lower, upper = min(values), max(values)
    minimum_speed_squared = min(x for row in reference for x in row)
    minimum_speed = (
        square_root_lower(minimum_speed_squared) if minimum_speed_squared > 0 else Fraction(0)
    )
    numerator_squared_lower = min(x for row in squared for x in row)
    numerator_speed_lower = (
        square_root_lower(numerator_squared_lower) if numerator_squared_lower > 0 else Fraction(0)
    )
    weight_lower_squared = min(x for row in weight for x in row) ** 2
    denominator_lower = weight_lower_squared * (
        numerator_speed_lower + weight_lower_squared * minimum_speed
    )
    residual_integral = sum(max(abs(value) for value in row) for row in residual) / len(residual)
    discrepancy = residual_integral / denominator_lower if minimum_speed > 0 else None
    checkpoint()
    return SpanPathBound(patch, lower, upper, discrepancy, edge_coordinate)


@dataclass(frozen=True)
class BoundaryPathCertificate:
    """
    Retain a diagnostic uniformity bound for any boundary pair on any corresponding interval.

    Center is the common comparison path. Twice the accumulated worst-edge error
    bounds every boundary pair, including paths on different source edges. This
    sufficient bound can be conservative and does not establish interior isometry.
    Unresolved full-boundary uniformity is not failure of the required midline rule.
    """

    status: str
    pairwise_upper_mm: Fraction | None
    spans: tuple[tuple[SpanPathBound, ...], ...]


def certify(
    patches: tuple[tuple[SpatialPatch, ...], ...], checkpoint: Callable[[], None]
) -> BoundaryPathCertificate:
    """
    Enclose all ordered spans under one caller checkpoint without per-station acceptance slack.

    The integral of absolute speed difference cannot hide cancellation. Thus the
    same accumulated bound covers complete paths and every corresponding local
    interval. Exact source span closure/order must already be validated by the
    branch assembler. Empty/mismatched edge coverage is refused, not skipped.
    """
    checkpoint()
    validate_patches(patches, checkpoint)
    proofs = tuple(tuple(enclose(patch, checkpoint) for patch in span) for span in patches)
    accumulated = Fraction(0)
    for span in proofs:
        bounds: list[Fraction] = []
        for proof in span:
            value = proof.discrepancy_upper_mm
            if value is None:
                return BoundaryPathCertificate("unresolved", None, proofs)
            bounds.append(value)
        accumulated += max(bounds)
    pairwise = 2 * accumulated
    return BoundaryPathCertificate(
        "certified" if pairwise <= Fraction(1, 100) else "unresolved", pairwise, proofs
    )


@dataclass(frozen=True)
class BranchPathAudit:
    """
    Bind the measurement to the same immutable branch plan without clearing other material checks.
    """

    plan: SpatialBranchPlan
    boundary_paths: BoundaryPathCertificate


def audit(plan: SpatialBranchPlan, checkpoint: Callable[[], None]) -> BranchPathAudit:
    """
    Measure actual proposed boundary geometry while preserving source, patch and outstanding-check identity.

    A certified longitudinal bound alone cannot clear material_metrics: transverse
    compatibility and a valid interior material map remain separately required.
    """
    return BranchPathAudit(plan, certify(plan.patches, checkpoint))


@dataclass(frozen=True)
class StretchWitness:
    """
    Retain a one-sided proven excess over the center path on a specified corresponding interval.

    A nonpositive/small lower bound is inconclusive, never a material pass.
    Source coordinates identify the original patch and local parameter interval.
    """

    patch: SpatialPatch
    low: Fraction
    high: Fraction
    edge_coordinate: Fraction
    excess_lower_mm: Fraction
    violation: bool


def witness(
    patch: SpatialPatch,
    low: Fraction,
    high: Fraction,
    edge_coordinate: Fraction,
    checkpoint: Callable[[], None],
) -> StretchWitness:
    """
    Compare an exact rational boundary chord with a polynomial center control-polygon upper length.

    Boundary arc length is at least its chord. Center arc length is at most its
    restricted polynomial control polygon. A difference above0.01mm therefore
    witnesses longitudinal incompatibility on this interval, even if full totals
    agree. Finite witnesses cannot certify absence of stretching elsewhere.
    """
    checkpoint()
    if (
        any(type(value) is not Fraction for value in (low, high, edge_coordinate))
        or not Fraction(0) <= low < high <= Fraction(1)
        or not Fraction(0) <= edge_coordinate <= Fraction(1)
    ):
        raise ValueError("Exact ordered local interval and source edge coordinate required")
    if compose(patch.section, patch.frame, checkpoint).rows != patch.rows:
        raise ValueError("Material witness cannot transfer to changed world controls")

    def point(parameter: Fraction) -> tuple[Fraction, ...]:
        """
        Evaluate the actual homogeneous tensor exactly before dividing by its positive weight.
        """
        values = tuple(
            split_at(
                tuple(
                    split_at(tuple(p[k] for p in row), edge_coordinate)[0][-1] for row in patch.rows
                ),
                parameter,
            )[0][-1]
            for k in range(4)
        )
        return tuple(values[k] / values[3] for k in range(3))

    boundary_lower = distance(point(low), point(high))[0]
    center = tuple(restrict(field, low, high) for field in patch.frame.fields()[0])
    controls = tuple(tuple(field[i] for field in center) for i in range(len(center[0])))
    center_upper = sum((distance(a, b)[1] for a, b in zip(controls, controls[1:])), Fraction(0))
    excess = boundary_lower - center_upper
    checkpoint()
    return StretchWitness(patch, low, high, edge_coordinate, excess, excess > Fraction(1, 100))
