"""
Derive spatial steering from material-compatible intermediate widths instead of independent roll targets.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from cable_bundler.routing.geometry import Vector3, difference, magnitude, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_feature_insertion.features import Chain
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, relative
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology, rotation_choices


def aim(start: Pose, tangent: Vector3, radius: float, width: float) -> CylindricalFold | None:
    """
    Aim one regular material fold at a directed unit tangent, allowing its width to follow exactly.

    The crease lies in the departing material plane and has equal projection on
    both tangents. This determines its bank and signed bend analytically. Aligned
    tangents need no fold; an unresolved longitudinal crease declines. No angle
    grid, endpoint roll interpolation or independent width rotation is introduced.
    """
    wanted = unit(tangent)
    local = relative(start, wanted)
    if magnitude(difference(start.tangent, wanted)) <= 1e-10:
        return None
    axis = math.hypot(local.y, 1 - local.x)
    if axis <= 1e-12:
        return None
    cosine = (1 - local.x) / axis
    sine = -local.y / axis
    bank = math.atan2(sine, cosine)
    if abs(bank) >= math.pi / 2 - 1e-6:
        return None
    angle = math.atan2(local.z / cosine, (local.x - sine * sine) / (cosine * cosine))
    piece = fold(radius, width, angle, bank, 0.0)
    placed = PlacedPiece(start, piece, "Exact tangent steering")
    if magnitude(difference(placed.end_pose().tangent, wanted)) > 1e-9:
        raise ArithmeticError("Tangent steering lost its exact directed frame")
    return piece


def chains(
    boundary: Boundary,
    frames: Frames,
    parameters: tuple[float, ...],
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> tuple[Chain, ...]:
    """
    Aim at two deviation-guide tangents and factor only the remaining full terminal rotation.

    Each intermediate width is the actual material result of its preceding fold,
    with no extra roll constraint. Up to two exact terminal roots yield at most
    five folds and sixty-four straight masks each. Unneeded/unsupported steering
    declines rather than adding arbitrary folds or a different guide.
    """
    if len(parameters) != 2 or not 0 < parameters[0] < parameters[1] < 1:
        raise ValueError("Material steering requires two ordered guide stations")
    target = boundary.targets
    cursor = Pose(target.start, target.start_tangent, target.start_width)
    references: list[Pose] = []
    steering: list[CylindricalFold] = []
    for parameter in parameters:
        checkpoint()
        reference = frames.at(parameter)
        bent = aim(cursor, reference.tangent, boundary.radius_mm, 2 * boundary.half_width_mm)
        if bent is None:
            return ()
        steering.append(bent)
        cursor = PlacedPiece(cursor, bent, "Material-compatible steering").end_pose()
        references.append(Pose(reference.origin, cursor.tangent, cursor.width))
    end = Pose(target.end, target.end_tangent, target.end_width)
    choices = rotation_choices(cursor, end, boundary.radius_mm, 2 * boundary.half_width_mm)
    if len(choices) > 2:
        raise ArithmeticError("Terminal material steering exceeded two exact roots")
    result: list[Chain] = []
    for root, terminal in enumerate(choices):
        checkpoint()
        primitives = tuple(steering) + terminal
        if not terminal or len(primitives) > 5:
            continue
        record({"stage": "material_deviation", "root": root, "folds": len(primitives)})
        result.append(
            Chain(
                Topology(f"material_deviation_{root}", primitives, None),
                (1, 2),
                tuple(references),
                3,
                (root,),
            )
        )
    return tuple(result)
