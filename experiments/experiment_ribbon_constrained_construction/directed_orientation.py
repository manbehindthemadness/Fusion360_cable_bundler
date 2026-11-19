"""
Factor exact frame rotation through an intermediate tangent directed toward spatial travel.

Balanced crease banks are not a spatial direction constraint. For relative
quaternion q=(w,x,y,z), two crease-plane factors allow unit intermediate tangents
h satisfying (x,y,z).h=x. Maximizing the stage displacement dot h over that circle
selects one exact orientation construction without testing guessed fold signs.
This preference is not a clearance certificate or global path-length optimum.
"""

from __future__ import annotations

import math
from typing import Callable

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_feature_insertion.features import Chain
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_fold_route.geometry import Pose, relative
from experiments.experiment_ribbon_fold_route.orientation import (
    material_factors,
    relative_rotation,
    remaining_rotation,
)
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology, rotation_choices


def factors(start: Pose, end: Pose, radius: float, width: float) -> tuple[CylindricalFold, ...]:
    """
    Match the final frame while maximizing intermediate heading toward end.origin-start.origin.

    Rotation identity and pure longitudinal rotation retain the existing exact
    degeneracy construction. A tied spatial objective uses existing exact roots
    rather than an arbitrary world axis. A selected longitudinal crease remains
    unsupported and raises; no alternate heading search or geometry repair runs.
    """
    q = relative_rotation(start, end)
    _, x, y, z = q
    vector = Vector3(x, y, z)
    norm = magnitude(vector)
    displacement = relative(start, difference(end.origin, start.origin))
    if norm < 1e-12 or magnitude(displacement) < 1e-12:
        return min(
            rotation_choices(start, end, radius, width),
            key=lambda group: sum(g.material_length_mm for g in group),
        )
    axis = unit(vector)
    center = Vector3(0, 0, 0).translated(axis, x / norm)
    radius_squared = max(0.0, 1 - (x / norm) ** 2)
    wanted = unit(displacement)
    transverse = wanted.translated(axis, -dot(wanted, axis))
    if radius_squared < 1e-20 or magnitude(transverse) < 1e-12:
        return min(
            rotation_choices(start, end, radius, width),
            key=lambda group: sum(g.material_length_mm for g in group),
        )
    heading = center.translated(unit(transverse), math.sqrt(radius_squared))
    c = math.sqrt(max(0.0, (1 - heading.x) / 2))
    if c < 1e-10:
        raise ValueError("Directed intermediate heading requires a singular longitudinal crease")
    first = (-heading.z / (2 * c), heading.y / (2 * c), c, 0.0)
    return material_factors(first, radius, width, 0.0) + material_factors(
        remaining_rotation(first, q), radius, width, 0.0
    )


def chain(
    boundary: Boundary,
    frames: Frames,
    parameters: tuple[float, ...],
    checkpoint: Callable[[], None],
) -> Chain:
    """
    Construct one displacement-directed factor sequence through the existing ordered guide sites.

    No saved route, sign permutation, extra stage or alternative station enters.
    Material travel remains A-to-B even though each frame pair has its own local
    displacement objective. Position closure and physical checks remain required.
    """
    if (
        not 1 <= len(parameters) <= 2
        or tuple(sorted(parameters)) != parameters
        or any(not 0 < p < 1 for p in parameters)
    ):
        raise ValueError("Use one or two existing ordered interior guide parameters")
    target = boundary.targets
    if frames.targets != target:
        raise ValueError("Guide frames must retain the construction targets")
    references = tuple(frames.at(p) for p in parameters)
    sequence = (
        Pose(target.start, target.start_tangent, target.start_width),
        *references,
        Pose(target.end, target.end_tangent, target.end_width),
    )
    groups = []
    for start, end in zip(sequence, sequence[1:]):
        checkpoint()
        groups.append(factors(start, end, boundary.radius_mm, boundary.half_width_mm * 2))
    folds = tuple(fold for group in groups for fold in group)
    if any(not group for group in groups) or len(folds) > 6:
        raise ValueError("Directed guide stages require one to six nonempty material folds")
    ends = []
    count = 0
    for group in groups[:-1]:
        count += len(group)
        ends.append(count)
    return Chain(
        Topology("displacement-directed", folds, None),
        tuple(ends),
        references,
        len(groups),
        tuple(0 for _ in groups),
    )
