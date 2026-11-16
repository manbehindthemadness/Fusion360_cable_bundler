"""
Transfer whole-bend separation to native surface uniqueness using rigorous residual derivatives.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, derivative, elevate, multiply
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc

from .native_material_chart import NativeMaterialChart
from .volume_injectivity import GlobalBendProof


def profile_separation(arc: MaterialArc, checkpoint: Callable[[], None]) -> Fraction | None:
    """
    Bound Euclidean profile chord separation per original V by a monotone chord projection.

    Project on d/||d||1, where d is the original endpoint chord. This projection
    has Euclidean norm at most1. A positive lower bound on its rational derivative
    therefore gives ||profile(v)-profile(w)||2 >=lower*|v-w|. Closed/backtracking
    or inconclusive arcs stay unresolved; no sampled derivative can replace it.
    """
    checkpoint()
    if len(arc.controls) != 3 or any(len(p) != 2 for p in arc.controls) or len(arc.weights) != 3:
        raise ValueError("A complete original quadratic rational profile required")
    weights = tuple(Fraction(w) for w in arc.weights)
    if min(weights) <= 0:
        raise ValueError("Positive original profile weights required")
    chord = tuple(Fraction(arc.controls[-1][k]) - Fraction(arc.controls[0][k]) for k in range(2))
    norm = sum(map(abs, chord), Fraction(0))
    if norm == 0:
        return None
    numerator = tuple(
        sum((d * Fraction(p[k]) for k, d in enumerate(chord)), Fraction(0)) * w / norm
        for p, w in zip(arc.controls, weights)
    )
    quotient = elevate(
        add(
            multiply(derivative(numerator), weights),
            multiply(numerator, derivative(weights)),
            Fraction(-1),
        ),
        4,
    )
    denominator = multiply(weights, weights)
    lower = min(x / w for x, w in zip(quotient, denominator))
    return lower if lower > 0 else None


def residual_derivatives(
    chart: NativeMaterialChart, checkpoint: Callable[[], None]
) -> tuple[Fraction, Fraction]:
    """
    Enclose native-minus-canonical U/V partial L1 norms on the SAME complete global rectangle.

    U uses ordinary degree5 B-spline derivative control differences over positive
    W²(V). V uses (D'W²-D(W²)')/(W²)², preserving exact cancellations. All quotient
    numerator coefficients are elevated to the matching positive denominator
    degree before convex-ratio bounds. Values never stand in for derivatives.
    """
    checkpoint()
    if chart.status != "certified_native_material_parameter_chart" or chart.correspondence is None:
        raise ValueError("A qualified SAME-source native chart with owned residual required")
    residual = chart.correspondence.residual
    basis = chart.volume.source.surface.basis
    if len(residual.numerators) != basis.count:
        raise ValueError("The SAME complete original U basis and residual required")
    denominator = residual.denominator
    along = Fraction(0)
    for i, (first, second) in enumerate(zip(residual.numerators, residual.numerators[1:])):
        checkpoint()
        span = basis.knots[i + 6] - basis.knots[i + 1]
        if span <= 0:
            raise ValueError("Positive original derivative support required")
        along = max(
            along,
            max(
                sum((abs(b - a) for a, b in zip(p, q)), Fraction(0)) / w
                for p, q, w in zip(first, second, denominator)
            )
            * 5
            / span,
        )
    across = Fraction(0)
    squared = multiply(denominator, denominator)
    denominator_first = derivative(denominator)
    for row in residual.numerators:
        checkpoint()
        axes = []
        for k in range(3):
            numerator = tuple(p[k] for p in row)
            axes.append(
                elevate(
                    add(
                        multiply(derivative(numerator), denominator),
                        multiply(numerator, denominator_first),
                        Fraction(-1),
                    ),
                    8,
                )
            )
        across = max(
            across,
            max(
                sum((abs(axis[j]) for axis in axes), Fraction(0)) / w for j, w in enumerate(squared)
            ),
        )
    return along, across


@dataclass(frozen=True)
class NativeEmbeddingEvidence:
    """
    Bind the exact residual derivative calculation to its original native chart and canonical proof.
    """

    chart: NativeMaterialChart
    canonical: GlobalBendProof
    profile_lower_mm: Fraction
    residual_partial_upper: tuple[Fraction, Fraction]
    perturbation_upper: Fraction


@dataclass(frozen=True)
class NativeFaceEmbedding:
    """
    Retain whole native parameter uniqueness, separately from1024 conditioning and physical acceptance.

    The separation metric uses physical (R*phase,cV*V) coordinates. A positive
    lower bound implies injectivity and a Lipschitz inverse onto this surface
    image. It does not assert that a target belongs to the image, that a trim
    covers the whole rectangle, or that cap labels have been adopted. Full local
    conditioning/material/contact/ending gates remain separate and unaccepted.
    """

    chart: NativeMaterialChart
    canonical: GlobalBendProof
    profile_lower_mm: Fraction | None
    residual_partial_upper: tuple[Fraction, Fraction] | None
    perturbation_upper: Fraction | None
    separation_lower: Fraction | None
    status: str
    evidence: NativeEmbeddingEvidence | None = None

    def __post_init__(self) -> None:
        """
        Reject stale volume ownership and qualification without a strictly positive separation margin.
        """
        if self.canonical.volume is not self.chart.volume:
            raise ValueError("The SAME original canonical volume and native chart required")
        owned = self.evidence
        if owned is not None and (
            owned.chart is not self.chart
            or owned.canonical is not self.canonical
            or owned.profile_lower_mm != self.profile_lower_mm
            or owned.residual_partial_upper != self.residual_partial_upper
            or owned.perturbation_upper != self.perturbation_upper
            or self.canonical.separation_lower is None
            or self.separation_lower != self.canonical.separation_lower - owned.perturbation_upper
        ):
            raise ValueError(
                "Embedding evidence must own the SAME chart, canonical proof and bounds"
            )
        if self.status == "certified_native_face_global_injectivity" and (
            owned is None
            or self.separation_lower is None
            or self.separation_lower <= 0
            or self.profile_lower_mm is None
            or self.profile_lower_mm <= 0
            or self.canonical.status != "certified_bend_global_injectivity"
        ):
            raise ValueError("A positive source-bound native separation margin required")


def certify(
    chart: NativeMaterialChart, canonical: GlobalBendProof, checkpoint: Callable[[], None]
) -> NativeFaceEmbedding:
    """
    Subtract a global physical-parameter Lipschitz perturbation from SAME-source canonical separation.

    Original material-profile separation makes the canonical surface at least
    as separated in (R*phase,cV*V) as the volume is in (R*phase,q,b). Integrating
    residual partial bounds along a straight segment of the parameter rectangle
    gives operator bound U_error/R+V_error/cV. Both fields share the continuous
    global basis, so internal knots introduce no jumps. Strictly positive
    canonical_lower-perturbation proves uniqueness without new sampling or tuning.
    """
    checkpoint()
    if canonical.volume is not chart.volume:
        raise ValueError("The SAME original canonical volume and native chart required")
    profile = profile_separation(chart.arc, checkpoint)
    if (
        canonical.status != "certified_bend_global_injectivity"
        or canonical.separation_lower is None
        or profile is None
    ):
        return NativeFaceEmbedding(
            chart, canonical, profile, None, None, None, "unresolved_native_face_reference"
        )
    partials = residual_derivatives(chart, checkpoint)
    perturbation = partials[0] / chart.volume.radius_mm + partials[1] / profile
    lower = canonical.separation_lower - perturbation
    status = (
        "certified_native_face_global_injectivity"
        if lower > 0
        else "unresolved_native_face_gradient_margin"
    )
    checkpoint()
    evidence = NativeEmbeddingEvidence(chart, canonical, profile, partials, perturbation)
    return NativeFaceEmbedding(
        chart, canonical, profile, partials, perturbation, lower, status, evidence
    )
