"""
Certify whole material cells against finite hardware using conservative additional axes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import Vector3, cross, magnitude, unit
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, prepare_projection
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece

from .model import Box


def _dot_enclosure(first: Vector3, second: Vector3) -> Span:
    """
    Enclose the real dot product of stored floating coordinates with outward arithmetic.
    """
    result = Span(0.0, 0.0)
    for coordinate in "xyz":
        value = getattr(first, coordinate)
        result = result.add(Span(value, value).scale(getattr(second, coordinate)))
    return result


@dataclass(frozen=True)
class BoxProjection:
    """
    Enclose coordinate-defined box slabs despite floating frame nonorthogonality.

    The Gram error bounds the difference between slab coordinates and coordinates
    along the stored frame vectors. Enlarging each interval by that derived bound
    is conservative; it grants no geometric clearance tolerance. Instances belong
    to one immutable hardware check, never a global geometry cache.
    """

    origin: Vector3
    axes: tuple[Vector3, Vector3, Vector3]
    bounds: tuple[Span, ...]

    @classmethod
    def create(cls, box: Box) -> BoxProjection | None:
        """
        Bound the inverse Gram correction, declining nonfinite or uncertain frames.

        For G=I+E with ||E||inf<1, ||G^-1-I||inf is bounded by
        ||E||inf/(1-||E||inf). Apply that bound to every original slab interval
        before projecting along any requested direction.
        """
        axes = box.axes
        errors = []
        for i, first in enumerate(axes):
            terms = []
            for j, second in enumerate(axes):
                product = _dot_enclosure(first, second)
                expected = float(i == j)
                terms.append(
                    math.nextafter(
                        max(abs(product.low - expected), abs(product.high - expected)), math.inf
                    )
                )
            errors.append(math.nextafter(math.fsum(terms), math.inf))
        epsilon = max(errors)
        reach = max(max(abs(span.low), abs(span.high)) for span in box.bounds)
        if not math.isfinite(epsilon) or not math.isfinite(reach) or epsilon >= 1:
            return None
        denominator = math.nextafter(1 - epsilon, -math.inf)
        if denominator <= 0:
            return None
        dilation = math.nextafter(math.nextafter(epsilon * reach, math.inf) / denominator, math.inf)
        if not math.isfinite(dilation):
            return None
        bounds = tuple(
            Span(
                math.nextafter(span.low - dilation, -math.inf),
                math.nextafter(span.high + dilation, math.inf),
            )
            for span in box.bounds
        )
        return cls(box.pose.origin, axes, bounds)

    def span(self, axis: Vector3) -> Span | None:
        """
        Outward-enclose the full slab solid on one axis; uncertain arithmetic proves nothing.
        """
        if not all(math.isfinite(getattr(axis, coordinate)) for coordinate in "xyz"):
            return None
        result = _dot_enclosure(self.origin, axis)
        for frame, limit in zip(self.axes, self.bounds):
            result = result.add(limit.multiply(_dot_enclosure(frame, axis)))
        return result if math.isfinite(result.low) and math.isfinite(result.high) else None


def separated_on_piece_axes(
    piece: PlacedPiece,
    cell: Cell,
    hardware: BoxProjection,
    checkpoint: Callable[[], None] | None = None,
) -> bool:
    """
    Prove strict disjointness on three piece axes and nine box/piece cross products.

    Use the unchanged full thick-material enclosure. Skip degenerate axes and
    nonfinite projections. No returned proof means only that subdivision or
    witness measurement is still required. Extra projections do not evict the
    caller's existing material-cell cache; cancellation propagates on each axis.
    """
    local = (
        piece.pose.tangent,
        piece.pose.width,
        cross(piece.pose.tangent, piece.pose.width),
    )
    candidates = local + tuple(cross(first, second) for first in hardware.axes for second in local)
    for raw in candidates:
        if checkpoint is not None:
            checkpoint()
        if magnitude(raw) < 1e-10:
            continue
        axis = unit(raw)
        box_span = hardware.span(axis)
        if box_span is None:
            continue
        material = prepare_projection(piece, axis)(cell)
        if not math.isfinite(material.low) or not math.isfinite(material.high):
            continue
        if material.high < box_span.low or material.low > box_span.high:
            return True
    return False
