"""
Prove global injectivity of original physical-label projections of rational native surface rectangles.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import derivative, split
from artifacts.verification.resume3217.metric import Polynomial, product

from .flat_cut_domain import FlatCutFrame
from .material_paths import combine
from .native_material_chart import NativeSurfaceSnapshot
from .spatial_frame import split_at

Pair = tuple[Fraction, Fraction]
Matrix = tuple[Pair, Pair]


def label_numerators(surface: NativeSurfaceSnapshot, frame: FlatCutFrame) -> tuple[Polynomial, ...]:
    """
    Pull physical s/q/b through the original affine inverse over the SAME positive tensor denominator.
    """
    inverse = frame.inverse.rows
    assert inverse is not None
    return tuple(
        tuple(
            tuple(
                sum((a * (x - o) for a, x, o in zip(row, p, frame.origin)), Fraction(0)) * w
                for p, w in zip(points, weights)
            )
            for points, weights in zip(surface.rows, surface.weights)
        )
        for row in inverse
    )


def _du(values: Polynomial) -> Polynomial:
    """
    Differentiate in the normalized original U span without changing its surface image.
    """
    degree = len(values) - 1
    return tuple(
        tuple(degree * (b - a) for a, b in zip(first, second))
        for first, second in zip(values, values[1:])
    )


def _dv(values: Polynomial) -> Polynomial:
    """
    Differentiate in the normalized original V span without assigning physical units to native UV.
    """
    return tuple(derivative(row) for row in values)


def _center(values: Polynomial) -> Fraction:
    """
    Evaluate a complete tensor exactly at the precommitted proof-domain center.
    """
    along = tuple(split_at(row, Fraction(1, 2))[0][-1] for row in values)
    return split_at(along, Fraction(1, 2))[0][-1]


def _split_v(values: Polynomial) -> tuple[Polynomial, Polynomial]:
    """
    Subdivide one complete tensor while retaining the original boundary coefficients.
    """
    pairs = tuple(split(row) for row in values)
    return tuple(pair[0] for pair in pairs), tuple(pair[1] for pair in pairs)


def _split_u(values: Polynomial) -> tuple[Polynomial, Polynomial]:
    """
    Share the same exact subdivision in the other original parameter direction.
    """
    first, second = _split_v(tuple(zip(*values)))
    return tuple(zip(*first)), tuple(zip(*second))


@dataclass(frozen=True)
class NativePlanarProjection:
    """
    Own a sufficient global projection certificate on the entire normalized native rectangle.

    G is the original physical (s,q) field, never UV or redefined material labels.
    B=DG(center)^-1 is fixed once for proof only. Every symmetric Bernstein
    coefficient matrix of D(BG), with its matching positive denominator, must
    be positive definite. A common lower eigenvalue bounds the integral along
    every straight parameter segment, proving global injectivity. Two fixed
    subdivisions per axis tighten enclosures without changing the derivative
    scale. Unresolved certificates are not witnessed folds or infeasible inputs.
    The reported coercivity and condition transfer back through B, so a good
    proof preconditioner cannot hide poor physical projection conditioning.
    This establishes no trim coverage, original/copy equivalence or isometry.
    """

    surface: NativeSurfaceSnapshot
    frame: FlatCutFrame
    checkpoint: InitVar[Callable[[], None]]
    root_inverse: Matrix | None = field(init=False)
    monotonicity_lower: Fraction | None = field(init=False)
    global_coercivity_lower_mm: Fraction | None = field(init=False)
    condition_upper: Fraction | None = field(init=False)
    coefficient_matrices: int = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Derive the root, full-domain positivity and physical projection condition without transferable pass flags.
        """
        checkpoint()
        surface = self.surface
        for degree, knots, count in (
            (surface.degree_u, surface.knots_u, len(surface.rows)),
            (surface.degree_v, surface.knots_v, len(surface.rows[0])),
        ):
            if (
                count != degree + 1
                or knots != (knots[0],) * (degree + 1) + (knots[-1],) * (degree + 1)
                or knots[0] >= knots[-1]
            ):
                raise ValueError("Complete single-span native tensor domains required")
        weight = surface.weights
        denominator = product(weight, weight)
        labels = label_numerators(surface, self.frame)
        jacobian = tuple(
            tuple(
                combine(
                    combine(product(d(n), weight), product(n, d(weight)), Fraction(-1)),
                    denominator,
                    Fraction(0),
                )
                for d in (_du, _dv)
            )
            for n in labels[:2]
        )
        center_weight = _center(denominator)
        a, b = (_center(values) / center_weight for values in jacobian[0])
        c, d = (_center(values) / center_weight for values in jacobian[1])
        determinant = a * d - b * c
        inverse = (
            None
            if determinant == 0
            else ((d / determinant, -b / determinant), (-c / determinant, a / determinant))
        )
        minimum = None
        coercivity = None
        condition = None
        count = 0
        if inverse is not None:
            transformed = tuple(
                combine(
                    tuple(tuple(x * row[0] for x in values) for values in jacobian[0][k]),
                    jacobian[1][k],
                    row[1],
                )
                for row in inverse
                for k in range(2)
            )
            cells = [(*transformed, denominator)]
            for _ in range(2):
                following = []
                for cell in cells:
                    checkpoint()
                    u_pairs = tuple(_split_u(values) for values in cell)
                    for u in (0, 1):
                        v_pairs = tuple(_split_v(pair[u]) for pair in u_pairs)
                        following.extend(tuple(pair[v] for pair in v_pairs) for v in (0, 1))
                cells = following
            minimum = Fraction(1)
            positive = True
            for cell in cells:
                checkpoint()
                for i in range(len(cell[-1])):
                    for j in range(len(cell[-1][0])):
                        count += 1
                        aa, bb, cc, dd, w = (values[i][j] for values in cell)
                        cross = (bb + cc) / 2
                        det = aa * dd - cross * cross
                        if aa <= 0 or dd <= 0 or det <= 0:
                            positive = False
                        else:
                            minimum = min(minimum, det / (aa + dd) / w)
            if positive:
                original_norm = max(
                    sum(abs(values[i][j]) for row in jacobian for values in row) / denominator[i][j]
                    for i in range(len(denominator))
                    for j in range(len(denominator[0]))
                )
                inverse_norm = sum(abs(x) for row in inverse for x in row)
                coercivity = minimum / inverse_norm
                condition = original_norm / coercivity
            else:
                minimum = None
        object.__setattr__(self, "root_inverse", inverse)
        object.__setattr__(self, "monotonicity_lower", minimum)
        object.__setattr__(self, "global_coercivity_lower_mm", coercivity)
        object.__setattr__(self, "condition_upper", condition)
        object.__setattr__(self, "coefficient_matrices", count)
        checkpoint()

    @property
    def status(self) -> str:
        """
        Require the existing numerical coordinate-conditioning ceiling without treating proof exhaustion as geometry failure.
        """
        return (
            "certified_global_native_sq_projection"
            if self.monotonicity_lower is not None
            and self.condition_upper is not None
            and self.condition_upper <= 1024
            else "unresolved_global_native_sq_projection"
        )
