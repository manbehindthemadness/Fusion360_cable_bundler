"""
Propose strictly verified flat witnesses or one untrusted axis inside the original contact budget.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cached_property
from typing import Callable, Iterator

from cable_bundler.routing.geometry import Vector3

from .contact import Penetration, ProbeResult
from .contact_convex import Triple, dot, overlap_point, scaled, subtract, triple
from .contact_flat_geometry import FlatPhase, Shape, profile_arcs, shapes
from .contact_inverse import occupied_coordinates
from .geometry import FoldRoute


class _Limited(RuntimeError):
    """
    Stop optional probe work without catching caller cancellation or source/resource errors.
    """


@dataclass
class FlatProbe:
    """
    Own counters and at most2048constituent support queries for one optional certificate.
    """

    comparisons: int = 0
    supports: int = 0
    inverse_tests: int = 0
    skipped_phase_pairs: int = 0

    def __call__(
        self,
        route: FoldRoute,
        first: int,
        second: int,
        remaining_pairs: int,
        checkpoint: Callable[[], None] | None,
        *,
        excluded_phases: frozenset[tuple[FlatPhase, FlatPhase]] = frozenset(),
    ) -> ProbeResult:
        """
        Probe phase hulls, refining unoccupied proposals by exact profile arcs within the same limits.

        Whole-phase convex hulls can span empty profile valleys. Only when an
        overlap proposal fails strict material inversion, compare constituent
        arc hulls near its affine width coordinate. Every compared pair and
        support query shares the original allowance; no miss grants clearance.
        A normal miss may retain one already-computed direction for the full
        material interval checker. It adds no support query or clearance receipt.
        Per-call exclusions omit only named phase pairs from this negative probe,
        before any hull support work. They never persist into another call or
        change the caller's complete material interval certificate.
        """
        if type(remaining_pairs) is not int or remaining_pairs < 0:
            raise ValueError("Supply nonnegative remaining contact work")
        if not 0 <= first < second < len(route.pieces):
            raise ValueError("Probe two distinct ordered original pieces")
        before = self.comparisons
        limit: str | None = None
        axis_candidate: Vector3 | None = None

        def propose(direction: Triple) -> None:
            """
            Retain at most one finite direction without querying geometry again.
            """
            nonlocal axis_candidate
            length = math.hypot(*direction)
            if axis_candidate is None and math.isfinite(length) and length > 0:
                axis_candidate = Vector3(*(value / length for value in direction))

        def bounded() -> None:
            """
            Share every compared hull pair and constituent query with the caller's limits.
            """
            nonlocal limit
            if checkpoint is not None:
                checkpoint()
            if self.comparisons - before >= remaining_pairs:
                limit = "pairs"
                raise _Limited()
            if self.supports >= 2048:
                limit = "supports"
                raise _Limited()

        def query() -> None:
            """
            Charge every circular-profile extremum, including broad-phase preparation.
            """
            bounded()
            self.supports += 1

        def verify(world_point: Vector3) -> Penetration | None:
            """
            Require the unchanged actual strict inverse maps for every proposed world point.
            """
            self.inverse_tests += 2
            first_coordinates = occupied_coordinates(
                route.pieces[first], world_point, route.targets.lines, route.targets.diameter_mm
            )
            second_coordinates = occupied_coordinates(
                route.pieces[second], world_point, route.targets.lines, route.targets.diameter_mm
            )
            return (
                None
                if first_coordinates is None or second_coordinates is None
                else Penetration(
                    (first, second), first_coordinates, second_coordinates, world_point
                )
            )

        try:
            arcs = profile_arcs(route.targets.lines, route.targets.diameter_mm)
            hulls = []
            for piece_index in (first, second):
                groups: dict[FlatPhase, list[Shape]] = {}
                for shape in shapes(route.pieces[piece_index], arcs):
                    groups.setdefault(shape.placement.phase, []).append(shape)
                hulls.append([_Hull(tuple(members), query) for members in groups.values()])
            for a in hulls[0]:
                for b in hulls[1]:
                    phases = (a.members[0].placement.phase, b.members[0].placement.phase)
                    if phases in excluded_phases:
                        if checkpoint is not None:
                            checkpoint()
                        self.skipped_phase_pairs += 1
                        continue
                    bounded()
                    self.comparisons += 1
                    if any(x[1] < y[0] or y[1] < x[0] for x, y in zip(a.bounds(), b.bounds())):
                        continue
                    point = overlap_point(a, b, bounded, on_axis_proposal=propose)
                    if point is None:
                        continue
                    witness = verify(point)
                    if witness is not None:
                        return ProbeResult(self.comparisons - before, witness)
                    for left, right in _profile_pairs(a, b, point, query):
                        bounded()
                        self.comparisons += 1
                        bounds = tuple(zip(left.bounds(), right.bounds()))
                        if any(x[1] < y[0] or y[1] < x[0] for x, y in bounds):
                            continue
                        center = Vector3(
                            *((max(x[0], y[0]) + min(x[1], y[1])) / 2 for x, y in bounds)
                        )
                        witness = verify(center)
                        if witness is None:
                            proposal = overlap_point(left, right, bounded, on_axis_proposal=propose)
                            if proposal is not None:
                                witness = verify(proposal)
                        if witness is not None:
                            return ProbeResult(self.comparisons - before, witness)
        except _Limited:
            if limit == "pairs":
                return ProbeResult(self.comparisons - before, limit="pairs")
            return ProbeResult(self.comparisons - before, limit="supports")
        return ProbeResult(self.comparisons - before, axis_proposal=axis_candidate)


def _profile_pairs(
    first: _Hull, second: _Hull, point: Vector3, query: Callable[[], None]
) -> Iterator[tuple[_Hull, _Hull]]:
    """
    Visit nearby arc combinations first without allocating a quadratic candidate list.

    The width coordinate only orders negative proposals. It never narrows the
    positive interval proof or changes the actual joined-profile geometry.
    """

    def ordered(hull: _Hull) -> tuple[_Hull, ...]:
        """
        Rank exact profile strips by distance from the failed proposal in their affine frame.
        """
        placement = hull.members[0].placement
        coordinate = dot(subtract(triple(point), placement.origin), placement.width)
        members = sorted(
            hull.members,
            key=lambda shape: (
                max(shape.arc.low_q - coordinate, 0.0, coordinate - shape.arc.high_q),
                abs((shape.arc.low_q + shape.arc.high_q) / 2 - coordinate),
            ),
        )
        return tuple(_Hull((member,), query) for member in members)

    left, right = ordered(first), ordered(second)
    for rank in range(len(left) + len(right) - 1):
        for index in range(max(0, rank - len(right) + 1), min(rank + 1, len(left))):
            yield left[index], right[rank - index]


@dataclass(frozen=True)
class _Hull:
    """
    Retain a support-only phase hull, which can include empty profile valleys.
    """

    members: tuple[Shape, ...]
    checkpoint: Callable[[], None]

    @property
    def origin(self) -> Triple:
        """
        Return the shared affine material origin used by the bounded convex probe.
        """
        return self.members[0].origin

    def support(self, direction: Triple) -> Triple:
        """
        Return one constituent extremum while accounting every queried circular profile.
        """
        points = []
        for member in self.members:
            self.checkpoint()
            points.append(member.support(direction))
        return max(points, key=lambda point: dot(point, direction))

    def bounds(self) -> tuple[tuple[float, float], ...]:
        """
        Enclose this optional hull in three world-coordinate intervals.
        """
        return self._bounds

    @cached_property
    def _bounds(self) -> tuple[tuple[float, float], ...]:
        """
        Reuse six immutable broad-phase hull queries within this one optional probe call.
        """
        axes: tuple[Triple, ...] = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        return tuple(
            (
                dot(self.support(scaled(axis, -1)), axis) - 1e-10,
                dot(self.support(axis), axis) + 1e-10,
            )
            for axis in axes
        )
