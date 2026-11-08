"""
Guide joint correction with complete witnessed flat/profile regions instead of isolated fibers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from functools import cached_property, lru_cache
from typing import Callable

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_feature_insertion.separation import Region, Side, locate, regions
from experiments.experiment_ribbon_fold_route.contact import Penetration
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import (
    FlatPhase,
    profile_arcs,
    region,
)
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece

from .feature_plane import SignedJoints


class ProfileExtent(Enum):
    """
    Enclose a witnessed profile arc or the complete occupied width during motion guidance.
    """

    ARC = "arc"
    COMPLETE = "complete"


@dataclass(frozen=True)
class FlatPart:
    """
    Identify one complete flat phase and an unchanged occupied profile interval.
    """

    phase: FlatPhase
    low_q: float
    high_q: float
    half_height: float


def _identify(
    piece: PlacedPiece, coordinates: tuple[float, float, float], lines: int, diameter: float
) -> FlatPart | None:
    """
    Derive motion-guidance identity from an actual witness; curved interiors remain unsupported.

    Roundoff at a G1join may select its adjacent flat for guidance only. This
    changes no strict inverse test, geometry, physical tolerance or final proof.
    """
    geometry = piece.geometry
    u, q, _ = coordinates
    phase = FlatPhase.STRAIGHT
    if isinstance(geometry, CylindricalFold):
        c, s = math.cos(geometry.bank_radians), math.sin(geometry.bank_radians)
        xi = c * (u * geometry.material_length_mm - geometry.before_mm) + s * q
        guard = 1e-11 * (1 + geometry.material_length_mm + abs(q))
        if xi <= guard:
            phase = FlatPhase.BEFORE
        elif xi >= geometry.radius_mm * abs(geometry.angle_radians) - guard:
            phase = FlatPhase.AFTER
        else:
            return None
    for arc in profile_arcs(lines, diameter):
        if arc.low_q <= q <= arc.high_q:
            return FlatPart(phase, arc.low_q, arc.high_q, arc.maximum_height() + 1e-11)
    return None


def paired_return_fold(route: FoldRoute, witness: Penetration) -> int | None:
    """
    Select the material-entry fold of a strict BEFORE-to-AFTER adjacent-fold return bracket.

    Both pieces must be existing adjacent folds. Their measured flat phases
    bracket the entire pair, instead of its legitimate shared cap. Unsupported
    curved phases or other contact topologies grant no reflected action.
    """
    first, second = witness.pieces
    if not 0 <= first < second < len(route.pieces):
        raise ValueError("A return witness must identify ordered existing material pieces")
    if second != first + 1 or not all(
        isinstance(route.pieces[i].geometry, CylindricalFold) for i in (first, second)
    ):
        return None
    parts = (
        _identify(
            route.pieces[first], witness.first, route.targets.lines, route.targets.diameter_mm
        ),
        _identify(
            route.pieces[second], witness.second, route.targets.lines, route.targets.diameter_mm
        ),
    )
    if (
        parts[0] is None
        or parts[1] is None
        or parts[0].phase is not FlatPhase.BEFORE
        or parts[1].phase is not FlatPhase.AFTER
    ):
        return None
    return sum(isinstance(piece.geometry, CylindricalFold) for piece in route.pieces[:first])


def flat_prism(
    piece: PlacedPiece, part: FlatPart
) -> tuple[tuple[Vector3, ...], tuple[Vector3, ...], tuple[Vector3, ...]]:
    """
    Enclose the entire flat/profile region with its full current longitudinal extent.
    """
    placed = region(piece, part.phase, part.low_q, part.high_q)
    if len(placed.polygon) < 3:
        raise ValueError("Required flat material region vanished")
    origin = Vector3(*placed.origin)
    tangent, width, normal = (
        Vector3(*placed.tangent),
        Vector3(*placed.width),
        unit(Vector3(*placed.normal)),
    )
    centers = tuple(origin.translated(tangent, s).translated(width, q) for s, q in placed.polygon)
    vertices = tuple(
        p.translated(normal, height)
        for p in centers
        for height in (-part.half_height, part.half_height)
    )
    raw_edges = tuple(difference(b, a) for a, b in zip(centers, centers[1:] + centers[:1]))
    edges = tuple(unit(edge) for edge in raw_edges if magnitude(edge) > 1e-10) + (normal,)
    normals = (normal,) + tuple(unit(cross(edge, normal)) for edge in edges[:-1])
    return vertices, edges, normals


def flat_span(piece: PlacedPiece, part: FlatPart, axis: Vector3) -> tuple[float, float]:
    """
    Evaluate the identical complete-prism support directly in affine material coordinates.
    """
    placed = region(piece, part.phase, part.low_q, part.high_q)
    if len(placed.polygon) < 3:
        raise ValueError("Required flat material region vanished")
    a, b = dot(Vector3(*placed.tangent), axis), dot(Vector3(*placed.width), axis)
    normal = unit(Vector3(*placed.normal))
    height = part.half_height * abs(dot(normal, axis))
    origin = dot(Vector3(*placed.cap_origin), axis)
    if part.phase is FlatPhase.AFTER:
        origin += -piece.geometry.material_length_mm * a
    values = tuple(a * s + b * q for s, q in placed.polygon)
    return origin + min(values) - height, origin + max(values) + height


@dataclass(frozen=True)
class FlatSeparation:
    """
    Hold one deterministic nearest SAT direction while re-enclosing both complete material regions.

    This is conservative correction guidance. It cannot replace the full thick
    contact certificate after joint motion, including curved and adjacent regions.
    """

    model: SignedJoints
    pair: tuple[Region, Region]
    parts: tuple[FlatPart, FlatPart]
    axis: Vector3

    @classmethod
    def create(
        cls,
        model: SignedJoints,
        route: FoldRoute,
        witness: Penetration,
        *,
        extent: ProfileExtent = ProfileExtent.ARC,
    ) -> FlatSeparation | None:
        """
        Derive complete regions and the nearest signed convex-envelope SAT direction.

        Complete-profile guidance covers all conductors in both witnessed flat
        phases. It changes no curved-region proof or final contact requirement.
        """
        if not isinstance(extent, ProfileExtent):
            raise ValueError("Supply an explicit flat profile extent")
        first, second = witness.pieces
        target = route.targets
        a = _identify(route.pieces[first], witness.first, target.lines, target.diameter_mm)
        b = _identify(route.pieces[second], witness.second, target.lines, target.diameter_mm)
        if a is None or b is None:
            return None
        if extent is ProfileExtent.COMPLETE:
            a, b = (
                FlatPart(
                    part.phase,
                    -route.half_width_mm,
                    route.half_width_mm,
                    target.diameter_mm / 2 + 1e-11,
                )
                for part in (a, b)
            )
        first_shape = flat_prism(route.pieces[first], a)
        second_shape = flat_prism(route.pieces[second], b)
        candidates = (
            first_shape[2]
            + second_shape[2]
            + tuple(cross(x, y) for x in first_shape[1] for y in second_shape[1])
        )
        choices = []
        for raw in candidates:
            if magnitude(raw) <= 1e-10:
                continue
            axis = unit(raw)
            x, y = (
                tuple(dot(p, axis) for p in first_shape[0]),
                tuple(dot(p, axis) for p in second_shape[0]),
            )
            choices.extend(((min(y) - max(x), axis), (min(x) - max(y), axis.translated(axis, -2))))
        if not choices:
            return None
        axis = max(choices, key=lambda item: item[0])[1]
        tags = regions(route)
        return cls(model, (tags[first], tags[second]), (a, b), axis)

    @cached_property
    def _gaps(self) -> Callable[[tuple[float, ...], Side], float]:
        """
        Retain at most64immutable joint-coordinate gap evaluations per constraint.
        """
        return lru_cache(maxsize=64)(self._gap)

    def _gap(self, values: tuple[float, ...], side: Side) -> float:
        """
        Re-enclose both complete flat regions under the current joint coordinates.
        """
        pieces = self.model.pieces(values)
        first, second = tuple(
            flat_span(locate(self.model.original, pieces, tag), part, self.axis)
            for tag, part in zip(self.pair, self.parts)
        )
        gap = second[0] - first[1] if side is Side.BEFORE else first[0] - second[1]
        return gap / self.model.scale

    def gap(self, values: tuple[float, ...], side: Side) -> float:
        """
        Return a normalized signed complete-region gap on the retained world axis.
        """
        return self._gaps(values, side)
