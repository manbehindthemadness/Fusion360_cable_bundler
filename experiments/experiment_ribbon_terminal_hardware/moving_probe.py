"""
Focus negative hardware discovery on changed material without replacing full-route certification.
"""

from __future__ import annotations

from typing import Callable, Iterable

from experiments.experiment_ribbon_feature_insertion.separation import Region, regions
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece

from .feature_plane import FeaturePlane, SignedJoints
from .material_pose import current_regions
from .model import Hardware, Terminal
from .probe_domain import ProbeDomain


def moving_domain(
    route: FoldRoute,
    model: SignedJoints,
    values: tuple[float, ...],
    hardware: Hardware,
    planes: Iterable[FeaturePlane],
    checkpoint: Callable[[], None],
) -> ProbeDomain | None:
    """
    Select moved actual members lacking existing complete hardware guidance for each box.

    Resolve stable slots against the exact current placement. Missing original
    slots may appear; they count as changed, never as an inherited clearance.
    Prefer already involved terminals and reverse material order within each.
    Own mating material is left to its existing guidance and complete final
    check, avoiding meaningless open-cap starvation in this negative-only tool.
    Unchanged or guided members are omitted only from optional discovery.
    """
    checkpoint()
    tags = current_regions(route, model, values)
    if tags is None or route.targets != hardware.targets:
        return None
    original_tags = regions(model.original)
    if len(set(original_tags)) != len(original_tags):
        return None
    original: dict[Region, PlacedPiece] = dict(zip(original_tags, model.original.pieces))
    owned = tuple(plane for plane in planes if plane.model is model and plane.box in hardware.boxes)
    terminals = tuple(
        dict.fromkeys(
            [plane.box.terminal for plane in owned] + [box.terminal for box in hardware.boxes]
        )
    )
    pairs: list[tuple[Terminal, int]] = []
    for terminal in terminals:
        covered = {
            member for plane in owned if plane.box.terminal is terminal for member in plane.members
        }
        mating_index = len(route.pieces) - 1 if terminal is Terminal.END else 0
        for index in reversed(range(len(route.pieces))):
            checkpoint()
            tag, piece = tags[index], route.pieces[index]
            before = original.get(tag)
            if index == mating_index or tag in covered:
                continue
            if (
                before is not None
                and before.pose == piece.pose
                and before.geometry == piece.geometry
            ):
                continue
            pairs.append((terminal, index))
    checkpoint()
    return ProbeDomain(route, tuple(pairs)) if pairs else None
