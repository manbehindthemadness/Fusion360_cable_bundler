"""
Prepare affine flat-phase cores for strictly verified negative witness proposals.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from functools import cached_property, lru_cache
from typing import Callable

from .contact_convex import Triple
from .contact_core import core_dimensions
from .contact_flat_geometry import FlatPhase, FlatRegion, region
from .geometry import PlacedPiece


class PrismKind(Enum):
    """
    Select an inscribed valley or nominal-width full-lobe-height proposal, never clearance.
    """

    VALLEY = "valley"
    LOBE_HEIGHT = "lobe_height"


def _dot(first: Triple, second: Triple) -> float:
    """
    Accumulate a clipping-plane scalar product without discarding cancelling terms.
    """
    return math.fsum(a * b for a, b in zip(first, second))


@dataclass(frozen=True)
class FlatCore:
    """
    Extrude an original affine material polygon through one declared proposal height.

    Numerical phase clipping supplies proposals only. Strict actual inverse maps
    remain authoritative even at a phase boundary. Instances are prepared from
    at most five polygon vertices; no material or clearance result is retained.
    """

    placement: FlatRegion
    half_height: float

    def _world(self, along: float, across: float, height: float) -> Triple:
        """
        Apply the original phase's rigid material placement.
        """
        p = self.placement
        return (
            p.origin[0] + along * p.tangent[0] + across * p.width[0] + height * p.normal[0],
            p.origin[1] + along * p.tangent[1] + across * p.width[1] + height * p.normal[1],
            p.origin[2] + along * p.tangent[2] + across * p.width[2] + height * p.normal[2],
        )

    def local(self, point: Triple) -> Triple:
        """
        Express one world point in this same orthonormal affine material frame.
        """
        p = self.placement
        relative = point[0] - p.origin[0], point[1] - p.origin[1], point[2] - p.origin[2]
        return _dot(relative, p.tangent), _dot(relative, p.width), _dot(relative, p.normal)

    @cached_property
    def planes(self) -> tuple[tuple[Triple, float], ...]:
        """
        Retain the oriented polygon halfplanes and the two profile-core height planes.
        """
        polygon = self.placement.polygon
        sides: list[tuple[Triple, float]] = []
        for first, second in zip(polygon, polygon[1:] + polygon[:1]):
            ds, dq = second[0] - first[0], second[1] - first[1]
            sides.append(((dq, -ds, 0.0), dq * first[0] - ds * first[1]))
        return tuple(sides) + (
            ((0.0, 0.0, 1.0), self.half_height),
            ((0.0, 0.0, -1.0), self.half_height),
        )

    @cached_property
    def _vertices(self) -> tuple[tuple[Triple, ...], tuple[Triple, ...]]:
        """
        Prepare at most ten world vertices once for bounds and any later edge clipping.
        """
        polygon = self.placement.polygon
        bottom = tuple(self._world(*point, -self.half_height) for point in polygon)
        top = tuple(self._world(*point, self.half_height) for point in polygon)
        return bottom, top

    @property
    def vertices(self) -> tuple[Triple, ...]:
        """
        Expose the same immutable bottom/top vertex order without another preparation or cache.
        """
        bottom, top = self._vertices
        return bottom + top

    @cached_property
    def bounds(self) -> tuple[tuple[float, float], ...]:
        """
        Bound this proposal prism outward in world axes, without bounding actual full material.

        These bounds may skip only spatially disjoint negative proposals. They
        supply neither contact clearance nor a separating axis to the full proof.
        """
        points = self.vertices
        return tuple(
            (
                math.nextafter(min(point[i] for point in points), -math.inf),
                math.nextafter(max(point[i] for point in points), math.inf),
            )
            for i in range(3)
        )

    @cached_property
    def edges(self) -> tuple[tuple[Triple, Triple], ...]:
        """
        Retain at most fifteen immutable edges of this clipped flat-phase prism.
        """
        polygon = self.placement.polygon
        bottom, top = self._vertices
        edges: list[tuple[Triple, Triple]] = []
        for i in range(len(polygon)):
            following = (i + 1) % len(polygon)
            edges.extend(
                ((bottom[i], bottom[following]), (top[i], top[following]), (bottom[i], top[i]))
            )
        return tuple(edges)


def prepare(
    piece: PlacedPiece,
    phase: FlatPhase,
    lines: int,
    diameter: float,
    kind: PrismKind = PrismKind.VALLEY,
) -> FlatCore | None:
    """
    Prepare one nominal-width prism, declining an empty or degenerate flat polygon.

    Before/after phase cuts retain their actual bank dependence. The common
    valley excludes lobe bulges; the lobe-height envelope includes empty valleys.
    Both exclude side extensions. Neither supplies material occupancy or clearance.
    The supplied phase must belong to the actual piece kind.
    """
    half_width, half_height = core_dimensions(lines, diameter)
    if not isinstance(kind, PrismKind):
        raise ValueError("Use an explicit flat-prism proposal kind")
    if kind is PrismKind.LOBE_HEIGHT:
        half_height = diameter / 2
    placement = region(piece, phase, -half_width, half_width)
    polygon = placement.polygon
    if len(polygon) < 3:
        return None
    if len(polygon) > 5:
        raise ArithmeticError("A rectangular material phase acquired extra polygon edges")
    area = math.fsum(
        first[0] * second[1] - second[0] * first[1]
        for first, second in zip(polygon, polygon[1:] + polygon[:1])
    )
    if not math.isfinite(area) or area <= 0:
        return None
    return FlatCore(placement, half_height)


class CorePreparations:
    """
    Own at most sixty-four immutable prism preparations across kinds, retaining no results.
    """

    def __init__(self) -> None:
        """
        Bind one exact geometry factory to this discovery context alone.
        """
        self._prepared = lru_cache(maxsize=64)(prepare)

    def __call__(
        self,
        piece: PlacedPiece,
        phase: FlatPhase,
        lines: int,
        diameter: float,
        kind: PrismKind = PrismKind.VALLEY,
    ) -> FlatCore | None:
        """
        Reuse only identical placed material, phase, profile dimensions and proposal kind.
        """
        return self._prepared(piece, phase, lines, diameter, kind)

    def statistics(self) -> dict[str, int]:
        """
        Report preparation work and retained size, independently of witness outcomes.
        """
        info = self._prepared.cache_info()
        return {
            "hits": info.hits,
            "preparations": info.misses,
            "retained": info.currsize,
            "capacity": 64,
        }


def height_separated(first: FlatCore, second: FlatCore, checkpoint: Callable[[], None]) -> bool:
    """
    Reject only complete proposal prisms strictly separated by an existing height plane.

    Project every vertex of the opposing convex prism into the same local
    height coordinate used by edge clipping. A conservative floating padding
    defers near-boundary cases to the unchanged clipper. Nonfinite or overflowed
    data also declines this accelerator. No actual material bounds, occupancy
    or clearance follow from a rejected negative proposal; final strict inverse
    witnesses and the complete positive contact proof remain authoritative.
    Use only the existing at-most-ten prepared vertices, without another cache.
    Caller checkpoints propagate cancellation before each bounded normal test.
    """
    for own, other in ((first, second), (second, first)):
        checkpoint()
        placement = own.placement
        if (
            not math.isfinite(own.half_height)
            or own.half_height <= 0
            or any(not math.isfinite(v) for v in placement.origin + placement.normal)
        ):
            return False
        vertices = other.vertices
        if not vertices:
            return False
        projections: list[float] = []
        maximum_size = 0.0
        for point in vertices:
            relative = (
                point[0] - placement.origin[0],
                point[1] - placement.origin[1],
                point[2] - placement.origin[2],
            )
            size = sum(abs(a) + abs(b) for a, b in zip(point, placement.origin))
            if not math.isfinite(size) or any(not math.isfinite(v) for v in relative):
                return False
            projection = _dot(relative, placement.normal)
            if not math.isfinite(projection):
                return False
            projections.append(projection)
            maximum_size = max(maximum_size, size)
        guard = 1e-11 * (1 + own.half_height + maximum_size)
        if not math.isfinite(guard):
            return False
        if (
            min(projections) > own.half_height + guard
            or max(projections) < -own.half_height - guard
        ):
            return True
    return False


def intersection_vertices(
    first: FlatCore, second: FlatCore, visit_edge: Callable[[], None]
) -> tuple[Triple, ...]:
    """
    Clip both prisms' existing edges to the opposing halfplanes for one negative proposal.

    Visit at most thirty edges and retain at most sixty endpoints. Caller work
    and cancellation checks run before each edge. Near-parallel or empty misses
    have no clearance authority; final strict material inverses are independent.
    """
    points: list[Triple] = []
    for source, other in ((first, second), (second, first)):
        for start, end in source.edges:
            visit_edge()
            origin, stop = other.local(start), other.local(end)
            direction = stop[0] - origin[0], stop[1] - origin[1], stop[2] - origin[2]
            low, high = 0.0, 1.0
            for normal, right in other.planes:
                value, slope = _dot(normal, origin), _dot(normal, direction)
                if abs(slope) < 1e-14:
                    if value > right:
                        low, high = 1.0, 0.0
                        break
                elif slope > 0:
                    high = min(high, (right - value) / slope)
                else:
                    low = max(low, (right - value) / slope)
            if low <= high:
                for t in (low, high):
                    points.append(
                        (
                            start[0] + t * (end[0] - start[0]),
                            start[1] + t * (end[1] - start[1]),
                            start[2] + t * (end[2] - start[2]),
                        )
                    )
    return tuple(points)
