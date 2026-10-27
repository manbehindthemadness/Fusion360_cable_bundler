"""
Select distinct geometric starts without treating seed labels as route diversity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Seed:
    """
    Freeze one scored start and width-normalized A/center/B sample coordinates.

    Descriptors share a fixture and sample order. They measure geometric separation,
    not homotopy, feasibility, or an invariant classification under reparameterizing.
    """

    index: int
    coordinates: tuple[float, ...]
    score: float
    descriptor: tuple[float, ...]


def separation(left: Seed, right: Seed) -> float:
    """
    Measure RMS point separation in ribbon widths using matching spatial samples.
    """
    if not left.descriptor or len(left.descriptor) != len(right.descriptor):
        raise ValueError("Route descriptors must have matching nonempty dimensions.")
    if len(left.descriptor) % 3:
        raise ValueError("Route descriptors require complete three-coordinate points.")
    return math.sqrt(
        sum((a - b) ** 2 for a, b in zip(left.descriptor, right.descriptor))
        / (len(left.descriptor) / 3)
    )


def select(seeds: tuple[Seed, ...], *, maximum: int = 3) -> tuple[Seed, ...]:
    """
    Keep up to the explicit family limit,separated by half a ribbon width.

    Visit starts in ascending objective/index order. A start must differ from every
    retained start. Never fill an empty slot with a duplicate or infer feasibility
    from selection. The half-width threshold is a frozen search heuristic. The
    historical limit remains three;changing it requires a newly budgeted run.
    """
    if type(maximum) is not int or maximum < 1:
        raise ValueError("A positive integer family limit is required.")
    if len({seed.index for seed in seeds}) != len(seeds):
        raise ValueError("Seed identifiers must be unique.")
    dimensions = {len(seed.descriptor) for seed in seeds}
    if len(dimensions) > 1:
        raise ValueError("All descriptors must use the same samples.")
    for seed in seeds:
        if (
            not math.isfinite(seed.score)
            or seed.score < 0
            or not seed.descriptor
            or len(seed.descriptor) % 3
            or not all(math.isfinite(v) for v in seed.descriptor + seed.coordinates)
        ):
            raise ValueError(
                "Seeds require finite coordinates, descriptors and nonnegative scores."
            )
    selected: list[Seed] = []
    for seed in sorted(seeds, key=lambda item: (item.score, item.index)):
        if all(separation(seed, previous) >= 0.5 for previous in selected):
            selected.append(seed)
        if len(selected) == maximum:
            break
    return tuple(selected)
