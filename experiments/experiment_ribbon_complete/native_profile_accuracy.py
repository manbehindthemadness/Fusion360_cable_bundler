"""
Bound whole-face original-profile distance through exact quadric residuals and a nondegenerate arc-branch estimate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction

from .cylinder_enclosure import NativeFaceBox
from .exact_frame import Point
from .flat_cut_domain import FlatCutFrame
from .material_paths import square_root_lower
from .profile_conic import EllipseArc, Matrix
from .ruled_support import square_root_upper


def chord_gradient(conic: EllipseArc, frame: FlatCutFrame) -> Point:
    """
    Pull the ORIGINAL profile chord normal through the material inverse without fitting a native face.
    """
    rows = frame.inverse.rows
    assert rows is not None
    return tuple(conic.normal[0] * a + conic.normal[1] * b for a, b in zip(rows[1], rows[2]))


def bilinear(matrix: Matrix, left: tuple[Fraction, ...], right: tuple[Fraction, ...]) -> Fraction:
    """
    Evaluate an exact fixed-dimensional homogeneous quadratic bilinear form.
    """
    return sum(
        (left[i] * matrix[i][j] * right[j] for i in range(len(left)) for j in range(len(right))),
        Fraction(0),
    )


def residual_bound(conic: EllipseArc, frame: FlatCutFrame, box: NativeFaceBox) -> Fraction:
    """
    Bound the original implicit profile on EVERY actual cylinder-face point by cancelling its support quadric first.

    Coordinates X are world displacements from the captured native cylinder
    origin. H(X) is the exact source-profile conic pulled back through the
    original affine q/b field. K(X)=X'PX-R² vanishes on the actual cylinder.
    beta=trace(H_quadratic)/2 is an algebraic scaling, never a geometry fit.
    Bound H-beta*K over the entire SDK box using its constant/linear/quadratic
    monomial coefficient absolute sum on [-1,1]³. The support contract, not
    sampled residuals, then transfers this bound to the actual face.
    """
    native = box.native
    rows = frame.inverse.rows
    assert rows is not None
    affine = tuple(
        (*rows[k], sum(r * (o - c) for r, o, c in zip(rows[k], native.origin, frame.origin)))
        for k in (1, 2)
    ) + ((Fraction(0), Fraction(0), Fraction(0), Fraction(1)),)
    source = tuple(
        tuple(
            sum(
                affine[a][i] * conic.matrix[a][b] * affine[b][j] for a in range(3) for b in range(3)
            )
            for j in range(4)
        )
        for i in range(4)
    )
    squared = sum(x * x for x in native.axis)
    support = tuple(
        tuple(
            (Fraction(int(i == j)) - native.axis[i] * native.axis[j] / squared)
            if i < 3 and j < 3
            else -(native.radius_mm**2)
            if i == j == 3
            else Fraction(0)
            for j in range(4)
        )
        for i in range(4)
    )
    beta = sum(source[i][i] for i in range(3)) / 2
    if beta <= 0:
        raise ValueError("Positive source/cylinder quadric comparison required")
    residual = tuple(tuple(source[i][j] - beta * support[i][j] for j in range(4)) for i in range(4))
    center = tuple(p - o for p, o in zip(box.center_mm, native.origin)) + (Fraction(1),)
    axes = tuple((*axis, Fraction(0)) for axis in box.half_axes_mm)
    return (
        abs(bilinear(residual, center, center))
        + 2 * sum(abs(bilinear(residual, axis, center)) for axis in axes)
        + sum(abs(bilinear(residual, a, b)) for a in axes for b in axes)
    )


@dataclass(frozen=True)
class NativeProfileAccuracy:
    """
    Compute a uniform profile-arc distance bound without changing native points or material coordinates.

    For H(z)=(z-c)'Q(z-c)-kappa and Q>=lambda*I, radial projection onto
    the ellipse has Euclidean distance <=abs(H)/sqrt(lambda*kappa), provided
    abs(H)<kappa. Original arc is the ellipse cap n.(z-c)>=d>0. If its
    projected point misses that cap by epsilon<d, circle coordinates give
    angular excess <=epsilon/sqrt(kappa*n'Q^-1*n-d²); ellipse radius upper
    converts it to distance. Factor2 converts 2D Euclidean distance to L1;
    original material-frame column norms bound world L1 with the SAME bound.
    This is an existence-of-distance-witness proof, not clamping/remapping,
    material isometry, transverse label assignment or complete-trim acceptance.
    """

    conic: EllipseArc
    frame: FlatCutFrame
    boxes: tuple[NativeFaceBox, ...]
    checkpoint: InitVar[Callable[[], None]]
    implicit_residual_upper: Fraction = field(init=False)
    minimum_chord_gap: Fraction = field(init=False)
    distance_upper_mm: Fraction | None = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Derive every bound from the SAME actual face, original material frame and profile under caller resource checks.
        """
        checkpoint()
        if not self.boxes or any(box.native is not self.boxes[0].native for box in self.boxes):
            raise ValueError("Enclosures of the SAME actual native face required")
        if (
            self.conic.arc.label != self.boxes[0].native.profile_label
            or self.frame.region.value != self.boxes[0].native.region
        ):
            raise ValueError("The SAME original native region/profile required")
        residual = min(residual_bound(self.conic, self.frame, box) for box in self.boxes)
        rows = self.frame.inverse.rows
        assert rows is not None
        p0 = tuple(Fraction(x) for x in self.conic.arc.controls[0])
        gradient = chord_gradient(self.conic, self.frame)
        offset = -sum(n * p for n, p in zip(self.conic.normal, p0))
        lower_bounds = []
        for box in self.boxes:
            gaps = []
            for point in box.corners():
                gaps.append(
                    offset + sum(g * (p - o) for g, p, o in zip(gradient, point, self.frame.origin))
                )
            lower_bounds.append(min(gaps))
        minimum = max(lower_bounds)
        distance = None
        divisor = square_root_lower(self.conic.eigenvalue_lower * self.conic.kappa)
        angular_scale = square_root_lower(self.conic.angular_scale_squared)
        if residual < self.conic.kappa and divisor > 0 and angular_scale > 0:
            radial = residual / divisor
            normal_norm = square_root_upper(sum((n * n for n in self.conic.normal), Fraction(0)))
            epsilon = max(Fraction(0), -minimum) + normal_norm * radial
            if epsilon < self.conic.chord_offset:
                radius = square_root_upper(self.conic.kappa / self.conic.eigenvalue_lower)
                material_euclidean = radial + radius * epsilon / angular_scale
                scale = max(
                    Fraction(1), *(sum(map(abs, column)) for column in self.frame.columns[1:])
                )
                distance = 2 * scale * material_euclidean
        checkpoint()
        object.__setattr__(self, "implicit_residual_upper", residual)
        object.__setattr__(self, "minimum_chord_gap", minimum)
        object.__setattr__(self, "distance_upper_mm", distance)

    @property
    def status(self) -> str:
        """
        Require a complete nondegenerate branch-aware dimensional bound within the authorized inclusive tolerance.
        """
        return (
            "within_native_original_profile_accuracy"
            if self.distance_upper_mm is not None and self.distance_upper_mm <= Fraction(1, 100)
            else "unresolved_native_original_profile_accuracy"
        )
