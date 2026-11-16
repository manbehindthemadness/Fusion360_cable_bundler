"""
Qualify global flat material coordinates on native cylinder supports without assuming trim coverage.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, derivative, elevate, multiply

from .flat_chart import certify as frame_bounds
from .material_paths import square_root_lower
from .native_cap_chain import profile_rates
from .native_face_condition import parameter_bounds
from .native_face_embedding import profile_separation
from .native_flat_cylinder import CylinderRadialField, FlatCylinderBound, radial_field


def implicit_bounds(
    field: CylinderRadialField, extent_mm: Fraction, checkpoint: Callable[[], None]
) -> tuple[Fraction, Fraction, tuple[Fraction, Fraction]]:
    """
    Bound r², abs(S) and physical s/original V derivatives of S=r²-R² over one rectangle.

    S uses degree2 in normalized longitudinal position and positive W²(V).
    Differentiate that same residual, preserving exact coefficient cancellation;
    V uses the full rational quotient derivative over positive W⁴. No small
    positional residual is substituted for a derivative enclosure.
    """
    checkpoint()
    if type(extent_mm) is not Fraction or extent_mm <= 0:
        raise ValueError("An exact positive physical rectangle extent required")
    denominator = field.denominator[0]
    residual = field.residual
    lower = min(x / w for row in field.squared for x, w in zip(row, denominator))
    magnitude = max(abs(x) / w for row in residual for x, w in zip(row, denominator))
    along = max(
        abs(b - a) * (len(residual) - 1) / w / extent_mm
        for first, second in zip(residual, residual[1:])
        for a, b, w in zip(first, second, denominator)
    )
    denominator_prime = derivative(denominator)
    squared_denominator = multiply(denominator, denominator)
    across = Fraction(0)
    for row in residual:
        checkpoint()
        numerator = elevate(
            add(
                multiply(derivative(row), denominator),
                multiply(row, denominator_prime),
                Fraction(-1),
            ),
            len(squared_denominator) - 1,
        )
        across = max(across, max(abs(x) / w for x, w in zip(numerator, squared_denominator)))
    return lower, magnitude, (along, across)


@dataclass(frozen=True)
class FlatEmbeddingEvidence:
    """
    Own the original support, covering physical domain and explicit derivative bounds.
    """

    support: FlatCylinderBound
    interval_mm: tuple[Fraction, Fraction]
    field: CylinderRadialField | None
    profile_lower_mm: Fraction | None
    canonical_lower: Fraction | None
    error_partials: tuple[Fraction, Fraction] | None
    separation_lower: Fraction | None
    condition_upper: Fraction | None


@dataclass(frozen=True)
class FlatSupportEmbedding:
    """
    Retain inverse-on-support-image validity, with actual native trims and interior material gates open.

    Coordinates are physical(s,cV*V), not cylinder-native UV or normalized lead
    fractions. The rectangle covers both original curved cuts, including tiny
    signed fragments. No geometry, source domain or native UV is altered.
    """

    support: FlatCylinderBound
    evidence: FlatEmbeddingEvidence
    status: str

    def __post_init__(self) -> None:
        """
        Reject stale support replacement and qualified status without owned positive bounded evidence.
        """
        proof = self.evidence
        if proof.support is not self.support or (
            proof.field is not None and proof.field.native is not self.support.native
        ):
            raise ValueError("The SAME original support and native cylinder evidence required")
        if self.status == "certified_flat_support_global_coordinates" and (
            proof.field is None
            or proof.profile_lower_mm is None
            or proof.profile_lower_mm <= 0
            or proof.error_partials is None
            or proof.separation_lower is None
            or proof.separation_lower <= 0
            or proof.condition_upper is None
            or proof.condition_upper > 1024
            or self.support.status != "within_support_construction_accuracy"
        ):
            raise ValueError("Owned positive global separation and1024 conditioning required")


def certify(support: FlatCylinderBound, checkpoint: Callable[[], None]) -> FlatSupportEmbedding:
    """
    Transfer canonical global separation using a rigorous radial-projection error gradient.

    For E=(R/r-1)*rvec, ||E_j||1 <=abs(S)/(r_min*R)*||rvec_j||1
    +R*abs(S_j)/r_min², since sqrt(3)/2<=1. The SAME affine frame inverse
    gives canonical Euclidean separation >=1/(2*inverse_norm) in physical
    (s,cV*V). Subtract E_s+E_V/cV; a positive remainder proves global
    injectivity and inverse onto the projected image. Forward partials plus
    inverse separation give the independent1024 conditioning bound.
    """
    checkpoint()
    chart, arc, native = support.chart, support.arc, support.native
    frame = frame_bounds(chart)
    cuts = tuple(cut.at(Fraction(q)) for cut in (chart.low, chart.high) for q, _ in arc.controls)
    interval = min(cuts), max(cuts)
    profile_lower = profile_separation(arc, checkpoint)
    field = None
    canonical_lower = None
    errors = None
    separation = None
    condition = None
    status = "unresolved_flat_support_embedding"
    if (
        support.status == "within_support_construction_accuracy"
        and frame.status == "certified_affine_material_chart"
        and frame.frame.inverse_norm is not None
        and profile_lower is not None
        and interval[0] < interval[1]
    ):
        rows = tuple(
            tuple(chart.point(s, Fraction(q), Fraction(b)) for q, b in arc.controls)
            for s in interval
        )
        field = radial_field(native, rows, tuple(map(Fraction, arc.weights)), checkpoint)
        lower, residual, derivatives = implicit_bounds(field, interval[1] - interval[0], checkpoint)
        minimum_radius = square_root_lower(lower) if lower > 0 else Fraction(0)
        if minimum_radius > 0:
            q_rate, b_rate = profile_rates(arc)
            radial_along = sum(map(abs, native.radial(chart.columns[0])), Fraction(0))
            radial_across = (
                sum(map(abs, native.radial(chart.columns[1])), Fraction(0)) * q_rate
                + sum(map(abs, native.radial(chart.columns[2])), Fraction(0)) * b_rate
            )
            partial_errors = tuple(
                residual / (minimum_radius * native.radius_mm) * rate
                + native.radius_mm * d / minimum_radius**2
                for rate, d in zip((radial_along, radial_across), derivatives)
            )
            errors = partial_errors[0], partial_errors[1]
            canonical_lower = 1 / (2 * frame.frame.inverse_norm)
            separation = canonical_lower - errors[0] - errors[1] / profile_lower
            status = "unresolved_flat_support_global_injectivity"
            if separation > 0:
                along = sum(map(abs, chart.columns[0]), Fraction(0)) + errors[0]
                across = (
                    sum(map(abs, chart.columns[1]), Fraction(0)) * q_rate
                    + sum(map(abs, chart.columns[2]), Fraction(0)) * b_rate
                    + errors[1]
                )
                _, _, condition = parameter_bounds(
                    (along, across), (Fraction(1), profile_lower), separation
                )
                status = (
                    "certified_flat_support_global_coordinates"
                    if condition <= 1024
                    else "unresolved_flat_support_parameter_conditioning"
                )
    checkpoint()
    evidence = FlatEmbeddingEvidence(
        support, interval, field, profile_lower, canonical_lower, errors, separation, condition
    )
    return FlatSupportEmbedding(support, evidence, status)
