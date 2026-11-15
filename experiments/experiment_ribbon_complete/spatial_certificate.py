"""
Enclose the signed ambient coordinate Jacobian of a framed section transition.

This is local chart regularity, not global injectivity, isometry, contact or
native acceptance. Frame normalization is never substituted for measurement.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import Polynomial, add, multiply

from .spatial_frame import Components, differentiated
from .spatial_transition import SpatialPatch, compose
from .transition_certificate import certify as certify_section


def cross(a: Components, b: Components) -> Components:
    """
    Form the raw frame normal polynomial without normalizing away singularity or scale.
    """
    return (
        add(multiply(a[1], b[2]), multiply(a[2], b[1]), Fraction(-1)),
        add(multiply(a[2], b[0]), multiply(a[0], b[2]), Fraction(-1)),
        add(multiply(a[0], b[1]), multiply(a[1], b[0]), Fraction(-1)),
    )


def dot(a: Components, b: Components) -> Polynomial:
    """
    Retain the exact determinant contribution of two vector fields.
    """
    return add(add(multiply(a[0], b[0]), multiply(a[1], b[1])), multiply(a[2], b[2]))


@dataclass(frozen=True)
class CoordinateCertificate:
    """
    Separate a sufficient local coordinate bound from all outstanding physical checks.
    """

    status: str
    minimum_signed_jacobian: Fraction
    q_bounds: tuple[Fraction, Fraction]
    b_bounds: tuple[Fraction, Fraction]
    section_status: str


def certify(patch: SpatialPatch, checkpoint: Callable[[], None]) -> CoordinateCertificate:
    """
    Bound(C'+qW'+bN') dot(W cross N) over the complete span and section envelope.

    Positive rational section weights enclose q/b by their Euclidean control
    ratios. The determinant is affine in q/b, so four rectangle corners and exact
    Bernstein convexity suffice. The root's prescribed orientation is retained;
    negative or mixed lower bounds stay unresolved, never automatically mirrored.
    """
    checkpoint()
    expected = compose(patch.section, patch.frame, checkpoint)
    if expected.rows != patch.rows or expected.section_rows != patch.section_rows:
        raise ValueError("Coordinate proof cannot transfer to changed spatial control geometry")
    section = certify_section(patch.section, checkpoint)
    q_values = tuple(p[0] / p[2] for row in patch.section_rows for p in row)
    b_values = tuple(p[1] / p[2] for row in patch.section_rows for p in row)
    q_bounds, b_bounds = (min(q_values), max(q_values)), (min(b_values), max(b_values))
    center, width, thickness = patch.frame.fields()
    normal = cross(width, thickness)
    base, q_term, b_term = (
        dot(differentiated(center), normal),
        dot(differentiated(width), normal),
        dot(differentiated(thickness), normal),
    )
    values = []
    for q in q_bounds:
        for b in b_bounds:
            checkpoint()
            polynomial = add(add(base, q_term, q), b_term, b)
            values.extend(
                patch.frame.orientation.value * x / (patch.frame.high - patch.frame.low)
                for x in polynomial
            )
    minimum = min(values)
    status = "certified" if minimum > 0 and section.status == "certified" else "unresolved"
    return CoordinateCertificate(status, minimum, q_bounds, b_bounds, section.status)
