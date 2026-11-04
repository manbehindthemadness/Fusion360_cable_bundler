"""
Factor one added guide steering stage into exact, fixed-radius material-fold primitives.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any, Callable

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import Pose
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology, rotation_choices

from .guide_frames import Frames


@dataclass(frozen=True)
class Chain:
    """
    Retain steering-feature boundaries, logical roots and legacy factor-discontinuity evidence.
    """

    topology: Topology
    group_ends: tuple[int, ...]
    targets: tuple[Pose, ...]
    feature_count: int
    roots: tuple[int, ...]
    factor_discontinuity: bool = False


def chains(
    boundary: Boundary,
    frames: Frames,
    parameters: tuple[float, ...],
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> tuple[Chain, ...]:
    """
    Enumerate only exact algebraic root ambiguities of the same guide-derived frame sequence.

    Two rotation stages form the baseline; three represent one added feature.
    At most eight root combinations/six fold primitives are supported. Empty
    stages or excess primitives stay explicit unresolved representations.
    """
    target = boundary.targets
    references = tuple(frames.at(u) for u in parameters)
    start = Pose(target.start, target.start_tangent, target.start_width)
    end = Pose(target.end, target.end_tangent, target.end_width)
    sequence = (start, *references, end)
    choices = tuple(
        rotation_choices(a, b, boundary.radius_mm, boundary.half_width_mm * 2)
        for a, b in zip(sequence, sequence[1:])
    )
    count = 1
    for group in choices:
        count *= len(group)
    if count > 8:
        raise ValueError("Derived orientation root count exceeds eight")
    result = []
    seen = set()
    for roots in product(*(range(len(group)) for group in choices)):
        checkpoint()
        groups = tuple(options[root] for options, root in zip(choices, roots))
        primitives: tuple[CylindricalFold, ...] = tuple(p for group in groups for p in group)
        event: dict[str, Any] = {
            "stage": "derived_feature_roots",
            "roots": roots,
            "group_sizes": tuple(len(g) for g in groups),
        }
        if any(not group for group in groups):
            event["status"] = "empty_feature"
        elif len(primitives) > 6:
            event["status"] = "primitive_budget_unresolved"
        else:
            signature = tuple(
                (round(p.angle_radians, 12), round(p.bank_radians, 12)) for p in primitives
            )
            if signature in seen:
                event["status"] = "duplicate"
            else:
                seen.add(signature)
                cumulative = []
                size = 0
                for group in groups[:-1]:
                    size += len(group)
                    cumulative.append(size)
                identifier = "features-" + "-".join(str(i) for i in roots)
                result.append(
                    Chain(
                        Topology(identifier, primitives, None),
                        tuple(cumulative),
                        references,
                        len(groups),
                        tuple(roots),
                    )
                )
                event["status"] = "derived"
        record(event)
    return tuple(result)
