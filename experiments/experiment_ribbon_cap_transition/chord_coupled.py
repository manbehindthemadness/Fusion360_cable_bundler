"""
Use endpoint displacement to select an intermediate coupled ribbon frame.

Six eased bend/rotation motions and one chord-aligned straight motion provide
seven length freedoms. One minimum-deviation linear solve closes position. Its
negative solutions reject; no active-set search, clipping, retries or repair.
"""

from __future__ import annotations

import math
from dataclasses import replace

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit

from .coupled_motion import ZERO, CoupledMotion, orientation_angles, rotate
from .coupled_route import CoupledRejection
from .coupled_route import construct as original_construct
from .endpoint_first import EndpointCase, controls


def _transport(width: Vector3, tangent: Vector3, heading: Vector3) -> Vector3:
    """
    Transport ordered width by the shortest rotation between two headings.

    An exactly antiparallel heading has no unique transport axis and rejects;
    no arbitrary extra roll is assigned to resolve that ambiguity.
    """
    axis = cross(tangent, heading)
    sine, cosine = magnitude(axis), dot(tangent, heading)
    if sine <= 1e-10:
        if cosine < 0:
            raise CoupledRejection("Antiparallel chord transport has no unique axis.")
        return width
    return rotate(width, unit(axis), math.atan2(sine, cosine))


def _turn(
    tangent: Vector3, width: Vector3, end_tangent: Vector3, end_width: Vector3
) -> tuple[CoupledMotion, ...]:
    """
    Factor one orientation leg into the original admissible oblique-axis motions.

    The primitive basis is unchanged; endpoint displacement now determines the
    intervening frame and therefore the rotation amounts and later world axes.
    """
    motions = []
    angles = orientation_angles(tangent, width, end_tangent, end_width)
    for angle, sign in zip(angles, (1, -1, 1)):
        motion = CoupledMotion(
            ZERO, tangent, width, unit(tangent.translated(width, sign)), angle, 1
        )
        motions.append(motion)
        tangent, width = motion.frame(1)
    if (
        max(magnitude(difference(tangent, end_tangent)), magnitude(difference(width, end_width)))
        > 1e-8
    ):
        raise RuntimeError("Chord leg orientation failed closure.")
    return tuple(motions)


def schedule(case: EndpointCase) -> tuple[CoupledMotion, ...]:
    """
    Choose seven unit-length prototypes from both endpoint poses and displacement.

    The middle tangent is the chord direction. Its ordered width bisects the
    transported endpoint widths. A signed half-turn tie takes +pi; these inputs
    prescribe endpoint frames, not an additional winding class. No material roll
    limiter, obstacle routing, target movement or fitted interior path is used.
    """
    controls(case)
    heading = unit(difference(case.end, case.start))
    a = _transport(case.start_width, case.start_tangent, heading)
    b = _transport(case.end_width, case.end_tangent, heading)
    sine, cosine = dot(heading, cross(a, b)), dot(a, b)
    angle = math.pi if abs(sine) <= 1e-12 and cosine < 0 else math.atan2(sine, cosine)
    width = rotate(a, heading, angle / 2)
    return (
        *_turn(case.start_tangent, case.start_width, heading, width),
        CoupledMotion(ZERO, heading, width, width, 0, 1),
        *_turn(heading, width, case.end_tangent, case.end_width),
    )


def travel_lengths(columns: tuple[Vector3, ...], chord: Vector3) -> tuple[float, ...]:
    """
    Close three position equations with the minimum change to equal nominal travel.

    Nominal travel is chord length divided by the number of motions. The direct
    solution is l=l0+A^T(AA^T)^-1(d-A*l0). This is an unconstrained algebraic
    projection, not a nonnegative optimizer: nonpositive travel rejects without
    trying another active set. Singular position systems also reject explicitly.
    """
    if not columns or not all(math.isfinite(v) for p in (*columns, chord) for v in (p.x, p.y, p.z)):
        raise ValueError("Finite travel columns and displacement are required.")
    distance = magnitude(chord)
    if distance <= 1e-8:
        raise ValueError("Travel displacement must be nonzero.")
    preferred = distance / len(columns)
    residual = chord
    for column in columns:
        residual = residual.translated(column, -preferred)
    rows = tuple(
        Vector3(
            sum(getattr(p, axis) * p.x for p in columns),
            sum(getattr(p, axis) * p.y for p in columns),
            sum(getattr(p, axis) * p.z for p in columns),
        )
        for axis in ("x", "y", "z")
    )
    determinant = dot(rows[0], cross(rows[1], rows[2]))
    scale = ((rows[0].x + rows[1].y + rows[2].z) / 3) ** 3
    if scale <= 0 or determinant <= 1e-12 * scale:
        raise CoupledRejection("Chord-guided position system is singular; no alternate basis.")
    multiplier = Vector3(
        dot(residual, cross(rows[1], rows[2])) / determinant,
        dot(rows[0], cross(residual, rows[2])) / determinant,
        dot(rows[0], cross(rows[1], residual)) / determinant,
    )
    lengths = tuple(preferred + dot(column, multiplier) for column in columns)
    if min(lengths) <= 1e-8:
        raise CoupledRejection(
            f"Chord-guided projection requires nonpositive travel {lengths}; no repair."
        )
    return lengths


def construct(case: EndpointCase) -> tuple[CoupledMotion, ...]:
    """
    Connect fixed poses once, preserving compatible analytic planar controls.

    A positive pose-closing path is still subject to the unchanged curvature,
    lane, envelope and native checks. Neither the nominal travel nor the direct
    projection establishes minimum length, physical equilibrium or feasibility.
    """
    controls(case)
    chord = difference(case.end, case.start)
    if (
        magnitude(difference(case.start_width, case.end_width)) <= 1e-10
        and abs(dot(chord, case.start_width)) <= 1e-10
    ):
        return original_construct(case)
    prototypes = schedule(case)
    lengths = travel_lengths(tuple(m.displacement(1) for m in prototypes), chord)
    motions, start = [], case.start
    for prototype, length in zip(prototypes, lengths):
        motion = replace(prototype, start=start, length=length)
        motions.append(motion)
        start = motion.jet(1)[0]
    if magnitude(difference(start, case.end)) > 1e-8:
        raise RuntimeError("Chord-guided integration failed fixed position closure.")
    return tuple(motions)
