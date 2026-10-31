"""
Construct fold routes from fixed poses and reject unresolved thick-volume contact.

Direct steering avoids lateral/height overshoot and separates fold modules.
No route guesses, shortest-path proof or native sweep success is implied.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Callable

from cable_bundler.routing.geometry import cross, difference, dot, magnitude
from devtools.ribbon_analysis.contracts import TargetPose, Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from devtools.ribbon_analysis.pinch import PinchLimit

from .construction import ConstructionPolicy, spatial_fold_radius
from .contact_solve import ContactTrial, resolve_contact
from .contact_solve import SelfContactError as SelfContactError
from .geometry import FoldRoute, PlacedPiece, Pose, Straight, extend, pose_error, relative
from .lateral import halfturn_pair, lateral_pair
from .orientation import orient as _orientation
from .orientation import orthogonal
from .primitives import Piece
from .steering import fold as _fold
from .steering import signed_distance as _signed_distance
from .steering import translation

__all__ = [
    "ConstructionPolicy",
    "FoldStrategy",
    "SelfContactError",
    "connect",
    "construct_candidate",
]

DEFAULT_LIMIT = PinchLimit()


class FoldStrategy(Enum):
    """
    Keep the measured outward construction alongside the continuous-angle trial.
    """

    OUTWARD = "outward"
    CONTINUOUS = "continuous"


def _simple(
    start: Pose, end: Pose, radius: float, width: float, runway: float
) -> tuple[Piece, ...] | None:
    """
    Solve straight or one-plane turns directly before using spatial steering.
    """
    if magnitude(difference(start.width, end.width)) >= 1e-10:
        return None
    delta = difference(end.origin, start.origin)
    angle = math.atan2(
        dot(end.tangent, cross(start.tangent, start.width)), dot(end.tangent, start.tangent)
    )
    if abs(angle) < 1e-12:
        lateral = delta.translated(start.tangent, -dot(delta, start.tangent))
        if magnitude(lateral) < 1e-10:
            return _signed_distance(dot(delta, start.tangent), radius, width, runway)
        return None
    if abs(math.sin(angle)) < 1e-10:
        return None
    fold = _fold(radius, width, angle, 0.0, runway)
    offset = difference(extend(start, (fold,)).origin, start.origin)
    residual = difference(delta, offset)
    b = dot(residual, cross(start.tangent, start.width)) / math.sin(angle)
    a = dot(residual, start.tangent) - math.cos(angle) * b
    if abs(dot(residual, start.width)) > 1e-10 or min(a, b) < -1e-10:
        return None
    return (
        tuple([Straight(a)] if a > 1e-12 else [])
        + (fold,)
        + tuple([Straight(b)] if b > 1e-12 else [])
    )


def construct_candidate(
    source: TargetPose,
    limit: PinchLimit = DEFAULT_LIMIT,
    *,
    runway_mm: float = 0.0,
    checkpoint: Callable[[], None] | None = None,
    record_candidate: Callable[[tuple[Piece, ...], float], None] | None = None,
    strategy: FoldStrategy = FoldStrategy.OUTWARD,
    construction: ConstructionPolicy = ConstructionPolicy.MATERIAL_FOLD,
) -> FoldRoute:
    """
    Construct a locally compatible candidate requiring a separate contact check.

    Straight distances are solved after subtracting finite-fold offsets. Spatial
    steering returns to the departure frame before the arrival orientation is
    applied. All pieces preserve material length and the same profile coordinates.
    A declared1e-9relative radius inset avoids a floating boundary classification;
    numerical cap residuals must remain below1e-7, without moving targets.
    OUTWARD preserves the measured baseline; CONTINUOUS is an optional angle
    generalization whose longer paths have not replaced it. record_candidate
    retains every complete primitive sequence considered by the exact quadratic
    factorization before selecting material cost; it does not certify contact.
    RIGID_PERPENDICULAR additionally bounds local rigid-sweep collapse for spatial
    folds, independently of material pinch. Tight planar solutions stay unchanged.
    It does not make rigid sweep geometry identical to the material-fold surface.
    """
    targets = Targets.capture(source)
    spatial_radius = spatial_fold_radius(targets, limit, construction)
    if not isinstance(strategy, FoldStrategy):
        raise ValueError("Use an explicit FoldStrategy.")
    if not math.isfinite(runway_mm) or runway_mm < 0 or isinstance(runway_mm, bool):
        raise ValueError("Runway must be a finite nonnegative material distance.")
    if magnitude(difference(targets.start, targets.end)) <= 1e-8:
        raise ValueError("Coincident endpoints need a separately specified loop construction.")
    if checkpoint is not None:
        checkpoint()
    radius = targets.diameter_mm / 2 / limit.fraction * (1 + 1e-9)
    width = 2 * (targets.lines * targets.diameter_mm / 2 + targets.diameter_mm * 0.1)
    start = Pose(targets.start, targets.start_tangent, targets.start_width)
    end = Pose(targets.end, targets.end_tangent, targets.end_width)
    simple = _simple(start, end, radius, width, runway_mm)
    if simple is not None:
        geometries = simple
    else:
        radius = spatial_radius

        def sequence(factors: tuple[CylindricalFold, ...]) -> tuple[Piece, ...]:
            """
            Close this exact rotation factorization's positional displacement.
            """
            oriented = extend(start, factors)
            residual = relative(start, difference(end.origin, oriented.origin))
            builder = halfturn_pair if strategy is FoldStrategy.OUTWARD else lateral_pair
            return (
                translation(
                    residual,
                    radius,
                    width,
                    runway_mm,
                    targets.diameter_mm / 2,
                    factors,
                    lateral_builder=builder,
                )
                + factors
            )

        def material_cost(factors: tuple[CylindricalFold, ...]) -> float:
            """
            Compare exact algebraic roots by complete closed material distance.
            """
            branch_geometries = sequence(factors)
            value = math.fsum(g.material_length_mm for g in branch_geometries)
            if record_candidate is not None:
                record_candidate(branch_geometries, value)
            return value

        if strategy is FoldStrategy.OUTWARD:
            orientation = orthogonal(start, end, radius, width, runway_mm)
        else:
            orientation = _orientation(start, end, radius, width, runway_mm, material_cost)
        geometries = sequence(orientation)
    pose = start
    pieces = []
    for index, geometry in enumerate(geometries):
        if checkpoint is not None:
            checkpoint()
        label = f"{'Fold' if isinstance(geometry, CylindricalFold) else 'Straight'} {index + 1}"
        piece = PlacedPiece(pose, geometry, label)
        pieces.append(piece)
        pose = piece.end_pose()
    gap, frame_gap = pose_error(pose, end)
    if not pieces or max(gap, frame_gap) > 1e-7:
        raise ValueError(f"Algebraic construction failed cap closure: {gap=}, {frame_gap=}.")
    return FoldRoute(targets, tuple(pieces), radius)


def connect(
    source: TargetPose,
    limit: PinchLimit = DEFAULT_LIMIT,
    *,
    maximum_contact_pairs: int = 20000,
    maximum_contact_depth: int = 36,
    maximum_corrections: int = 0,
    checkpoint: Callable[[], None] | None = None,
    record: Callable[[ContactTrial], None] | None = None,
    strategy: FoldStrategy = FoldStrategy.OUTWARD,
    construction: ConstructionPolicy = ConstructionPolicy.MATERIAL_FOLD,
) -> FoldRoute:
    """
    Return a connected route only after the full thick-profile contact gate clears.

    Penetration and unresolved checks raise SelfContactError with the original
    candidate/evidence retained. This is not proof that another route cannot fit.
    Runway repair is opt-in: its bounded development trial did not clear the
    spatial cases, so default execution rejects immediately without growing them.
    The explicit construction policy is applied to every candidate before contact.
    """
    targets = Targets.capture(source)

    def build(runway: float) -> FoldRoute:
        """
        Recompute closure after a common material runway change.
        """
        return construct_candidate(
            targets,
            limit,
            runway_mm=runway,
            checkpoint=checkpoint,
            strategy=strategy,
            construction=construction,
        )

    step = targets.diameter_mm * (targets.lines + 1.2)
    return resolve_contact(
        build,
        step,
        maximum_corrections=maximum_corrections,
        maximum_pairs=maximum_contact_pairs,
        maximum_depth=maximum_contact_depth,
        checkpoint=checkpoint,
        record=record,
    )
