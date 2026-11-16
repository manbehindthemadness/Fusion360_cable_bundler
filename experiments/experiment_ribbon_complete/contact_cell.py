"""
Enclose actual canonical bend and flat cells for clipped-profile contact support.

The first box coordinate is global phase for bends and physical distance for
flats. No normalized analytic-fold coordinate or inverse is substituted.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from fractions import Fraction
from functools import cached_property

from artifacts.verification.resume2998.dual import fixed, valid
from artifacts.verification.resume3011.outer import Linearization
from artifacts.verification.resume3020.support import upper as support_upper
from artifacts.verification.resume3204.polynomial import Polynomial
from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span

from .contact_profile_cover import ProfileSupportCover
from .curve_lengths import outward
from .flat_chart import FlatChart
from .spatial_frame import restrict, split_at
from .volume_field import BendVolume, Point


@dataclass(frozen=True)
class BendPreparation:
    """
    Reuse exact normal controls only within the SAME immutable canonical bend owner.

    The private memo is bounded by the original span count. It stores no cell
    remainder, separation, inverse or acceptance result. Resource checkpoints
    run on both hits and misses; another owner cannot inherit this preparation.
    """

    region: BendVolume
    _normals: dict[int, tuple[Point, ...]] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def normal(self, index: int, checkpoint: Callable[[], None]) -> tuple[Point, ...]:
        """
        Extract each requested original normal span once without changing its coefficients.
        """
        checkpoint()
        if type(index) is not int or not 0 <= index < len(self.region.source.spans):
            raise ValueError("An original canonical bend span required")
        if index not in self._normals:
            self._normals[index] = self.region.span(index).normal
        return self._normals[index]


@dataclass(frozen=True)
class ContactCell:
    """
    Bind a whole-box enclosure to its unchanged canonical owner and coordinate box.

    Residual is an exact L1 bound before float conversion; the legacy model's
    Euclidean error also includes every stored affine coefficient's conversion.
    This is positive support only, not membership, injectivity or cap ownership.
    """

    region: BendVolume | FlatChart
    box: Cell
    origin: Point
    columns: tuple[Point, ...]
    residual_mm: Fraction
    model: Linearization
    preparation: BendPreparation | None = None

    @cached_property
    def cut_models(self) -> tuple[tuple[Linearization, Cell], ...] | None:
        """
        Prepare immutable flatcut supersets once per cell; None denotes a strictly empty domain.

        Geometry, cut and box ownership are frozen on this object. Dataclass
        replacement cannot carry this memo. Normal, anchor and profile queries
        remain independent and do not retain positive contact decisions.
        """
        if not isinstance(self.region, FlatChart):
            return ()
        qlow, qhigh = Fraction(self.box.q.low), Fraction(self.box.q.high)
        slow, shigh = Fraction(self.box.u.low), Fraction(self.box.u.high)
        result = []
        for cut, sign in ((self.region.low, 1), (self.region.high, -1)):
            endpoints = cut.at(qlow), cut.at(qhigh)
            maximum = shigh - min(endpoints) if sign == 1 else max(endpoints) - slow
            if maximum < 0:
                return None
            origin = tuple(o + c * cut.offset for o, c in zip(self.origin, self.columns[0]))
            columns = (
                tuple(sign * c for c in self.columns[0]),
                tuple(c + a * cut.slope for c, a in zip(self.columns[1], self.columns[0])),
                self.columns[2],
            )
            box = Cell(
                self.box.piece,
                Span(0.0, outward(maximum, True)),
                self.box.q,
                self.box.height,
                self.box.depth,
            )
            ranges = tuple((Fraction(s.low), Fraction(s.high)) for s in (box.u, box.q, box.height))
            result.append((_floating(origin, columns, ranges, Fraction(0)), box))
        return tuple(result)


def restricted(values: Polynomial, low: Fraction, high: Fraction) -> Polynomial:
    """
    Retain the original degree on closed subintervals, including collapsed faces.
    """
    if low == high:
        return (split_at(values, low)[0][-1],) * len(values)
    return restrict(values, low, high)


def _floating(
    origin: Point,
    columns: tuple[Point, ...],
    ranges: tuple[tuple[Fraction, Fraction], ...],
    residual: Fraction,
) -> Linearization:
    """
    Charge exact affine-to-float conversion over the full box without an arbitrary guard.
    """
    vectors = tuple(Vector3(*(float(x) for x in p)) for p in (origin,) + columns)
    differences = tuple(
        sum((abs(x - Fraction(getattr(v, axis))) for x, axis in zip(p, "xyz")), Fraction(0))
        for p, v in zip((origin,) + columns, vectors)
    )
    error = (
        residual
        + differences[0]
        + sum(
            (
                max(abs(a), abs(b)) * difference
                for (a, b), difference in zip(ranges, differences[1:])
            ),
            Fraction(0),
        )
    )
    return Linearization(vectors[0], (vectors[1], vectors[2], vectors[3]), outward(error, True))


def enclose(
    region: BendVolume | FlatChart,
    box: Cell,
    checkpoint: Callable[[], None],
    *,
    preparation: BendPreparation | None = None,
) -> ContactCell:
    """
    Bound every point of the actual polynomial map on a complete closed box.

    Each original bend span is restricted exactly in phase and width. The true
    5x2x1 tensor minus an affine map has Bernstein control vectors whose maximum
    L1 norm bounds the entire residual. Multiple spans share one affine model.
    Flat domain cuts may clip a box later; enclosing its superset is safe.
    Thickness may over-enclose the physical section: the captured polynomial
    extrusion defines the same map for every finite b, so this only enlarges
    positive support. Phase and normalized width remain inside their source.
    """
    checkpoint()
    spans = box.u, box.q, box.height
    if any(not math.isfinite(x) for span in spans for x in (span.low, span.high)) or any(
        span.low > span.high for span in spans
    ):
        raise ValueError("Finite increasing closed contact box required")
    ranges = tuple((Fraction(span.low), Fraction(span.high)) for span in spans)
    if isinstance(region, FlatChart):
        if preparation is not None:
            raise ValueError("A flat chart cannot inherit bend preparation")
        model = _floating(region.origin, region.columns, ranges, Fraction(0))
        return ContactCell(region, box, region.origin, region.columns, Fraction(0), model)
    if not isinstance(region, BendVolume):
        raise ValueError("Actual canonical bend or flat owner required")
    if preparation is None:
        preparation = BendPreparation(region)
    elif preparation.region is not region:
        raise ValueError("Preparation must own the SAME original canonical bend")
    (low, high), (qlow, qhigh), (blow, bhigh) = ranges
    source = region.source
    breaks = source.surface.basis.breaks
    if not (
        breaks[0] <= low <= high <= breaks[-1]
        and -source.half_mm <= qlow <= qhigh <= source.half_mm
    ):
        raise ValueError("Box must remain inside the captured canonical bend domain")
    center = tuple((a + b) / 2 for a, b in ranges)
    u, q, b = center
    jet = region.jet(u, q, b)
    point, columns = jet.point, jet.columns
    origin = tuple(
        point[k] - sum((column[k] * x for column, x in zip(columns, center)), Fraction(0))
        for k in range(3)
    )
    residual = Fraction(0)
    vlo, vhi = ((x / source.half_mm + 1) / 2 for x in (qlow, qhigh))
    for index, (a, z) in enumerate(zip(breaks, breaks[1:])):
        if high < a or low > z:
            continue
        checkpoint()
        start: Fraction = low if low > a else a
        end: Fraction = high if high < z else z
        left, right = (start - a) / (z - a), (end - a) / (z - a)
        net = source.spans[index]
        normals = preparation.normal(index, checkpoint)
        axes = []
        normal_axes = []
        for k in range(3):
            longitudinal = tuple(
                restricted(tuple(row[j][k] for row in net), left, right) for j in range(3)
            )
            axes.append(
                tuple(
                    restricted(tuple(longitudinal[j][i] for j in range(3)), vlo, vhi)
                    for i in range(6)
                )
            )
            normal_axes.append(restricted(tuple(row[k] for row in normals), left, right))
        for i in range(6):
            phase = start + (end - start) * Fraction(i, 5)
            for j in range(3):
                width = qlow + (qhigh - qlow) * Fraction(j, 2)
                for height in (blow, bhigh):
                    error = sum(
                        (
                            abs(
                                axes[k][i][j]
                                + height * normal_axes[k][i]
                                - origin[k]
                                - columns[0][k] * phase
                                - columns[1][k] * width
                                - columns[2][k] * height
                            )
                            for k in range(3)
                        ),
                        Fraction(0),
                    )
                    residual = max(residual, error)
    model = _floating(origin, columns, ranges, residual)
    return ContactCell(region, box, origin, columns, residual, model, preparation)


def upper(
    cell: ContactCell,
    profile: ProfileSupportCover,
    normal: Vector3,
    anchor: Vector3,
) -> float | None:
    """
    Retain both original affine flat cuts through additional enclosing support queries.

    For each cut s=d+e*q, introduce nonnegative r with s=d+e*q+sign*r.
    Its box upper endpoint follows from the original s/q box. Every occupied
    point satisfies both transformed supersets. The minimum of their separate
    support bounds therefore remains enclosing, including slanted cap interiors.
    A box wholly beyond a cut is certified empty and returns negative infinity.
    """
    if profile.status != "certified_positive_support_cover":
        raise ValueError("Certified original filled-profile support cover required")
    value = support_upper(cell.model, cell.box, profile.lines, profile.diameter_mm, normal, anchor)
    prepared = cell.cut_models
    if prepared is None:
        return -math.inf
    for model, box in prepared:
        candidate = support_upper(model, box, profile.lines, profile.diameter_mm, normal, anchor)
        if candidate is not None:
            value = candidate if value is None else min(value, candidate)
    return value


def separated(
    first: ContactCell,
    second: ContactCell,
    profile: ProfileSupportCover,
    normal: Vector3,
    anchor: Vector3,
) -> bool:
    """
    Reuse positive support only after whole filled-profile compatibility is established.

    Failure is unresolved, never a penetration witness. This does not exempt
    adjacent interiors or determine legitimate shared-cap topology.
    """
    length = math.hypot(normal.x, normal.y, normal.z)
    if not math.isfinite(length) or length <= 0:
        return False
    left = upper(first, profile, normal, anchor)
    right = upper(second, profile, Vector3(-normal.x, -normal.y, -normal.z), anchor)
    if left == -math.inf or right == -math.inf:
        return True
    if left is None or right is None:
        return False
    gap = fixed(left).add(fixed(right))
    return valid(gap) and gap.high < 0
