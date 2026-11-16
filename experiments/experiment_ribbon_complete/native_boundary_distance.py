"""
Bound both directions of finite original material-boundary coverage without moving native or source geometry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from enum import Enum
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import (
    Polynomial,
    add,
    multiply,
    split,
)

from .flat_cut_domain import FlatCutFrame
from .native_surface_trace import NativeSurfaceTrace
from .profile_conic import EllipseArc
from .profile_continuity import derivative_numerators


def _pieces(
    values: tuple[Polynomial, ...], checkpoint: Callable[[], None]
) -> list[tuple[Polynomial, ...]]:
    """
    Apply exactly two fixed coefficient subdivisions with all rational components kept together.
    """
    output = [values]
    for _ in range(2):
        following = []
        for row in output:
            checkpoint()
            pairs = tuple(split(value) for value in row)
            following.extend(tuple(pair[k] for pair in pairs) for k in (0, 1))
        output = following
    return output


def _absolute(
    numerator: Polynomial, denominator: Polynomial, checkpoint: Callable[[], None]
) -> Fraction:
    """
    Bound the complete positive-denominator scalar image without endpoint-only inference.
    """
    return max(
        abs(n) / d
        for ns, ds in _pieces((numerator, denominator), checkpoint)
        for n, d in zip(ns, ds)
    )


def interval_coverage_gap(
    source: tuple[Fraction, Fraction], intervals: tuple[tuple[Fraction, Fraction], ...]
) -> Fraction:
    """
    Return the exact one-dimensional source-to-union Hausdorff distance, retaining every missing end and interior gap.

    A zero-length source interval is valid. Intervals may overlap, extend past
    the source or be points. No interval is silently lengthened to its neighbors.
    """
    if (
        not intervals
        or any(type(x) is not Fraction for row in (source, *intervals) for x in row)
        or any(a > b for a, b in (source, *intervals))
    ):
        raise ValueError("Ordered exact source and nonempty coverage intervals required")
    merged: list[tuple[Fraction, Fraction]] = []
    for low, high in sorted(intervals):
        if merged and low <= merged[-1][1]:
            merged[-1] = merged[-1][0], max(high, merged[-1][1])
        else:
            merged.append((low, high))
    low, high = source
    candidates = [low, high]
    candidates.extend(min(high, max(low, (a[1] + b[0]) / 2)) for a, b in zip(merged, merged[1:]))
    return max(min(max(a - x, x - b, Fraction(0)) for a, b in merged) for x in candidates)


class BoundarySide(Enum):
    """
    Identify original finite cuts and ordered profile-end generators without relabeling sides.
    """

    LOW = 0
    HIGH = 1
    END0 = 2
    END1 = 3


@dataclass(frozen=True)
class ProfileGraph:
    """
    Own an original ellipse arc with a certified monotone q coordinate and finite b(q) Lipschitz bound.
    """

    conic: EllipseArc
    checkpoint: InitVar[Callable[[], None]]
    slope_upper: Fraction = field(init=False)
    interval: tuple[Fraction, Fraction] = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Derive graph regularity from original rational derivatives, rejecting turning or unresolved profiles.
        """
        checkpoint()
        arc = self.conic.arc
        q, b = derivative_numerators(arc)
        lower = min(q) if min(q) > 0 else -max(q) if max(q) < 0 else Fraction(0)
        if lower <= 0:
            raise ValueError("An original profile with certified monotone q required")
        ends = sorted((Fraction(arc.controls[0][0]), Fraction(arc.controls[-1][0])))
        object.__setattr__(self, "interval", (ends[0], ends[1]))
        object.__setattr__(self, "slope_upper", max(map(abs, b)) / lower)
        checkpoint()


