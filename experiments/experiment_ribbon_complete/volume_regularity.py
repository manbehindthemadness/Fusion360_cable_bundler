"""
Bound local material-coordinate Jacobians of the same measured-midplane volume extension.

Strict positivity and conditioning are coordinate-validity requirements. Neither
local regularity nor boundary proximity proves global injectivity or contact.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import derivative
from artifacts.verification.resume3217.metric import Polynomial, product

from .material_paths import combine
from .volume_boundary import VolumeSpan

Field = tuple[Polynomial, ...]


def cross(first: Field, second: Field) -> Field:
    """
    Retain exact polynomial cross-product cancellations before taking any magnitude bound.
    """
    return tuple(
        combine(
            product(first[(axis + 1) % 3], second[(axis + 2) % 3]),
            product(first[(axis + 2) % 3], second[(axis + 1) % 3]),
            Fraction(-1),
        )
        for axis in range(3)
    )


def determinant(first: Field, second: Field, third: Field) -> Polynomial:
    """
    Form the exact scalar triple product without sampling or a sign assumption.
    """
    result = ((Fraction(0),),)
    cofactors = cross(second, third)
    for field, cofactor in zip(first, cofactors):
        result = combine(result, product(field, cofactor))
    return result


def norm_bound(rows: tuple[Field, ...]) -> Fraction:
    """
    Enclose a three-by-three polynomial matrix's infinity norm over its whole rectangle.
    """
    return max(
        sum(
            (max(abs(x) for coefficients in entry for x in coefficients) for entry in row),
            Fraction(0),
        )
        for row in rows
    )


def coupled_condition(
    matrix_norms: tuple[Fraction, ...],
    adjugate_norms: tuple[Fraction, ...],
    determinant_lowers: tuple[Fraction, ...],
) -> Fraction:
    """
    Retain the same thickness coordinate when bounding two convex norms over a positive affine determinant.

    Endpoint norms bound each affine matrix/cofactor norm by interpolation.
    Their product has quadratic Bernstein coefficients. Elevating the positive
    affine denominator to degree2 makes the rational value a convex combination
    of three coefficient ratios. This avoids combining an outer-thickness
    matrix maximum with an inner-thickness inverse maximum; no subdivisions,
    changed coordinate domain or extra work allocation are introduced.
    """
    pairs = (matrix_norms, adjugate_norms, determinant_lowers)
    if (
        any(len(pair) != 2 or any(type(x) is not Fraction for x in pair) for pair in pairs)
        or min(matrix_norms + adjugate_norms) < 0
        or min(determinant_lowers) <= 0
    ):
        raise ValueError(
            "Two exact nonnegative endpoint norms and positive determinant lowers required"
        )
    a, b = matrix_norms
    c, d = adjugate_norms
    low, high = determinant_lowers
    return max(a * c / low, (a * d + b * c) / (low + high), b * d / high)


@dataclass(frozen=True)
class LocalVolumeBound:
    """
    Retain same-source strict Jacobian and conservative infinity-norm conditioning bounds.
    """

    volume: VolumeSpan
    half_thickness_mm: Fraction
    determinant_lower: Fraction
    determinant_upper: Fraction
    condition_upper: Fraction | None
    status: str


def enclose(
    volume: VolumeSpan,
    half_thickness_mm: Fraction,
    radius_mm: Fraction,
    cosine: Fraction,
    sine: Fraction,
    checkpoint: Callable[[], None],
) -> LocalVolumeBound:
    """
    Enclose the complete original phase/q/thickness box in physical material coordinates.

    For P=A_phi+b*N_phi, Q=A_q, derivatives are J_s=c*P/R,
    J_q=Q+s*P/R and J_b=N. The material determinant is c/R*det(P,Q,N),
    affine in b. Its extrema are bounded by Bernstein ranges at both thickness
    endpoints. Matrix entries and cofactor rows are affine in b too: the shared
    P cancels the quadratic term in J_s cross J_q. Exact cross-product
    polynomials retain cancellations before their Bernstein magnitudes bound
    ||J||inf*||J^-1||inf at the SAME thickness coordinate through a positive
    rational Bernstein enclosure. The fixed1024
    condition requirement is numerical robustness, not a distance tolerance.
    Negative/inconclusive Bernstein bounds remain unresolved; no positive floor,
    subdivision, hidden work allocation or global material-map claim is added.
    """
    checkpoint()
    if (
        any(type(x) is not Fraction for x in (half_thickness_mm, radius_mm, cosine, sine))
        or min(half_thickness_mm, radius_mm, cosine) <= 0
    ):
        raise ValueError("Exact positive thickness/radius/cosine and exact sine required")
    source = volume.source
    low, high = source.surface.basis.breaks[volume.index : volume.index + 2]
    width = high - low
    net = source.spans[volume.index]
    along = tuple(
        tuple(
            tuple(5 * (net[i + 1][j][k] - net[i][j][k]) / width for j in range(3)) for i in range(5)
        )
        for k in range(3)
    )
    across = tuple(
        tuple(tuple((row[j + 1][k] - row[j][k]) / source.half_mm for j in range(2)) for row in net)
        for k in range(3)
    )
    normal = tuple(tuple((p[k],) for p in volume.normal) for k in range(3))
    normal_first = tuple(
        tuple((Fraction(value, width),) for value in derivative(tuple(p[k] for p in volume.normal)))
        for k in range(3)
    )
    ranges = []
    matrices = []
    for b in (-half_thickness_mm, half_thickness_mm):
        checkpoint()
        p = tuple(combine(a, n, b) for a, n in zip(along, normal_first))
        det = determinant(p, across, normal)
        values = tuple(x * cosine / radius_mm for row in det for x in row)
        ranges.append((min(values), max(values)))
        first = tuple(
            tuple(tuple(x * cosine / radius_mm for x in row) for row in field) for field in p
        )
        second = tuple(combine(q, field, sine / radius_mm) for q, field in zip(across, p))
        matrices.append((first, second, normal))
    lower, upper = min(x[0] for x in ranges), max(x[1] for x in ranges)
    condition = None
    if lower > 0:
        cofactor_endpoints = tuple(
            tuple(cross(matrix[(i + 1) % 3], matrix[(i + 2) % 3]) for i in range(3))
            for matrix in matrices
        )
        norms = tuple(
            norm_bound(tuple(tuple(matrix[j][i] for j in range(3)) for i in range(3)))
            for matrix in matrices
        )
        adjugate_norms = tuple(norm_bound(rows) for rows in cofactor_endpoints)
        condition = coupled_condition(norms, adjugate_norms, tuple(value[0] for value in ranges))
    return LocalVolumeBound(
        volume,
        half_thickness_mm,
        lower,
        upper,
        condition,
        "certified_local_jacobian_and_conditioning"
        if condition is not None and condition <= 1024
        else "unresolved",
    )
