"""
Certify positive denominators and boundary angular orientation over a complete profile transition.

This two-dimensional boundary certificate is not a three-dimensional material
Jacobian, native loft, curvature, strain or self-contact certificate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import Polynomial, add, derivative, multiply

from .profile_transition import TransitionEdge


@dataclass(frozen=True)
class TransitionCertificate:
    """
    Retain exact continuous bounds for the declared transverse boundary properties only.
    """

    status: str
    minimum_weight: Fraction
    minimum_clockwise_numerator: Fraction
    terminal_radius_error_mm: Fraction


def cross(left: tuple[Polynomial, Polynomial], right: tuple[Polynomial, Polynomial]) -> Polynomial:
    """
    Compute a two-dimensional polynomial determinant in a common Bernstein basis.
    """
    return add(multiply(left[0], right[1]), multiply(left[1], right[0]), Fraction(-1))


def certify(edge: TransitionEdge, checkpoint: Callable[[], None]) -> TransitionCertificate:
    """
    Enclose all blend fractions and edge parameters without sampling or automatic subdivision.

    Homogeneous interpolation is linear in blend fraction; the quintic endpoint
    schedule covers[0,1] monotonically. Angular determinant has three Bernstein
    rows in blend fraction. Strictly positive clockwise coefficients establish
    orientation over the whole rectangle. Mixed coefficients stay unresolved.
    Radius error encloses the actual stored terminal coefficients, including
    floating circle authoring, rather than assuming an exact conic identity.
    """
    checkpoint()
    root, end = edge.rows[0], edge.rows[-1]
    a = (tuple(p[0] for p in root), tuple(p[1] for p in root))
    b = (tuple(p[0] for p in end), tuple(p[1] for p in end))
    da, db = (derivative(a[0]), derivative(a[1])), (derivative(b[0]), derivative(b[1]))
    rows = (cross(a, da), tuple(x / 2 for x in add(cross(a, db), cross(b, da))), cross(b, db))
    minimum = min(-value for row in rows for value in row)
    weight = min(p[2] for row in edge.rows for p in row)
    w = tuple(p[2] for p in end)
    radius = Fraction(edge.terminal_radius_mm)
    residual = add(add(multiply(b[0], b[0]), multiply(b[1], b[1])), multiply(w, w), -(radius**2))
    error = max(abs(x) for x in residual) / (min(w) ** 2 * radius)
    checkpoint()
    status = (
        "certified" if weight > 0 and minimum > 0 and error <= Fraction(1, 100) else "unresolved"
    )
    return TransitionCertificate(status, weight, minimum, error)
