"""
Bound the proposed outer-collar transverse Jacobian without certifying global material validity.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import derivative, elevate, multiply
from artifacts.verification.resume3217.metric import Polynomial, product

from .collared_transport import OUTER_CUBIC, OUTER_RADIAL_POSITION, OUTER_RADIAL_RATE
from .material_paths import combine
from .profile_transition import TransitionEdge
from .transition_certificate import certify as certify_boundary

Pair = tuple[Polynomial, Polynomial]


def dv(values: Polynomial) -> Polynomial:
    """
    Differentiate original edge-coordinate polynomials without resampling.
    """
    return tuple(derivative(row) for row in values)


def cross(a: Pair, b: Pair) -> Polynomial:
    """
    Keep signed transverse determinants exact in a common Bernstein basis.
    """
    return combine(product(a[0], b[1]), product(a[1], b[0]), Fraction(-1))


def derivative_numerator(points: Pair, weight: Polynomial) -> Pair:
    """
    Preserve the exact rational edge derivative numerator with its two-component shape.
    """
    return weighted_rate(points, weight, dv)


def weighted_rate(
    points: Pair, weight: Polynomial, differentiate: Callable[[Polynomial], Polynomial]
) -> Pair:
    """
    Apply one exact parameter derivative to a rational vector's homogeneous numerator.
    """
    weight_rate = differentiate(weight)
    return (
        combine(
            product(differentiate(points[0]), weight), product(points[0], weight_rate), Fraction(-1)
        ),
        combine(
            product(differentiate(points[1]), weight), product(points[1], weight_rate), Fraction(-1)
        ),
    )


@dataclass(frozen=True)
class SectionFields:
    """
    Share exact root/current homogeneous fields and edge derivatives across transport proofs.
    """

    root: Pair
    current: Pair
    root_weight: Polynomial
    weight: Polynomial
    root_rate: Pair
    current_rate: Pair
    root_velocity: Pair
    current_velocity: Pair


def prepare(section: TransitionEdge) -> SectionFields:
    """
    Extract unchanged stored coefficients once, without profile fitting or parameter normalization.
    """
    root = section.rows[0]
    r = ((tuple(p[0] for p in root),), (tuple(p[1] for p in root),))
    w0 = (tuple(p[2] for p in root),)
    p = (
        tuple(tuple(point[0] for point in row) for row in section.rows),
        tuple(tuple(point[1] for point in row) for row in section.rows),
    )
    w = tuple(tuple(point[2] for point in row) for row in section.rows)
    return SectionFields(
        r,
        p,
        w0,
        w,
        (dv(r[0]), dv(r[1])),
        (dv(p[0]), dv(p[1])),
        derivative_numerator(r, w0),
        derivative_numerator(p, w),
    )


@dataclass(frozen=True)
class TransportCertificate:
    """
    Retain the full outer-collar coefficient net and a sufficient Cartesian transverse Jacobian lower bound.
    """

    section: TransitionEdge
    status: str
    minimum_clockwise_numerator: Fraction
    cartesian_jacobian_lower: Fraction | None
    coefficients: tuple[Polynomial, ...]


def certify(section: TransitionEdge, checkpoint: Callable[[], None]) -> TransportCertificate:
    """
    Enclose all u,v and outer-collar tau, with s=1/4+3tau/4 and chi=tau³.

    T=sR+chi(P-R), so cross(T_s,T_v)=s*K00+chi*(K01-K00)
    +s*chi_s*(K10-K00)+chi*chi_s*(K11-K10-K01+K00), where
    Kij pairs each root/current point with the other root/current edge derivative.
    Positive common denominator w0²*w² gives a trivariate polynomial numerator.
    Strict clockwise coefficient signs certify positive determinant relative to
    the root Cartesian fan map. The center collar is exactly identity and requires
    no division by its vanishing polar-coordinate Jacobian. No subdivision or
    per-label physical tolerance is introduced. Seam metric continuity, numerical
    conditioning, global material injectivity and physical strain remain separate.
    """
    checkpoint()
    if certify_boundary(section, checkpoint).status != "certified":
        return TransportCertificate(section, "unresolved", Fraction(0), None, ())
    root = section.rows[0]
    fields = prepare(section)
    r, p, w0, w = fields.root, fields.current, fields.root_weight, fields.weight
    dr, dp, vr, vp = (
        fields.root_rate,
        fields.current_rate,
        fields.root_velocity,
        fields.current_velocity,
    )
    checkpoint()
    k00 = product(cross(r, dr), product(w, w))
    k01 = product(w0, cross(r, vp))
    k10 = product(w, cross(p, vr))
    k11 = product(product(w0, w0), cross(p, dp))
    terms = (
        k00,
        combine(k01, k00, Fraction(-1)),
        combine(k10, k00, Fraction(-1)),
        combine(combine(combine(k11, k10, Fraction(-1)), k01, Fraction(-1)), k00),
    )
    s = OUTER_RADIAL_POSITION
    chi = OUTER_CUBIC
    chi_s = OUTER_RADIAL_RATE
    scalars = tuple(
        elevate(values, 5) for values in (s, chi, multiply(s, chi_s), multiply(chi, chi_s))
    )
    coefficients = []
    for index in range(6):
        checkpoint()
        combined: Polynomial = ((Fraction(0),),)
        for scalar, term in zip(scalars, terms):
            combined = combine(
                combined, tuple(tuple(scalar[index] * x for x in row) for row in term)
            )
        coefficients.append(tuple(tuple(-x for x in row) for row in combined))
    minimum = min(x for values in coefficients for row in values for x in row)
    root_cross = cross(r, dr)
    root_upper = max(abs(x) for row in root_cross for x in row) / min(p[2] for p in root) ** 2
    denominator_upper = (
        max(p[2] for p in root) ** 2 * max(point[2] for row in section.rows for point in row) ** 2
    )
    lower = (
        min(Fraction(1), minimum / (denominator_upper * root_upper))
        if minimum > Fraction(0)
        else None
    )
    return TransportCertificate(
        section,
        "certified" if lower is not None else "unresolved",
        minimum,
        lower,
        tuple(coefficients),
    )
