"""
Propose one bounded affine-cell intersection point without granting material clearance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product
from typing import Callable, Optional

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, unit

from .contact_bounds import Cell, Span
from .geometry import FoldRoute, PlacedPiece, Pose, Straight

Coordinates = tuple[float, float, float]
Occupied = Callable[[int, Vector3], Optional[Coordinates]]
Witness = tuple[Coordinates, Coordinates, Vector3]


@dataclass(frozen=True)
class _Frame:
    """
    Describe an affine proposal frame, never a replacement for actual material inversion.
    """

    origin: Vector3
    tangent: Vector3
    width: Vector3
    normal: Vector3
    length: float

    def point(self, coordinates: Coordinates) -> Vector3:
        """
        Place a material-box point in this fixed flat frame.
        """
        u, q, height = coordinates
        return (
            self.origin.translated(self.tangent, u * self.length)
            .translated(self.width, q)
            .translated(self.normal, height)
        )

    def coordinates(self, point: Vector3) -> Coordinates:
        """
        Supply the original near-orthogonal material-frame coordinates for proposal clipping only.
        """
        relative = difference(point, self.origin)
        return (
            dot(relative, self.tangent) / self.length,
            dot(relative, self.width),
            dot(relative, self.normal),
        )


def _frame(piece: PlacedPiece, cell: Cell) -> _Frame | None:
    """
    Decline curved or uncertain phases using an outward enclosure of every material corner.
    """
    pose = piece.pose
    length = piece.geometry.material_length_mm
    if not isinstance(piece.geometry, Straight):
        fold = piece.geometry
        along = cell.u.scale(length).add(Span(-fold.before_mm, -fold.before_mm))
        xi = along.scale(math.cos(fold.bank_radians)).add(cell.q.scale(math.sin(fold.bank_radians)))
        if xi.high <= 0:
            pass
        elif xi.low >= fold.radius_mm * abs(fold.angle_radians):
            pose = piece.end_pose()
            pose = Pose(pose.origin.translated(pose.tangent, -length), pose.tangent, pose.width)
        else:
            return None
    return _Frame(
        pose.origin, pose.tangent, pose.width, unit(cross(pose.tangent, pose.width)), length
    )


def _spans(cell: Cell) -> tuple[Span, Span, Span]:
    """
    Preserve the complete current material-box coordinates.
    """
    return cell.u, cell.q, cell.height


class AffineWitnesses:
    """
    Own at most 32 negative-only affine proposals in one immutable complete contact walk.

    A box intersection's vertices lie on edges of either box. Clipping their
    24 edges supplies at most 48 endpoints; their mean is one proposal. Actual
    joined-profile material can occupy less than these boxes. Only both original
    strict inverse maps establish a witness; a miss, limit or nonaffine phase
    never grants clearance or changes the ordinary full-cell proof.
    """

    def __init__(self, maximum_candidates: int = 32) -> None:
        """
        Require a finite nonrenewable allowance within the fixed 32-proposal ceiling.
        """
        if type(maximum_candidates) is not int or not 0 <= maximum_candidates <= 32:
            raise ValueError("Use zero to 32 affine witness proposals")
        self.maximum_candidates = maximum_candidates
        self._source: FoldRoute | None = None
        self.attempts = self.edges = self.candidates = self.inverse_requests = self.witnesses = 0
        self.nonaffine = self.limited = 0

    def bind(self, route: FoldRoute) -> None:
        """
        Seal this context to one walk and refuse reuse even for identical source geometry.
        """
        if self._source is not None:
            raise ValueError("Use a fresh affine witness context for each contact walk")
        self._source = route

    def _edges(
        self,
        source: Cell,
        frame: _Frame,
        target: Cell,
        other: _Frame,
        checkpoint: Callable[[], None] | None,
    ) -> list[Vector3]:
        """
        Clip exactly twelve source edges against the other three material slabs.
        """
        spans, limits = _spans(source), _spans(target)
        points = []
        for axis in range(3):
            fixed = tuple(i for i in range(3) if i != axis)
            for choices in product((0, 1), repeat=2):
                if checkpoint is not None:
                    checkpoint()
                self.edges += 1
                low = [0.0] * 3
                high = [0.0] * 3
                for index, upper in zip(fixed, choices):
                    low[index] = high[index] = spans[index].high if upper else spans[index].low
                low[axis], high[axis] = spans[axis].low, spans[axis].high
                start = frame.point((low[0], low[1], low[2]))
                end = frame.point((high[0], high[1], high[2]))
                a, b = other.coordinates(start), other.coordinates(end)
                enter, leave = 0.0, 1.0
                for first, second, interval in zip(a, b, limits):
                    delta = second - first
                    if delta == 0:
                        if not interval.low <= first <= interval.high:
                            enter, leave = 1.0, 0.0
                            break
                    else:
                        x, y = (interval.low - first) / delta, (interval.high - first) / delta
                        enter, leave = max(enter, min(x, y)), min(leave, max(x, y))
                if enter <= leave:
                    direction = difference(end, start)
                    points.extend(
                        (start.translated(direction, enter), start.translated(direction, leave))
                    )
        return points

    def inspect(
        self,
        first: Cell,
        second: Cell,
        occupied: Occupied,
        checkpoint: Callable[[], None] | None,
    ) -> Witness | None:
        """
        Measure one proposal under the caller's original clocks, requiring both actual strict inverses.
        """
        if checkpoint is not None:
            checkpoint()
        source = self._source
        if source is None:
            raise ValueError("Bind an affine witness source before inspection")
        if (
            type(first.piece) is not int
            or type(second.piece) is not int
            or not 0 <= first.piece < second.piece < len(source.pieces)
        ):
            raise ValueError("Use ordered current material cell identities")
        if self.attempts >= self.maximum_candidates:
            self.limited += 1
            return None
        a, b = (
            _frame(source.pieces[first.piece], first),
            _frame(source.pieces[second.piece], second),
        )
        if a is None or b is None:
            self.nonaffine += 1
            return None
        self.attempts += 1
        points = self._edges(first, a, second, b, checkpoint) + self._edges(
            second, b, first, a, checkpoint
        )
        if not points:
            return None
        anchor = points[0]
        offset = Vector3(
            *(
                math.fsum(getattr(p, axis) - getattr(anchor, axis) for p in points) / len(points)
                for axis in "xyz"
            )
        )
        point = anchor.translated(offset, 1.0)
        if not all(math.isfinite(value) for value in (point.x, point.y, point.z)):
            return None
        self.candidates += 1
        if checkpoint is not None:
            checkpoint()
        self.inverse_requests += 1
        first_coordinates = occupied(first.piece, point)
        if first_coordinates is None:
            return None
        if checkpoint is not None:
            checkpoint()
        self.inverse_requests += 1
        second_coordinates = occupied(second.piece, point)
        if second_coordinates is None:
            return None
        self.witnesses += 1
        return first_coordinates, second_coordinates, point

    def statistics(self) -> dict[str, int]:
        """
        Report attempted work and verified witnesses separately from geometric acceptance.
        """
        return {
            "attempts": self.attempts,
            "edges": self.edges,
            "candidates": self.candidates,
            "inverse_requests": self.inverse_requests,
            "witnesses": self.witnesses,
            "nonaffine": self.nonaffine,
            "limited": self.limited,
            "capacity": self.maximum_candidates,
        }
