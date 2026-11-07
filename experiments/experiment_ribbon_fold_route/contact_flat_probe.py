"""
Find only strictly verified flat-region penetration witnesses inside the original contact budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Callable

from .contact import Penetration, ProbeResult
from .contact_convex import Triple, dot, overlap_point, scaled
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

    def __call__(
        self,
        route: FoldRoute,
        first: int,
        second: int,
        remaining_pairs: int,
        checkpoint: Callable[[], None] | None,
    ) -> ProbeResult:
        """
        Probe complete phase hulls for at most eight GJK steps, never clear a missed pair.
        """
        if type(remaining_pairs) is not int or remaining_pairs < 0:
            raise ValueError("Supply nonnegative remaining contact work")
        if not 0 <= first < second < len(route.pieces):
            raise ValueError("Probe two distinct ordered original pieces")
        before = self.comparisons
        limit: str | None = None

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
                    bounded()
                    self.comparisons += 1
                    if any(x[1] < y[0] or y[1] < x[0] for x, y in zip(a.bounds(), b.bounds())):
                        continue
                    point = overlap_point(a, b, bounded)
                    if point is None:
                        continue
                    self.inverse_tests += 2
                    left = occupied_coordinates(
                        route.pieces[first], point, route.targets.lines, route.targets.diameter_mm
                    )
                    right = occupied_coordinates(
                        route.pieces[second], point, route.targets.lines, route.targets.diameter_mm
                    )
                    if left is not None and right is not None:
                        return ProbeResult(
                            self.comparisons - before,
                            Penetration((first, second), left, right, point),
                        )
        except _Limited:
            if limit == "pairs":
                return ProbeResult(self.comparisons - before, limit="pairs")
            return ProbeResult(self.comparisons - before, limit="supports")
        return ProbeResult(self.comparisons - before)


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
