"""
Enclose frozen cubic branch lengths with a shared, checkpointed subdivision budget.

Chord/control-polygon bounds cover each supplied cubic exactly. Dyadic subdivision
uses exact control arithmetic. This measures planned branch paths, not whatever
interpolation a native loft eventually creates, nor its material compatibility.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from fractions import Fraction

from cable_bundler.routing import RoutePreview
from cable_bundler.routing.geometry import CubicBezier

from .contracts import CompleteRibbonInput
from .lengths import BranchLength, LengthBasis, LengthEvidence

Point = tuple[Fraction, ...]
Controls = tuple[Point, ...]
Cell = tuple[Fraction, int, Controls, Fraction, Fraction]


@dataclass
class LengthWork:
    """
    Debit every created cell from one caller-sized scope, including unsuccessful refinements.

    The caller must supply its existing time/memory checkpoint. Exhaustion leaves
    a wider valid bound; it never enlarges this allocation or changes targets.
    If used during solver recovery, measurement CPU/work must also be charged to
    that same recovery allocation; this object grants no separate CPU allowance.
    """

    maximum_cells: int
    checkpoint: Callable[[], None]
    used_cells: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        """
        Refuse an absent, zero or ambiguous work allocation before measuring any curve.
        """
        if type(self.maximum_cells) is not int or self.maximum_cells <= 0:
            raise ValueError("A positive fixed cell allocation is required")

    def claim(self, count: int) -> None:
        """
        Check the shared resource guard and charge new cells without refunds.
        """
        if type(count) is not int or count <= 0:
            raise ValueError("A cell debit must be a positive integer")
        self.checkpoint()
        if self.used_cells + count > self.maximum_cells:
            raise RuntimeError(
                "Planned length cell allocation exhausted before route initialization"
            )
        self.used_cells += count


@dataclass(frozen=True)
class CurveLength:
    """
    Retain a conservative planned-length range even when the requested width is unresolved.
    """

    length: LengthEvidence
    cells: int
    leaves: int
    resolution_reached: bool


def controls(curve: CubicBezier) -> Controls:
    """
    Freeze the exact supplied finite binary control coordinates, without fitting the path.
    """
    output = []
    for point in (curve.start, curve.control_a, curve.control_b, curve.end):
        values = (point.x, point.y, point.z)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Planned branch controls must be finite")
        output.append(tuple(Fraction(value) for value in values))
    return tuple(output)


def distance(a: Point, b: Point) -> tuple[Fraction, Fraction]:
    """
    Enclose a Euclidean distance with integer square roots on a fixed dyadic grid.

    Forty fractional bits bound arithmetic uncertainty without any floating sqrt
    assumption. This is constant arithmetic precision, not a dimensional acceptance
    gate or a geometry-refinement target below the user's0.01mm policy.
    """
    squared = sum(((x - y) ** 2 for x, y in zip(a, b)), Fraction())
    scale = 1 << 40
    integer = math.isqrt(squared.numerator * scale**2 // squared.denominator)
    low = Fraction(integer, scale)
    high = low if low**2 == squared else Fraction(integer + 1, scale)
    return low, high


def bounds(points: Controls) -> tuple[Fraction, Fraction]:
    """
    Bound one polynomial Bezier segment by its endpoint chord and complete control polygon.
    """
    return distance(points[0], points[-1])[0], sum(
        (distance(a, b)[1] for a, b in zip(points, points[1:])), Fraction()
    )


def split(points: Controls) -> tuple[Controls, Controls]:
    """
    Bisect one exact polynomial segment by de Casteljau, sharing its exact seam point.
    """
    levels = [points]
    while len(levels[-1]) > 1:
        levels.append(
            tuple(
                tuple((x + y) / 2 for x, y in zip(a, b)) for a, b in zip(levels[-1], levels[-1][1:])
            )
        )
    return tuple(level[0] for level in levels), tuple(level[-1] for level in reversed(levels))


def outward(value: Fraction, upper: bool) -> float:
    """
    Serialize a rational enclosure endpoint without rounding it inward.
    """
    result = float(value)
    rounded = Fraction(result)
    inward = rounded < value if upper else rounded > value
    if inward:
        result = math.nextafter(result, math.inf if upper else -math.inf)
    return result


def enclose_segments(
    segments: tuple[Controls, ...],
    work: LengthWork,
    receipt: str,
    *,
    maximum_width_mm: float = 0.01,
) -> CurveLength:
    """
    Enclose a sum of exact constant-through-quintic segments under one shared allocation.

    Stop at the requested measurement width or the shared cell allocation. Even
    an exhausted result is an enclosure, although the allowance decision can stay
    unresolved. Gaps, tangent continuity, native interpolation and local material
    increments require their separate audits; no connecting segment is invented.
    """
    if (
        not segments
        or any(
            not 1 <= len(segment) <= 6
            or any(
                len(point) != 3 or any(type(x) is not Fraction for x in point) for point in segment
            )
            for segment in segments
        )
        or type(maximum_width_mm) not in (int, float)
        or not math.isfinite(maximum_width_mm)
        or maximum_width_mm <= 0
        or not isinstance(receipt, str)
        or not receipt.strip()
    ):
        raise ValueError(
            "Exact three-dimensional polynomial segments and a positive measurement width required"
        )
    started = work.used_cells
    work.claim(len(segments))
    pending: list[Cell] = []
    lower, upper = Fraction(), Fraction()
    serial = 0
    for points in segments:
        work.checkpoint()
        low, high = bounds(points)
        heapq.heappush(pending, (low - high, serial, points, low, high))
        lower, upper = lower + low, upper + high
        serial += 1
    goal = Fraction(maximum_width_mm)
    while upper - lower > goal and work.used_cells + 2 <= work.maximum_cells:
        work.claim(2)
        _, _, parent, old_low, old_high = heapq.heappop(pending)
        lower, upper = lower - old_low, upper - old_high
        for child in split(parent):
            low, high = bounds(child)
            heapq.heappush(pending, (low - high, serial, child, low, high))
            serial += 1
            lower, upper = lower + low, upper + high
    evidence = LengthEvidence(
        outward(lower, False), outward(upper, True), LengthBasis.ENCLOSURE, receipt
    )
    emitted_low, emitted_high = evidence.bounds
    return CurveLength(
        evidence,
        work.used_cells - started,
        len(pending),
        emitted_high - emitted_low <= goal,
    )


def enclose_route(
    route: RoutePreview,
    work: LengthWork,
    receipt: str,
    *,
    maximum_width_mm: float = 0.01,
) -> CurveLength:
    """
    Measure the unchanged cubic preview through the shared exact polynomial implementation.

    These receipts describe preview geometry only. They cannot automatically
    transfer to a spatial branch whose frame fields differ from that preview.
    """
    return enclose_segments(
        tuple(controls(curve) for curve in route.curves),
        work,
        receipt,
        maximum_width_mm=maximum_width_mm,
    )


def iter_branch_lengths(
    plan: CompleteRibbonInput, work: LengthWork, receipt_prefix: str
) -> Iterator[tuple[BranchLength, CurveLength]]:
    """
    Yield unchanged routes' measurements in explicit order under one aggregate allocation.

    Callers can preserve each yielded receipt immediately. A later resource stop
    propagates without losing that prefix or silently skipping the unattempted tail.
    """
    if not isinstance(receipt_prefix, str) or not receipt_prefix.strip():
        raise ValueError("Planned branch measurements require an explicit evidence origin")
    for branch in plan.branches:
        work.checkpoint()
        route = branch.source.route
        result = enclose_route(route, work, f"{receipt_prefix}/route/{route.cable_id}")
        yield BranchLength(route, result.length), result
