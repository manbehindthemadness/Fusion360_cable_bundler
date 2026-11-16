"""
Measure corresponding conductor paths in the actual stored C2 bend midsurface.

This covers captured b=0 bend fields only. Straight regions, junction label
correspondence, full-volume validity and native material correspondence do not
follow from these measurements. No whole-trunk declaration is manufactured.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction

from artifacts.verification.resume3216.field import Midsurface
from artifacts.verification.resume3217.extraction import Net, tensor

from .curve_lengths import Controls, distance
from .root_profiles import RootProfile
from .spatial_frame import split_at


@dataclass(frozen=True)
class MidplaneSource:
    """
    Retain the original captured field and exact extracted spans under explicit provenance.

    The caller establishes capture hashes and input ownership. A receipt string
    alone is not a geometry or native certificate. Half width maps q to the
    original unit V coordinate; it does not move any control or material label.
    """

    surface: Midsurface
    half_mm: Fraction
    receipt: str
    checkpoint: InitVar[Callable[[], None]]
    spans: tuple[Net, ...] = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Derive spans from their actual owner, so replacement cannot carry stale extraction.
        """
        checkpoint()
        if (
            type(self.half_mm) is not Fraction
            or self.half_mm <= 0
            or not isinstance(self.receipt, str)
            or not self.receipt.strip()
        ):
            raise ValueError("An exact positive captured half width and provenance are required")
        spans = []
        for index in range(len(self.surface.basis.breaks) - 1):
            checkpoint()
            spans.append(tensor(self.surface, index))
        object.__setattr__(self, "spans", tuple(spans))


def prepare(
    surface: Midsurface,
    half_mm: Fraction,
    receipt: str,
    checkpoint: Callable[[], None],
) -> MidplaneSource:
    """
    Extract each original quintic span exactly once without regenerating rounded controls.
    """
    return MidplaneSource(surface, half_mm, receipt, checkpoint)


def labels(root: RootProfile) -> tuple[Fraction, Fraction, Fraction]:
    """
    Resolve ordered midplane extrema and the original lobe center from the unchanged root.

    Current partition edges have one thickness sign or a symmetric monotone
    midplane crossing. Unsupported edges reject rather than losing a crossing.
    The lobe center is the top/bottom middle-control q, not the midpoint of
    asymmetric outer-lobe partition extrema.
    """
    candidates = []
    centers = []
    for edge in root.edges:
        arc = edge.geometry
        if (
            len(arc.controls) != 3
            or len(arc.weights) != 3
            or any(weight <= 0 for weight in arc.weights)
        ):
            raise ValueError("Original positive-weight quadratic root edges required")
        rows = tuple(
            (Fraction(q) * Fraction(w), Fraction(b) * Fraction(w), Fraction(w))
            for (q, b), w in zip(arc.controls, arc.weights)
        )
        thickness = tuple(p[1] for p in rows)
        if not any(thickness):
            raise ValueError("A midplane boundary segment needs an explicit label contract")
        parameters = [Fraction(i) for i in (0, 1) if thickness[2 * i] == 0]
        if min(thickness) < 0 < max(thickness):
            derivative = (thickness[1] - thickness[0], thickness[2] - thickness[1])
            if split_at(thickness, Fraction(1, 2))[0][-1] != 0 or not (
                min(derivative) > 0 or max(derivative) < 0
            ):
                raise ValueError("Unsupported original root midplane crossing")
            parameters.append(Fraction(1, 2))
        for parameter in parameters:
            q, _, w = tuple(split_at(tuple(p[k] for p in rows), parameter)[0][-1] for k in range(3))
            candidates.append(q / w)
        if arc.label in (f"top-{root.pin_number - 1}", f"bottom-{root.pin_number - 1}"):
            centers.append(Fraction(arc.controls[1][0]))
    if len(centers) != 2 or centers[0] != centers[1] or not candidates:
        raise ValueError("Original matching top/bottom conductor center labels required")
    left, center, right = min(candidates), centers[0], max(candidates)
    if not left < center < right:
        raise ValueError("Root midplane extrema must bracket their original lobe center")
    return left, center, right


