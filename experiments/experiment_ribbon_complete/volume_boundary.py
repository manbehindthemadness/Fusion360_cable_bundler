"""
Relate an explicit bend-volume extension of the measured midplane to outgoing boundary controls.

Boundary agreement does not establish invertibility, contact, native topology or
material metrics away from b=0. Those qualifications remain separate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, multiply
from artifacts.verification.resume3217.extraction import Net
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc

from .c2_material import MidplaneSource
from .curve_lengths import Controls

HomogeneousNet = tuple[tuple[tuple[Fraction, ...], ...], ...]


@dataclass(frozen=True)
class VolumeSpan:
    """
    Extend the original b0 tensor by b times an explicit polynomial thickness direction.

    F(phi,q,b)=A(phi,q)+b*N(phi), with A the SAME captured measured midsurface.
    N uses the same quintic U basis. Neither unit N nor a positive/global volume
    Jacobian is assumed. Span and source identities are retained for later proofs.
    """

    source: MidplaneSource
    index: int
    normal: Controls

    def __post_init__(self) -> None:
        """
        Reject missing original spans and nonexact or incompatible thickness fields.
        """
        if (
            type(self.index) is not int
            or not 0 <= self.index < len(self.source.spans)
            or len(self.normal) != 6
            or any(len(p) != 3 or any(type(x) is not Fraction for x in p) for p in self.normal)
        ):
            raise ValueError("An original midplane span and complete exact quintic normal required")


def boundary(volume: VolumeSpan, arc: MaterialArc) -> HomogeneousNet:
    """
    Compose the rational profile exactly with the same quadratic transverse volume field.

    Q=(q*w+half*w)/(2*half) is the homogeneous transverse coordinate and W=w.
    A(Q/W) has numerator A0*(W-Q)²+2*A1*Q*(W-Q)+A2*Q².
    The thickness contribution is N*b*W and the common denominator is W².
    This retains the small nonaffine transverse terms in stored world controls;
    no affine fit, weight separation or geometry modification is introduced.
    """
    return compose(volume.source.spans[volume.index], volume.normal, volume.source.half_mm, arc)


def compose(
    rows: Net,
    normals: Controls,
    half_mm: Fraction,
    arc: MaterialArc,
    checkpoint: Callable[[], None] | None = None,
) -> HomogeneousNet:
    """
    Compose the same rational profile with any complete shared polynomial-U control sequence.

    Positive U basis functions must form a partition of unity, as with the
    original Bernstein spans or captured global clamped B-spline basis. No
    extraction, fitting, normalization or control rounding occurs here.
    """
    if (
        not rows
        or len(rows) != len(normals)
        or type(half_mm) is not Fraction
        or half_mm <= 0
        or any(
            len(row) != 3
            or any(len(p) != 3 or any(type(x) is not Fraction for x in p) for p in row)
            for row in rows
        )
        or any(len(p) != 3 or any(type(x) is not Fraction for x in p) for p in normals)
    ):
        raise ValueError(
            "Complete exact shared-U midplane/normal controls and positive half width required"
        )
    if (
        len(arc.controls) != 3
        or len(arc.weights) != 3
        or any(weight <= 0 for weight in arc.weights)
    ):
        raise ValueError("An original positive-weight quadratic profile required")
    w = tuple(Fraction(x) for x in arc.weights)
    q = tuple(
        (Fraction(p[0]) + half_mm) * weight / (2 * half_mm) for p, weight in zip(arc.controls, w)
    )
    b = tuple(Fraction(p[1]) * weight for p, weight in zip(arc.controls, w))
    opposite = add(w, q, Fraction(-1))
    factors = (
        multiply(opposite, opposite),
        tuple(2 * x for x in multiply(q, opposite)),
        multiply(q, q),
    )
    thickness, weight = multiply(b, w), multiply(w, w)
    output = []
    for row, normal in zip(rows, normals):
        if checkpoint is not None:
            checkpoint()
        output.append(
            tuple(
                tuple(
                    sum((row[j][axis] * factors[j][v] for j in range(3)), Fraction(0))
                    + normal[axis] * thickness[v]
                    for axis in range(3)
                )
                + (weight[v],)
                for v in range(5)
            )
        )
    return tuple(output)


@dataclass(frozen=True)
class BoundaryCorrespondence:
    """
    Retain a continuous source-to-outgoing boundary bound without a whole-volume validity flag.
    """

    volume: VolumeSpan
    arc: MaterialArc
    outgoing_controls: Net
    volume_boundary: HomogeneousNet
    upper_mm: Fraction


def enclose(
    volume: VolumeSpan,
    arc: MaterialArc,
    outgoing: Net,
    checkpoint: Callable[[], None],
) -> BoundaryCorrespondence:
    """
    Bound all original U/V boundary positions by exact homogeneous control differences.

    Outgoing is the actual physical-unit polynomial-U control net, after any cm
    conversion/conditioning that the caller captured. Its positive profile
    weights are original. Multiplication by W gives the same W² denominator as
    the volume composition. Bernstein convexity and its positive lower weight
    bound yield a complete positional enclosure. No sampled agreement or absent
    native audit is promoted to physical/material validity.
    """
    checkpoint()
    if len(outgoing) != 6 or any(
        len(row) != 3 or any(len(p) != 3 or any(type(x) is not Fraction for x in p) for p in row)
        for row in outgoing
    ):
        raise ValueError("Complete exact outgoing quintic/quadratic physical controls required")
    composed = boundary(volume, arc)
    maximum = position_bound(composed, outgoing, arc, checkpoint)
    return BoundaryCorrespondence(volume, arc, outgoing, composed, maximum)


@dataclass(frozen=True)
class RationalBoundaryResidual:
    """
    Retain exact canonical-minus-native numerator controls over a shared positive V denominator.

    U rows must use the same basis. Geometry ownership is retained by the caller's
    chart receipt; this pure algebra object stores no acceptance or native identity.
    """

    numerators: Net
    denominator: tuple[Fraction, ...]

    def __post_init__(self) -> None:
        """
        Require complete exact quartic V rows and strictly positive denominator coefficients.
        """
        if (
            not self.numerators
            or len(self.denominator) != 5
            or any(type(x) is not Fraction or x <= 0 for x in self.denominator)
            or any(
                len(row) != 5
                or any(len(p) != 3 or any(type(x) is not Fraction for x in p) for p in row)
                for row in self.numerators
            )
        ):
            raise ValueError(
                "Complete exact residual controls and positive shared denominator required"
            )

    @property
    def position_upper_mm(self) -> Fraction:
        """
        Bound every complete-chart position by convexity of the shared positive bases.
        """
        return max(sum(map(abs, p), Fraction(0)) for row in self.numerators for p in row) / min(
            self.denominator
        )


def position_bound(
    composed: HomogeneousNet, outgoing: Net, arc: MaterialArc, checkpoint: Callable[[], None]
) -> Fraction:
    """
    Preserve the existing positional entry point using the same exact homogeneous residual.
    """
    return control_residual(composed, outgoing, arc, checkpoint).position_upper_mm


def control_residual(
    composed: HomogeneousNet, outgoing: Net, arc: MaterialArc, checkpoint: Callable[[], None]
) -> RationalBoundaryResidual:
    """
    Bound complete-chart positions over identical nonnegative shared U basis functions.

    Outgoing quadratic rational rows use the SAME original arc weights W.
    Multiplication by W yields the canonical W² denominator. The maximum L1
    numerator coefficient difference divided by its positive coefficient lower
    bound encloses every parameter position, including between sample stations.
    """
    checkpoint()
    if (
        not composed
        or len(composed) != len(outgoing)
        or any(len(row) != 5 for row in composed)
        or any(len(row) != 3 for row in outgoing)
    ):
        raise ValueError(
            "Matching complete canonical quartic and outgoing quadratic row sequences required"
        )
    weights = tuple(Fraction(w) for w in arc.weights)
    if len(weights) != 3 or min(weights) <= 0:
        raise ValueError("Original positive quadratic profile weights required")
    squared = multiply(weights, weights)
    if any(
        len(p) != 4 or any(type(x) is not Fraction for x in p) or p[3] != squared[v]
        for row in composed
        for v, p in enumerate(row)
    ) or any(
        len(p) != 3 or any(type(x) is not Fraction for x in p) for row in outgoing for p in row
    ):
        raise ValueError("Exact coordinates and the SAME original homogeneous denominator required")
    differences = []
    for row, actual in zip(composed, outgoing):
        checkpoint()
        axes = tuple(
            multiply(tuple(p[k] * w for p, w in zip(actual, weights)), weights) for k in range(3)
        )
        differences.append(
            tuple(tuple(p[k] - axes[k][v] for k in range(3)) for v, p in enumerate(row))
        )
    return RationalBoundaryResidual(tuple(differences), squared)
