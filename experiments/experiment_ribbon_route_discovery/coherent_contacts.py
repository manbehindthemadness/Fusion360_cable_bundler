"""
Form bounded, consistently oriented escape hypotheses for sampled crossing regions.

These support planes guide search only. They do not certify swept-surface contact
or change the physical thickness, and both escape signs must be tested separately.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from cable_bundler.routing.geometry import Vector3, dot
from experiments.experiment_ribbon_cap_transition.edge_clearance import NearPair

from .guidance import PlanePair, from_witness


@dataclass(frozen=True)
class CrossingModel:
    """
    Retain at most eight spatially distributed planes and omitted-direction counts.
    """

    planes: tuple[PlanePair, ...]
    components: int
    flipped: int
    ambiguous: int


def build(pairs: tuple[NearPair, ...], thickness_mm: float) -> CrossingModel:
    """
    Connect129-grid pairs within two stations and propagate a consistent normal sign.

    Region connectivity is a planner heuristic, not a material partition. Keep
    each region's closest witness before filling remaining slots by farthest
    material-pair distance. Exact parallel coincidences remain unmodeled; final
    full-width auditing must reject them. Selection uses at most eight passes;
    neighbor discovery uses a fixed25-cell stencil rather than an all-pairs scan.
    """
    if not math.isfinite(thickness_mm) or thickness_mm <= 0:
        raise ValueError("Crossing guidance requires positive finite thickness.")
    ordered = sorted(pairs, key=lambda p: (p.distance_mm, p.first.fraction, p.second.fraction))
    cells = {(round(p.first.fraction * 128), round(p.second.fraction * 128)): p for p in ordered}
    normals: dict[tuple[int, int], PlanePair] = {}
    seeds: list[tuple[int, int]] = []
    visited: set[tuple[int, int]] = set()
    flipped = ambiguous = 0
    for pair in ordered:
        cell = (round(pair.first.fraction * 128), round(pair.second.fraction * 128))
        if cell in visited:
            continue
        seeds.append(cell)
        queue: list[tuple[tuple[int, int], PlanePair | None]] = [(cell, None)]
        visited.add(cell)
        for current, parent in queue:
            witness = cells[current]
            try:
                plane = from_witness(
                    witness.first,
                    witness.second,
                    (witness.first_point, witness.second_point),
                    1.05 * thickness_mm,
                )
            except ValueError:
                # Exact parallel coincidence has no geometrically justified side.
                ambiguous += 1
                plane = parent
            else:
                if parent is not None and dot(plane.normal, parent.normal) < 0:
                    plane = replace(plane, normal=Vector3(0, 0, 0).translated(plane.normal, -1))
                    flipped += 1
                normals[current] = plane
            for du in range(-2, 3):
                for dv in range(-2, 3):
                    neighbor = (current[0] + du, current[1] + dv)
                    if neighbor in cells and neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, plane))
    chosen = [cell for cell in seeds if cell in normals][:8]
    while len(chosen) < min(8, len(normals)):
        remaining = [cell for cell in normals if cell not in chosen]
        if not chosen:
            chosen.append(remaining[0])
            continue
        chosen.append(
            max(
                remaining,
                key=lambda c: (
                    min((c[0] - q[0]) ** 2 + (c[1] - q[1]) ** 2 for q in chosen),
                    -c[0],
                    -c[1],
                ),
            )
        )
    return CrossingModel(tuple(normals[cell] for cell in chosen), len(seeds), flipped, ambiguous)
