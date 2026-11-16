"""
Bound the collared transport derivative in source Cartesian coordinates, including the longitudinal coupling.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import elevate, multiply
from artifacts.verification.resume3217.metric import Polynomial, product

from .collared_transport import OUTER_CUBIC, OUTER_RADIAL_POSITION, OUTER_RADIAL_RATE
from .material_paths import combine
from .profile_transition import TransitionEdge
from .ruled_support import square_root_upper
from .transport_certificate import cross, prepare, weighted_rate

Matrix = tuple[tuple[Fraction, Fraction], tuple[Fraction, Fraction]]


def du(values: Polynomial) -> Polynomial:
    """
    Differentiate global branch-phase coefficients, preserving the constant case.
    """
    degree = len(values) - 1
    return tuple(
        tuple(degree * (b - a) for a, b in zip(first, second))
        for first, second in zip(values, values[1:])
    ) or (tuple(Fraction(0) for _ in values[0]),)


def scale(values: Polynomial, factor: Fraction) -> Polynomial:
    """
    Preserve a tensor basis under multiplication by an exact scalar.
    """
    return tuple(tuple(factor * x for x in row) for row in values)


@dataclass(frozen=True)
class TransportRegularity:
    """
    Retain coefficient-ratio matrices and quantitative sufficient derivative bounds.
    """

    section: TransitionEdge
    status: str
    minimum_monotonicity: Fraction | None
    derivative_frobenius_squared_upper: Fraction | None
    longitudinal_rate_squared_upper: Fraction | None
    source_condition_upper: Fraction | None
    coefficient_shape: tuple[int, int, int]
    coefficient_ratios: tuple[Matrix, ...]


def certify(section: TransitionEdge, checkpoint: Callable[[], None]) -> TransportRegularity:
    """
    Bound Cartesian D_x0 T on the outer collar by positive rational coefficient ratios.

    With r/w0=R,p/w=P,k=cross(r,r_v)<0, d=p*w0-r*w and
    e=velocityP*w0²-velocityR*w², the positive common denominator is
    D=-s*w²*w0*k. Derivative numerator is D*I-s*chi_s*w*d*row(vR)
    -chi*e*row(r), where row(vR)=(vRb,-vRq), row(r)=(-rb,rq).
    Numerator/denominator share a Bernstein basis with positive denominator
    coefficients, so the actual matrix is a convex combination of exact ratio
    matrices. Positive symmetric parts supply a uniform monotonicity lower bound.
    Source u uses the same fixed1mm coordinate convention as the world chart.
    The inner collar is identity; no polar denominator is evaluated at the center.
    """
    checkpoint()
    f = prepare(section)
    r, p, w0, w = f.root, f.current, f.root_weight, f.weight
    wr2 = product(w0, w0)
    w2 = product(w, w)
    k = cross(r, f.root_rate)
    base = scale(product(product(w2, w0), k), Fraction(-1))
    delta = (
        combine(product(p[0], w0), product(r[0], w), Fraction(-1)),
        combine(product(p[1], w0), product(r[1], w), Fraction(-1)),
    )
    delta_rate = (
        combine(product(f.current_velocity[0], wr2), product(f.root_velocity[0], w2), Fraction(-1)),
        combine(product(f.current_velocity[1], wr2), product(f.root_velocity[1], w2), Fraction(-1)),
    )
    radial = (f.root_velocity[1], scale(f.root_velocity[0], Fraction(-1)))
    angular = (scale(r[1], Fraction(-1)), r[0])
    first = tuple(
        tuple(product(w, product(delta[i], radial[j])) for j in range(2)) for i in range(2)
    )
    second = tuple(tuple(product(delta_rate[i], angular[j]) for j in range(2)) for i in range(2))
    s = elevate(OUTER_RADIAL_POSITION, 3)
    sh = elevate(multiply(OUTER_RADIAL_POSITION, OUTER_RADIAL_RATE), 3)
    chi = OUTER_CUBIC
    ratios = []
    minimum = Fraction(1)
    norm2 = Fraction(2)
    shape = (4, len(base), len(base[0]))
    for index in range(4):
        checkpoint()
        den = scale(base, s[index])
        matrices = tuple(
            tuple(
                combine(
                    combine(
                        scale(base, s[index] if i == j else Fraction(0)), first[i][j], -sh[index]
                    ),
                    second[i][j],
                    -chi[index],
                )
                for j in range(2)
            )
            for i in range(2)
        )
        for u in range(shape[1]):
            for v in range(shape[2]):
                d = den[u][v]
                if d <= Fraction(0):
                    return TransportRegularity(
                        section, "unresolved", None, None, None, None, shape, tuple(ratios)
                    )
                matrix: Matrix = (
                    (matrices[0][0][u][v] / d, matrices[0][1][u][v] / d),
                    (matrices[1][0][u][v] / d, matrices[1][1][u][v] / d),
                )
                ratios.append(matrix)
                a, c = matrix[0][0], matrix[1][1]
                b = (matrix[0][1] + matrix[1][0]) / Fraction(2)
                determinant = a * c - b * b
                if a <= Fraction(0) or c <= Fraction(0) or determinant <= Fraction(0):
                    return TransportRegularity(
                        section, "unresolved", None, None, None, None, shape, tuple(ratios)
                    )
                lower = max(min(a - abs(b), c - abs(b)), determinant / (a + c))
                minimum = min(minimum, lower)
                norm2 = max(norm2, sum((x * x for row in matrix for x in row), Fraction(0)))
    checkpoint()
    phase = weighted_rate(p, w, du)
    aligned = tuple(combine(value, w2, Fraction(0)) for value in phase)
    rate2 = max(
        sum(((aligned[k][u][v] / w2[u][v]) ** 2 for k in range(2)), Fraction(0))
        for u in range(len(w2))
        for v in range(len(w2[0]))
    )
    condition = square_root_upper((1 + rate2 + norm2) * (1 + (2 + rate2) / minimum**2))
    return TransportRegularity(
        section,
        "certified" if condition <= 1024 else "unresolved",
        minimum,
        norm2,
        rate2,
        condition,
        shape,
        tuple(ratios),
    )
