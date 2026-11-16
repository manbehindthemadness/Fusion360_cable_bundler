"""
Derive an exact elliptic conic and minor-arc branch from original positive rational quadratic profile controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc

Matrix = tuple[tuple[Fraction, ...], ...]
Pair = tuple[Fraction, Fraction]


@dataclass(frozen=True)
class EllipseArc:
    """
    Own the implicit ellipse and original chord cap, without replacing or fitting the source profile.

    Positive barycentric rational-quadratic coordinates satisfy
    w0*w2*lambda1²-4*w1²*lambda0*lambda2=0. A positive definite quadratic
    part and a positive chord-center offset select the original minor arc.
    Unsupported/nonelliptic/degenerate inputs raise ValueError, not a physical
    failure declaration. Derived fields cannot be supplied as stale receipts.
    """

    arc: MaterialArc
    matrix: Matrix = field(init=False)
    center: Pair = field(init=False)
    kappa: Fraction = field(init=False)
    eigenvalue_lower: Fraction = field(init=False)
    normal: Pair = field(init=False)
    chord_offset: Fraction = field(init=False)
    angular_scale_squared: Fraction = field(init=False)

    def __post_init__(self) -> None:
        """
        Derive exact conic, center and branch constants from the SAME ordered original controls and weights.
        """
        if len(self.arc.controls) != 3 or len(self.arc.weights) != 3 or not self.arc.label:
            raise ValueError("A complete original quadratic profile required")
        points = tuple(tuple(Fraction(x) for x in p) for p in self.arc.controls)
        weights = tuple(Fraction(w) for w in self.arc.weights)
        if any(len(p) != 2 for p in points) or min(weights) <= 0:
            raise ValueError("Complete positive-weight original profile required")
        p0, p1, p2 = points
        u = tuple(b - a for a, b in zip(p0, p1))
        v = tuple(b - a for a, b in zip(p0, p2))
        determinant = u[0] * v[1] - u[1] * v[0]
        if determinant.numerator == 0:
            raise ValueError("A nondegenerate elliptic profile required")
        first = (v[1] / determinant, -v[0] / determinant)
        second = (-u[1] / determinant, u[0] / determinant)
        l1 = (*first, -sum(a * b for a, b in zip(first, p0)))
        l2 = (*second, -sum(a * b for a, b in zip(second, p0)))
        l0 = tuple(Fraction(int(k == 2)) - l1[k] - l2[k] for k in range(3))
        w0, w1, w2 = weights
        matrix = tuple(
            tuple(
                w0 * w2 * l1[i] * l1[j] - 2 * w1 * w1 * (l0[i] * l2[j] + l2[i] * l0[j])
                for j in range(3)
            )
            for i in range(3)
        )
        a, b, c = matrix[0][0], matrix[0][1], matrix[1][1]
        det = a * c - b * b
        if a <= 0 or det <= 0:
            raise ValueError("A nondegenerate elliptic profile required")
        inverse = ((c / det, -b / det), (-b / det, a / det))
        linear = matrix[0][2], matrix[1][2]
        center = tuple(-sum(x * y for x, y in zip(row, linear)) for row in inverse)
        kappa = -(matrix[2][2] + sum(x * y for x, y in zip(linear, center)))
        normal = (-v[1], v[0])
        if sum(n * x for n, x in zip(normal, u)) < 0:
            normal = tuple(-n for n in normal)
        d = sum(n * (p - o) for n, p, o in zip(normal, p0, center))
        scale_squared = (
            kappa * sum(normal[i] * inverse[i][j] * normal[j] for i in range(2) for j in range(2))
            - d * d
        )
        if kappa <= 0 or d <= 0 or scale_squared <= 0:
            raise ValueError("A proper positive minor ellipse arc required")
        object.__setattr__(self, "matrix", matrix)
        object.__setattr__(self, "center", center)
        object.__setattr__(self, "kappa", kappa)
        object.__setattr__(self, "eigenvalue_lower", det / (a + c))
        object.__setattr__(self, "normal", normal)
        object.__setattr__(self, "chord_offset", d)
        object.__setattr__(self, "angular_scale_squared", scale_squared)