@dataclass(frozen=True)
class FiniteBoundaryTrace:
    """
    Bound one whole native trace to its finite original side using proof witnesses only.

    The original affine inverse decodes physical s/q/b. For cut sides the
    conic derivative in b must retain one sign over the convex hull of source
    controls and decoded native controls. The mean-value theorem then bounds
    distance to the correct source graph at the nearest in-range q. Generator
    witnesses use the original nonempty s interval, including zero tips.
    These witnesses never clamp returned coordinates or change either geometry.
    """

    trace: NativeSurfaceTrace
    frame: FlatCutFrame
    graph: ProfileGraph
    side: BoundarySide
    checkpoint: InitVar[Callable[[], None]]
    forward_upper_mm: Fraction = field(init=False)
    progress_overhang_mm: Fraction = field(init=False)
    native_interval: tuple[Fraction, Fraction] = field(init=False)
    source_interval: tuple[Fraction, Fraction] = field(init=False)
    source_lipschitz: Fraction = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Derive all finite-side and progress bounds from the SAME immutable curve, source frame and profile.
        """
        checkpoint()
        if (
            not isinstance(self.side, BoundarySide)
            or self.graph.conic.arc.label != self.trace.surface.profile_label
        ):
            raise ValueError("An original owned boundary side/profile required")
        inverse = self.frame.inverse.rows
        assert inverse is not None
        numerators = tuple(
            self.trace.affine_numerator(
                row, -sum((a * b for a, b in zip(row, self.frame.origin)), Fraction(0))
            )
            for row in inverse
        )
        denominator = self.trace.denominator
        controls = tuple(tuple(n[i] / d for n in numerators) for i, d in enumerate(denominator))
        scales = tuple(sum(map(abs, col)) for col in self.frame.columns)
        if self.side in (BoundarySide.LOW, BoundarySide.HIGH):
            cut = self.frame.low if self.side is BoundarySide.LOW else self.frame.high
            source_interval = self.graph.interval
            overhang = max(
                max(source_interval[0] - p[1], p[1] - source_interval[1], Fraction(0))
                for p in controls
            )
            conic = self.graph.conic
            hull = tuple(tuple(map(Fraction, p)) for p in conic.arc.controls) + tuple(
                (p[1], p[2]) for p in controls
            )
            gradients = tuple(
                tuple(
                    2 * sum(conic.matrix[k][j] * x for j, x in enumerate((*p, Fraction(1))))
                    for k in range(2)
                )
                for p in hull
            )
            hb = [g[1] for g in gradients]
            lower = min(hb) if min(hb) > 0 else -max(hb) if max(hb) < 0 else Fraction(0)
            if lower <= 0:
                raise ValueError("The SAME nondegenerate original profile graph branch required")
            coordinates = (numerators[1], numerators[2], denominator)
            residual = (Fraction(0),)
            for i in range(3):
                for j in range(3):
                    checkpoint()
                    residual = add(
                        residual, multiply(coordinates[i], coordinates[j]), conic.matrix[i][j]
                    )
            error = _absolute(residual, multiply(denominator, denominator), checkpoint)
            b_error = (error + max(abs(g[0]) for g in gradients) * overhang) / lower
            cut_residual = add(
                add(numerators[0], numerators[1], -cut.slope), denominator, -cut.offset
            )
            s_error = _absolute(cut_residual, denominator, checkpoint) + abs(cut.slope) * overhang
            errors = s_error, overhang, b_error
            progress_axis = 1
            slope = self.graph.slope_upper
            lipschitz = max(
                abs(cut.slope) + 1 + slope,
                scales[0] * abs(cut.slope) + scales[1] + scales[2] * slope,
            )
        else:
            endpoint = self.graph.conic.arc.controls[0 if self.side is BoundarySide.END0 else -1]
            q, b = map(Fraction, endpoint)
            source_interval = self.frame.low.at(q), self.frame.high.at(q)
            if source_interval[0] > source_interval[1]:
                raise ValueError("A nonempty original finite generator required")
            overhang = max(
                max(source_interval[0] - p[0], p[0] - source_interval[1], Fraction(0))
                for p in controls
            )
            errors = (
                overhang,
                _absolute(add(numerators[1], denominator, -q), denominator, checkpoint),
                _absolute(add(numerators[2], denominator, -b), denominator, checkpoint),
            )
            progress_axis = 0
            lipschitz = max(Fraction(1), scales[0])
        forward = max(sum(errors), sum(scale * error for scale, error in zip(scales, errors)))
        ends = (
            numerators[progress_axis][0] / denominator[0],
            numerators[progress_axis][-1] / denominator[-1],
        )
        object.__setattr__(self, "forward_upper_mm", forward)
        object.__setattr__(self, "progress_overhang_mm", overhang)
        object.__setattr__(self, "native_interval", (min(ends), max(ends)))
        object.__setattr__(self, "source_interval", source_interval)
        object.__setattr__(self, "source_lipschitz", lipschitz)
        checkpoint()


@dataclass(frozen=True)
class FiniteBoundaryChain:
    """
    Bound both directions of one finite original side and its complete native trace chain.

    Continuity supplies every progress value between each trace's endpoints.
    The exact interval-union distance retains uncovered ends and split-edge
    gaps. A source-side Lipschitz bound transfers that progress gap and the
    forward witness overhang to reverse geometric and physical-label distance.
    This is boundary coverage, not filled-domain, isometry or full-path proof.
    """

    traces: tuple[FiniteBoundaryTrace, ...]
    checkpoint: InitVar[Callable[[], None]]
    coverage_gap_mm: Fraction = field(init=False)
    forward_upper_mm: Fraction = field(init=False)
    reverse_upper_mm: Fraction = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Reject foreign owners and derive one bidirectional allowance without welding missing native coverage.
        """
        checkpoint()
        if not self.traces:
            raise ValueError("A complete nonempty original boundary chain required")
        first = self.traces[0]
        if any(
            t.frame is not first.frame
            or t.graph is not first.graph
            or t.side is not first.side
            or t.trace.surface is not first.trace.surface
            for t in self.traces
        ):
            raise ValueError("The SAME native surface and original frame/profile/side required")
        gap = interval_coverage_gap(
            first.source_interval, tuple(t.native_interval for t in self.traces)
        )
        forward = max(t.forward_upper_mm for t in self.traces)
        reverse = forward + first.source_lipschitz * (
            gap + max(t.progress_overhang_mm for t in self.traces)
        )
        object.__setattr__(self, "coverage_gap_mm", gap)
        object.__setattr__(self, "forward_upper_mm", forward)
        object.__setattr__(self, "reverse_upper_mm", reverse)
        checkpoint()

    @property
    def status(self) -> str:
        """
        Require one inclusive joint material/world L1 bound in both directions of this finite side.
        """
        return (
            "within_finite_original_boundary_accuracy"
            if max(self.forward_upper_mm, self.reverse_upper_mm) <= Fraction(1, 100)
            else "unresolved_finite_original_boundary_accuracy"
        )