def path(net: Net, coordinate: Fraction) -> Controls:
    """
    Restrict the actual quadratic transverse tensor at one exact unit source coordinate.
    """
    if type(coordinate) is not Fraction or not 0 <= coordinate <= 1:
        raise ValueError("An exact original unit transverse coordinate required")
    return tuple(
        tuple(split_at(tuple(p[k] for p in row), coordinate)[0][-1] for k in range(3))
        for row in net
    )


def discrepancy(left: Controls, right: Controls, checkpoint: Callable[[], None]) -> Fraction:
    """
    Bound integral abs(speed_left-speed_right) on a shared local unit span.

    Reverse triangle inequality bounds speed difference by velocity difference.
    Convexity then bounds its integral by the average norms of the Bernstein
    derivative controls. Local derivatives include span scaling exactly once.
    This covers every subinterval without cancellation or a positive-speed
    denominator. Regularity and material correspondence remain separate gates.
    """
    checkpoint()
    if (
        len(left) != len(right)
        or len(left) != 6
        or any(len(p) != 3 or any(type(x) is not Fraction for x in p) for p in left + right)
    ):
        raise ValueError("Two exact three-dimensional quintic control curves required")
    offsets = tuple(tuple(a - b for a, b in zip(p, q)) for p, q in zip(left, right))
    # Degree cancels the integral of each degree-four Bernstein basis function.
    return sum((distance(a, b)[1] for a, b in zip(offsets, offsets[1:])), Fraction(0))


@dataclass(frozen=True)
class MidplanePathSpan:
    """
    Preserve exact three-path controls and separate center-relative increment bounds.
    """

    low: Fraction
    high: Fraction
    curves: tuple[Controls, ...]
    left_upper_mm: Fraction
    right_upper_mm: Fraction


@dataclass(frozen=True)
class MidplanePathAudit:
    """
    Retain one conductor's bend measurement without clearing any complete-output gate.
    """

    source: MidplaneSource
    root: RootProfile
    q_mm: tuple[Fraction, Fraction, Fraction]
    spans: tuple[MidplanePathSpan, ...]
    pairwise_upper_mm: Fraction


def measure(
    source: MidplaneSource, root: RootProfile, checkpoint: Callable[[], None]
) -> MidplanePathAudit:
    """
    Accumulate one bend's corresponding-path discrepancies across all original spans.

    Preserve source/root identity and the exact labels for later junction binding.
    No per-span 0.01mm allowance, subdivision, fitting or independent work pool is
    introduced. The caller's checkpoint owns all resource/time stopping. Source
    extraction must be the unchanged result of prepare, not a rebuilt field.
    """
    checkpoint()
    q = labels(root)
    coordinates = tuple((value / source.half_mm + 1) / 2 for value in q)
    if (
        any(not 0 <= value <= 1 for value in coordinates)
        or len(source.spans) != len(source.surface.basis.breaks) - 1
    ):
        raise ValueError("Complete original span coverage and in-domain root labels required")
    output = []
    total = Fraction(0)
    for index, net in enumerate(source.spans):
        checkpoint()
        curves = tuple(path(net, coordinate) for coordinate in coordinates)
        low, high = source.surface.basis.breaks[index : index + 2]
        if output and any(a[-1] != b[0] for a, b in zip(output[-1].curves, curves)):
            raise ValueError("Captured paths must share exact original span junctions")
        left = discrepancy(curves[0], curves[1], checkpoint)
        right = discrepancy(curves[2], curves[1], checkpoint)
        total += left + right
        output.append(MidplanePathSpan(low, high, curves, left, right))
    return MidplanePathAudit(source, root, q, tuple(output), total)
