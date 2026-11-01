"""
Enumerate exact endpoint fold branches before committing to a directional layout.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Any, Callable

from cable_bundler.routing.geometry import difference
from experiments.experiment_ribbon_bend_reduction.rewrite import fold_count, reclose, rewrites
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.geometry import (
    FoldRoute,
    PlacedPiece,
    Pose,
    Straight,
    extend,
    relative,
)
from experiments.experiment_ribbon_fold_route.lateral import halfturn_pair
from experiments.experiment_ribbon_fold_route.orientation import orient
from experiments.experiment_ribbon_fold_route.primitives import Piece
from experiments.experiment_ribbon_fold_route.solver import construct_candidate
from experiments.experiment_ribbon_fold_route.steering import translation

from .guide import Agreement, Guide, agreement


@dataclass(frozen=True)
class Branch:
    """
    Identify a complete closed algebraic candidate whose contact is still unknown.
    """

    identifier: str
    route: FoldRoute
    agreement: Agreement
    rewrites_evaluated: int


def place(source: FoldRoute, geometries: tuple[Piece, ...]) -> FoldRoute:
    """
    Recompose a full sequence from the unchanged departure and audit both caps.
    """
    target = source.targets
    pose = Pose(target.start, target.start_tangent, target.start_width)
    pieces = []
    for geometry in geometries:
        piece = PlacedPiece(pose, geometry, f"Guided piece{len(pieces) + 1}")
        pieces.append(piece)
        pose = piece.end_pose()
    route = FoldRoute(target, tuple(pieces), source.radius_mm)
    if cap_error(route) > 1e-7:
        raise ArithmeticError("Exact guided construction lost ordered cap closure.")
    return route


def mirror_departure(geometries: tuple[Piece, ...]) -> tuple[Piece, ...]:
    """
    Mirror only an initial two-half-turn negative-travel module, preserving its pose.

    Both half-turns must be the same planar fold object emitted by signed_distance.
    Reversing their angles together cancels their offsets just as the original did.
    An isolated fold is never reversed, and all other sequences remain untouched.
    """
    if (
        len(geometries) >= 3
        and not isinstance(geometries[0], Straight)
        and isinstance(geometries[1], Straight)
        and geometries[0] is geometries[2]
        and geometries[0].bank_radians == 0
        and abs(abs(geometries[0].angle_radians) - math.pi) < 1e-12
    ):
        mirrored = replace(geometries[0], angle_radians=-geometries[0].angle_radians)
        return (mirrored, geometries[1], mirrored) + geometries[3:]
    return geometries


def _simplify(
    route: FoldRoute,
    guide: Guide,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> tuple[FoldRoute, int]:
    """
    Apply at most24provisional algebraic rewrites, largest reduction then guide score.

    These intermediate routes are not accepted physical results. Only the final
    candidate receives the full contact gate. Each round reduces bend count; no
    angle fitting, radius adjustment, seed search or contact-driven repair occurs.
    """
    count = 0
    for _ in range(3):
        choices = []
        for rewrite in rewrites(route):
            if count >= 24:
                break
            checkpoint()
            count += 1
            candidate = reclose(route, rewrite)
            record(
                {
                    "stage": "provisional_rewrite",
                    "rewrite": asdict(rewrite),
                    "route": snapshot(candidate) if candidate is not None else None,
                }
            )
            if candidate is not None:
                score = agreement(candidate, guide)
                choices.append(((-rewrite.removed_folds, round(score.rms_mm, 10)), candidate))
        if not choices:
            break
        route = min(choices, key=lambda item: item[0])[1]
    return route, count


def branches(
    source: FoldRoute,
    guide: Guide,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> tuple[Branch, ...]:
    """
    Close up to eight alternatives from two exact rotation roots and two mirror bits.

    The original outward lateral family is retained. Mirroring its layer and the
    negative-departure pair supplies geometric branches, not randomized guesses.
    Fixed local spacing remains a known limitation; guidance selects complete
    branches and provisional rewrites, not a general spline-to-ribbon projection.
    """
    target = source.targets
    start = Pose(target.start, target.start_tangent, target.start_width)
    end = Pose(target.end, target.end_tangent, target.end_width)
    radius, width = source.radius_mm, source.half_width_mm * 2
    direct = construct_candidate(target, minimum_radius_mm=radius)
    if fold_count(direct) <= 1:
        route = direct
        return (Branch("direct", route, agreement(route, guide), 0),)
    rotations: list[tuple[Piece, ...]] = []

    def collect(factors: tuple[Piece, ...]) -> float:
        """
        Retain each exact algebraic orientation root without choosing by old cost.
        """
        rotations.append(factors)
        return 0.0

    chosen = orient(start, end, radius, width, 0.0, collect)
    if not rotations:
        rotations.append(chosen)
    results = []
    signatures = set()
    for index, factors in enumerate(rotations):
        residual = relative(start, difference(end.origin, extend(start, factors).origin))
        for lateral_mirror in (False, True):

            def lateral(
                distance: float,
                height: float,
                r: float,
                w: float,
                runway: float,
                mirror: bool = lateral_mirror,
            ) -> tuple[Piece, ...]:
                """
                Select the opposite layer through the same closed lateral equations.
                """
                return halfturn_pair(distance, -height if mirror else height, r, w, runway)

            sequence = (
                translation(
                    residual,
                    radius,
                    width,
                    0.0,
                    target.diameter_mm / 2,
                    factors,
                    lateral_builder=lateral,
                )
                + factors
            )
            for departure_mirror in (False, True):
                checkpoint()
                geometries = mirror_departure(sequence) if departure_mirror else sequence
                signature = tuple(geometries)
                if signature in signatures:
                    continue
                signatures.add(signature)
                initial = place(source, geometries)
                record({"stage": "closed_branch", "route": snapshot(initial)})
                route, count = _simplify(initial, guide, checkpoint, record)
                results.append(
                    Branch(
                        f"root{index}-lateral{int(lateral_mirror)}-departure{int(departure_mirror)}",
                        route,
                        agreement(route, guide),
                        count,
                    )
                )
    if len(results) > 8:
        raise ArithmeticError("Exact branch count exceeded the frozen bound.")
    return tuple(
        sorted(
            results,
            key=lambda b: (
                round(b.agreement.rms_mm, 10),
                round(b.agreement.mean_direction_loss, 10),
                b.route.material_length_mm,
                b.identifier,
            ),
        )
    )
