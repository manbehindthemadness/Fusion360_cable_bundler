"""
Archive the exact material route and a separately labelled diagnostic interpolation.
"""

from __future__ import annotations

from devtools.ribbon_analysis.inspection.geometry import (
    PathSnapshot,
    Section,
    circle_section,
    guide,
    local_frame,
)
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute


def freeze(route: FoldRoute, identifier: str) -> PathSnapshot:
    """
    Freeze three material guides and seventeen sections without constructing geometry from cubics.

    Native construction uses the exact serialized fold route. These256interval
    cubics and section outlines are an inspection approximation only.
    """
    half = route.half_width_mm
    offsets = ((0, 0.0),) if route.targets.lines == 1 else ((-1, half), (0, 0.0), (-2, -half))
    curves = tuple(guide(number, lambda u, q=q: route.lane(u, q), 256) for number, q in offsets)
    sections = []
    for index in range(17):
        u = index / 16
        point, velocity, across, _ = route.surface(u, 0.0)
        frame = local_frame(point, velocity, across)
        sections.append(
            circle_section(index, u, frame, route.targets.diameter_mm)
            if route.targets.lines == 1
            else Section(
                index,
                u,
                frame,
                (route.lane(u, half)[0], route.lane(u, -half)[0]),
                "material_ruling",
            )
        )
    return PathSnapshot(
        identifier, route.targets.lines, route.targets.diameter_mm, 256, curves, tuple(sections)
    )
