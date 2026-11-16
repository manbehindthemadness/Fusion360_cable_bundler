"""
Bound path increments against one explicitly supplied common material-distance coordinate.

Equal bend phase is not equal material position on a diagonal crease. Each
source polynomial therefore carries its own material-distance interval. These
metric bounds do not establish source/native seam or volume correspondence.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, derivative, multiply

from .curve_lengths import Controls, distance
from .material_paths import square_root_lower


@dataclass(frozen=True)
class DistanceSpan:
    """
    Bind unchanged polynomial controls to their exact increasing material-distance interval.

    Controls use the local unit parameter. The affine material coordinate runs
    from low_mm to high_mm on that same parameter, without speed normalization.
    """

    low_mm: Fraction
    high_mm: Fraction
    controls: Controls

    def __post_init__(self) -> None:
        """
        Reject nonexact, nonfinite, stationary-domain or unsupported polynomial inputs.
        """
        if (
            type(self.low_mm) is not Fraction
            or type(self.high_mm) is not Fraction
            or not self.low_mm < self.high_mm
            or not 2 <= len(self.controls) <= 6
            or any(len(p) != 3 or any(type(x) is not Fraction for x in p) for p in self.controls)
        ):
            raise ValueError(
                "Exact increasing material interval and linear-through-quintic controls required"
            )


@dataclass(frozen=True)
class DistanceSpanBound:
    """
    Retain one whole-span absolute increment discrepancy bound and its original owner.
    """

    source: DistanceSpan
    squared_speed_residual: tuple[Fraction, ...]
    upper_mm: Fraction


def enclose(span: DistanceSpan, checkpoint: Callable[[], None]) -> DistanceSpanBound:
    """
    Bound integral abs(|X_t|-delta_s) without comparing unrelated path phases.

    R=|X_t|²-delta_s² and abs(|X_t|-delta_s)=abs(R)/(|X_t|+delta_s).
    Exact Bernstein ranges bound the numerator and, when positive, the actual
    speed below. The strictly positive supplied material increment always bounds
    the denominator, even for stationary spatial controls. Integration is over
    one local unit interval; no second interval-length multiplier is introduced.
    The bound also covers every corresponding local subinterval, without total
    cancellation, subdivision or an additional work allocation.
    """
    checkpoint()
    squared = (Fraction(0),)
    for axis in range(3):
        velocity = derivative(tuple(p[axis] for p in span.controls))
        squared = add(squared, multiply(velocity, velocity))
    expected = span.high_mm - span.low_mm
    residual = tuple(x - expected**2 for x in squared)
    minimum = min(squared)
    lower = square_root_lower(minimum) if minimum > 0 else Fraction(0)
    upper = max(map(abs, residual)) / (expected + lower)
    return DistanceSpanBound(span, residual, upper)


@dataclass(frozen=True)
class MaterialDistanceAudit:
    """
    Retain complete material-domain coverage and metric bounds without granting seam validity.

    Positive seam gaps remain measured outstanding source correspondence, even
    if small. The caller must establish the actual joined/native material map.
    """

    length_mm: Fraction
    spans: tuple[DistanceSpanBound, ...]
    upper_mm: Fraction
    seam_gaps_upper_mm: tuple[Fraction, ...]


def measure(
    spans: tuple[DistanceSpan, ...], length_mm: Fraction, checkpoint: Callable[[], None]
) -> MaterialDistanceAudit:
    """
    Cover the same complete material interval once and retain all source seam discrepancies.

    Each conductor label may have a different original knot partition, provided
    every partition covers exactly0..length. Summing absolute discrepancies to
    the same unit material speed permits comparisons on any shared subinterval.
    To compare two labels, sum their complete bounds once; do not infer another
    tolerance per region or allow a shared endpoint alone to prove cap flow.
    """
    checkpoint()
    if (
        type(length_mm) is not Fraction
        or length_mm <= 0
        or not spans
        or spans[0].low_mm != Fraction(0)
        or spans[-1].high_mm != length_mm
        or any(a.high_mm != b.low_mm for a, b in zip(spans, spans[1:]))
    ):
        raise ValueError("Every material label needs complete ordered common-distance coverage")
    proofs = tuple(enclose(span, checkpoint) for span in spans)
    gaps = tuple(distance(a.controls[-1], b.controls[0])[1] for a, b in zip(spans, spans[1:]))
    return MaterialDistanceAudit(
        length_mm, proofs, sum((p.upper_mm for p in proofs), Fraction(0)), gaps
    )
