"""
Construct spatial branch candidates from captured routes and explicit material roots.

One deterministic transported frame sequence feeds the existing exact rational
boundary assembler. Material, contact, curvature, native and junction acceptance
remain separate gates over that same candidate geometry.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from fractions import Fraction
from uuid import UUID

from cable_bundler.routing.geometry import Vector3, cross, dot, linear_combination, magnitude, unit

from .branch_plan import SpatialBranchPlan, assemble
from .capture import FRAME_IDENTITY, finite
from .contracts import CompleteRibbonInput, IncompleteRibbonInput, ResolvedBranch
from .root_profiles import CapFrame, RootProfile
from .spatial_frame import ChartOrientation, FrameSpan


@dataclass(frozen=True)
class BranchRoot:
    """
    Bind one route to its authoritative source profile and material frame.

    The caller verifies native ownership and profile provenance before invoking
    construction. Descendants require their actual parent-junction root; this
    entry never substitutes a trunk root or guesses a nearest cap.
    """

    route_id: UUID
    profile: RootProfile
    center_q_mm: float
    cap: CapFrame


def transport(value: Vector3, first: Vector3, following: Vector3, width: Vector3) -> Vector3:
    """
    Rotate a vector by the shortest endpoint-tangent rotation without changing scale.

    Directions must be finite unit vectors. Exactly antiparallel directions use
    the current transverse width as the half-turn axis, retaining material phase
    rather than selecting a world axis. This determines endpoint frames only;
    an interpolated frame is not guaranteed orthonormal or normal to the spine.
    """
    if (
        not all(finite(vector) for vector in (value, first, following, width))
        or abs(magnitude(first) - 1) > FRAME_IDENTITY
        or abs(magnitude(following) - 1) > FRAME_IDENTITY
    ):
        raise ValueError("Finite vectors and unit endpoint directions required")
    axis = cross(first, following)
    sine = magnitude(axis)
    cosine = dot(first, following)
    if sine == 0:
        if cosine > 0:
            return value
        axis = unit(width)
        if abs(dot(axis, first)) > FRAME_IDENTITY:
            raise ValueError("Antiparallel transport requires the transverse material width")
        return linear_combination(axis, 2 * dot(axis, value), value, -1)
    axis = Vector3(axis.x / sine, axis.y / sine, axis.z / sine)
    angle = math.atan2(sine, cosine)
    sine, cosine = math.sin(angle), math.cos(angle)
    crossed = cross(axis, value)
    return linear_combination(value, cosine, crossed, sine).translated(
        axis, dot(axis, value) * (1 - cosine)
    )


def frames(
    source: ResolvedBranch, root: BranchRoot, checkpoint: Callable[[], None]
) -> tuple[FrameSpan, ...]:
    """
    Preserve every reversed cubic and blend transported axes with zero endpoint jets.

    Uniform global intervals match the existing reversed-preview convention.
    Repeated first/last three vector controls give zero first/second axis jets
    at the ends of each interval. Center velocities and accelerations retain
    their actual source values; discontinuities are not repaired or concealed.
    No normalization inside the blend, frame fitting or extra work pool occurs.
    """
    checkpoint()
    curves = source.route.curves
    if not curves or root.route_id != source.leg.route_id:
        raise IncompleteRibbonInput("One matching branch root and complete source route required")
    width, thickness = root.cap.width, root.cap.thickness
    outward = Vector3(-root.cap.inward.x, -root.cap.inward.y, -root.cap.inward.z)
    orientation = (
        ChartOrientation.POSITIVE
        if dot(outward, cross(width, thickness)) > 0
        else ChartOrientation.NEGATIVE
    )
    output = []
    for index, curve in enumerate(reversed(curves)):
        checkpoint()
        forward = curve.derivative(1)
        direction = unit(Vector3(-forward.x, -forward.y, -forward.z))
        forward = curve.derivative(0)
        following = unit(Vector3(-forward.x, -forward.y, -forward.z))
        next_width = transport(width, direction, following, width)
        next_thickness = transport(thickness, direction, following, width)
        output.append(
            FrameSpan(
                Fraction(index, len(curves)),
                Fraction(index + 1, len(curves)),
                (curve.end, curve.control_b, curve.control_a, curve.start),
                (width,) if width == next_width else (width,) * 3 + (next_width,) * 3,
                (thickness,)
                if thickness == next_thickness
                else (thickness,) * 3 + (next_thickness,) * 3,
                orientation,
            )
        )
        width, thickness = next_width, next_thickness
    checkpoint()
    return tuple(output)


def construct(
    complete: CompleteRibbonInput,
    roots: tuple[BranchRoot, ...],
    checkpoint: Callable[[], None],
) -> Iterator[SpatialBranchPlan]:
    """
    Yield every branch's actual patches in captured order under one caller allocation.

    Require exactly one explicit root binding for every root and descendant
    branch before starting. Yielding preserves a completed prefix when later
    construction or resource checks stop. Outstanding physical/native checks
    from the existing assembler remain attached to every returned candidate.
    """
    checkpoint()
    by_route = {root.route_id: root for root in roots}
    route_ids = {branch.source.leg.route_id for branch in complete.branches}
    if len(by_route) != len(roots) or set(by_route) != route_ids:
        raise IncompleteRibbonInput("Every branch needs exactly one explicit material root")
    for branch in complete.branches:
        checkpoint()
        route_id = branch.source.leg.route_id
        root = by_route[route_id]
        yield assemble(
            complete,
            route_id,
            root.profile,
            root.center_q_mm,
            root.cap,
            frames(branch.source, root, checkpoint),
            checkpoint,
        )
