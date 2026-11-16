"""
Certify a complete bend's global injectivity through reference separation minus gradient perturbation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3217.extraction import scalar

from .scalar_reference import enclose as scalar_bounds
from .volume_field import BendVolume


@dataclass(frozen=True)
class SpanGradientBound:
    """
    Retain physical crease-distance/q/b gradient-error bounds on one original source span.
    """

    index: int
    entries: tuple[tuple[Fraction, ...], ...]
    operator_upper: Fraction


def gradient(volume: BendVolume, index: int, checkpoint: Callable[[], None]) -> SpanGradientBound:
    """
    Bound the SAME canonical volume minus the analytic cylinder over the complete q/b box.

    Assembly residual uses actual captured midplane controls minus the exact
    shared-spline expression. Scalar value/derivative errors separately account
    for analytic trigonometry and phase. Thickness terms use the same N fields.
    x=R*phi,q,b are all physical millimeters, so their error matrix is dimensionless.
    Sum of entry bounds safely bounds its Euclidean operator norm.
    """
    checkpoint()
    basis = volume.source.surface.basis
    low, high = basis.breaks[index : index + 2]
    width = high - low
    sine, cosine, phase = (
        scalar(curve, index)
        for curve in (volume.fields.sine, volume.fields.cosine, volume.fields.phase)
    )
    errors = scalar_bounds(sine, cosine, phase, low, high, checkpoint)
    first, second, normal = volume.columns
    radius, reach = volume.radius_mm, volume.half_thickness_mm
    ideal = tuple(
        tuple(
            tuple(
                volume.origin[k]
                + volume.forward[k] * volume.before_mm
                + first[k] * radius * sine[i]
                + second[k] * (-radius * phase[i] * volume.sine / volume.cosine + q / volume.cosine)
                + normal[k] * volume.sign * radius * (1 - cosine[i])
                for k in range(3)
            )
            for q in (-volume.source.half_mm, Fraction(0), volume.source.half_mm)
        )
        for i in range(6)
    )
    actual = volume.source.spans[index]
    residual = tuple(
        tuple(tuple(a - b for a, b in zip(p, q)) for p, q in zip(row, reference))
        for row, reference in zip(actual, ideal)
    )
    entries = []
    for k in range(3):
        checkpoint()
        assembly_phase = max(
            abs(5 * (residual[i + 1][j][k] - residual[i][j][k]) / width)
            for i in range(5)
            for j in range(3)
        )
        assembly_q = max(
            abs((row[j + 1][k] - row[j][k]) / volume.source.half_mm)
            for row in residual
            for j in range(2)
        )
        phase_error = (
            assembly_phase
            + (radius + reach)
            * (abs(first[k]) * errors.sine_first + abs(normal[k]) * errors.cosine_first)
            + abs(second[k]) * radius * abs(volume.sine / volume.cosine) * errors.phase_first
        )
        b_error = abs(first[k]) * errors.sine + abs(normal[k]) * errors.cosine
        entries.append((phase_error / radius, assembly_q, b_error))
    values = tuple(entries)
    total = Fraction(sum((value for row in values for value in row), Fraction(0)))
    return SpanGradientBound(index, values, total)


@dataclass(frozen=True)
class GlobalBendProof:
    """
    Bind whole-domain reference/perturbation bounds to the original continuous volume owner.

    This is per-bend global injectivity, not whole-trunk contact, native image
    membership, material isometry, junctions, endings or a solver success flag.
    """

    volume: BendVolume
    reference_lower: Fraction | None
    gradient_upper: Fraction | None
    separation_lower: Fraction | None
    spans: tuple[SpanGradientBound, ...]
    status: str


def audit(volume: BendVolume, checkpoint: Callable[[], None]) -> GlobalBendProof:
    """
    Prove global source separation on the complete convex box or retain an unresolved reference.

    The source and N fields share one complete global C2 basis. A straight
    parameter segment crosses finitely many original knots, so the maximum
    whole-span gradient bound gives a global Lipschitz error. If smaller than
    the reference's global lower separation factor, their difference is strictly
    positive and distinct material coordinates cannot coincide. No new spatial
    samples, subdivisions, metric tolerance or work allocation are introduced.
    """
    checkpoint()
    reference = volume.reference_lower()
    if reference is None:
        return GlobalBendProof(volume, None, None, None, (), "unresolved_reference_domain")
    spans = tuple(gradient(volume, i, checkpoint) for i in range(len(volume.source.spans)))
    upper = max(span.operator_upper for span in spans)
    lower = reference - upper
    return GlobalBendProof(
        volume,
        reference,
        upper,
        lower,
        spans,
        "certified_bend_global_injectivity" if lower > 0 else "unresolved_gradient_margin",
    )
