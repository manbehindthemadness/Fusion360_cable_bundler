"""
Derive exact endpoint rotation branches through a guide-directed intermediate frame.
"""

from __future__ import annotations

from dataclasses import dataclass

from cable_bundler.routing.geometry import cross, dot, magnitude, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Pose
from experiments.experiment_ribbon_fold_route.orientation import orient
from experiments.experiment_ribbon_spline_guide.guide import Guide


@dataclass(frozen=True)
class Topology:
    """
    Preserve a derived fold order, without fixed spatial placement or travel lengths.
    """

    identifier: str
    folds: tuple[CylindricalFold, ...]
    middle_after: int | None


def rotation_choices(
    start: Pose, end: Pose, radius: float, width: float
) -> tuple[tuple[CylindricalFold, ...], ...]:
    """
    Retain all exact algebraic rotation roots, including direct/degenerate cases.
    """
    choices: list[tuple[CylindricalFold, ...]] = []

    def collect(factors: tuple[CylindricalFold, ...]) -> float:
        """
        Collect derived roots without selecting one by the old steering construction.
        """
        choices.append(factors)
        return 0.0

    chosen = orient(start, end, radius, width, 0.0, collect)
    return tuple(choices) if choices else (chosen,)


def middle_frame(route: FoldRoute, guide: Guide) -> Pose:
    """
    Use the guide's middle tangent and projected mean ordered width, without a landmark.

    Its location describes the reference only; the position solver is free to place
    this orientation anywhere. If the mean width projection degenerates, use the
    longest projected endpoint width/entry normal, with stable input order. This
    remains covariant under rigid scene transforms, rather than choosing world axes.
    """
    target = route.targets
    origin, velocity = guide.sample(0.5)
    tangent = unit(velocity)
    mean = target.start_width.translated(target.end_width, 1)
    width = mean.translated(tangent, -dot(mean, tangent))
    if magnitude(width) <= 1e-10:
        sources = (
            target.start_width,
            target.end_width,
            cross(target.start_tangent, target.start_width),
        )
        projections = tuple(v.translated(tangent, -dot(v, tangent)) for v in sources)
        width = max(projections, key=magnitude)
    return Pose(origin, tangent, unit(width))


def topologies(route: FoldRoute, guide: Guide) -> tuple[Topology, ...]:
    """
    Offer direct rotation and two stages through the guide frame, at most six branches.

    No lateral/height translation modules, entry-frame resets, spacing envelopes or
    signed-distance backtracking are used. Rotation factors carry orientation
    progress forward. No random seeds, bank grid or specimen-specific branches.
    """
    target = route.targets
    start = Pose(target.start, target.start_tangent, target.start_width)
    end = Pose(target.end, target.end_tangent, target.end_width)
    middle = middle_frame(route, guide)
    radius, width = route.radius_mm, route.half_width_mm * 2
    choices = [
        Topology(f"direct-{i}", folds, None)
        for i, folds in enumerate(rotation_choices(start, end, radius, width))
    ]
    for first, a in enumerate(rotation_choices(start, middle, radius, width)):
        for last, b in enumerate(rotation_choices(middle, end, radius, width)):
            choices.append(Topology(f"guide-{first}-{last}", a + b, len(a)))
    seen = set()
    unique = []
    for choice in choices:
        signature = tuple(
            (round(f.angle_radians, 12), round(f.bank_radians, 12)) for f in choice.folds
        )
        if signature not in seen:
            seen.add(signature)
            unique.append(choice)
    if len(unique) > 6 or any(len(c.folds) > 6 for c in unique):
        raise ArithmeticError("Derived rotation branches exceed frozen representation bounds.")
    return tuple(unique)
