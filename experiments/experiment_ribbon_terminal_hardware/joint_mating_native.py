"""
Keep active native floors inside one bounded fixed-fold mating projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.native_length import minimum_coordinate
from experiments.experiment_ribbon_fold_route.straight_closure import SourceReadiness, prepare

from .active_projection import ActiveFaces, active_step
from .feature_plane import SignedJoints


def at_floor(model: SignedJoints, values: tuple[float, ...], minimum_mm: float) -> bool:
    """
    Select bounded algebra before projection when an occupied slot is at its native face.

    Other poses retain the original affine arithmetic. This selects one kernel,
    not an additional attempt after an unconstrained proposal has declined.
    """
    if minimum_mm <= 0:
        return False
    floor = minimum_coordinate(minimum_mm, model.scale)
    return floor is not None and any(0 < values[i] <= floor for i in model.straight_indices)


@dataclass(frozen=True)
class _Domain:
    """
    Bind occupied straight coordinates to their strict native floor and original upper bound.
    """

    source: SignedJoints
    indices: tuple[int, ...]
    minimum: float

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Preserve the original coordinate box while keeping positive material constructible.
        """
        low, high = self.source.bounds(self.indices[index])
        return max(low, self.minimum), high


def project(
    route: FoldRoute,
    model: SignedJoints,
    values: tuple[float, ...],
    checkpoint: Callable[[], None],
    *,
    minimum_mm: float,
    fixed: frozenset[int],
    readiness: SourceReadiness = SourceReadiness.FINAL_SHAPE,
) -> tuple[float, ...] | None:
    """
    Return one native-bounded proposal using the existing sixteen-update working-set kernel.

    Shared preparation preserves exact slot identity, strict frame preconditions
    and absent/fixed material. Fold coordinates never move. The six kernel rows
    contain three positional equations and three unchanged orientation equations;
    a constant satisfied inequality fills its required inequality slot.
    Completed active faces supply their exact bound coordinates, avoiding
    cancellation in endpoint arithmetic. Actual mating, all native bounds and
    physical certificates still require independent checks by the caller.
    """
    indices = model.straight_indices
    space = prepare(
        route.pieces,
        route.targets,
        tuple(values[i] * model.scale for i in indices),
        checkpoint,
        fixed_slots=frozenset(slot for slot, index in enumerate(indices) if index in fixed),
        readiness=readiness,
    )
    if space is None:
        return None
    if space.already_closed:
        return values
    floor = minimum_coordinate(minimum_mm, model.scale)
    if floor is None:
        return None
    active = tuple(indices[slot] for slot in space.active)
    domain = _Domain(model, active, floor)
    if any(domain.bounds(i)[0] > domain.bounds(i)[1] for i in range(len(active))):
        return None
    rows = [[getattr(space.directions[slot], axis) for slot in space.active] for axis in "xyz"] + [
        [0.0] * len(active) for _ in range(4)
    ]
    residual = tuple(-getattr(space.offset, axis) / model.scale for axis in "xyz") + (
        0.0,
        0.0,
        0.0,
        -1.0,
    )
    faces = ActiveFaces()
    delta = active_step(
        domain, tuple(values[i] for i in active), rows, residual, checkpoint, faces=faces
    )
    if delta is None:
        return None
    result = list(values)
    for slot, index in enumerate(active):
        low, high = domain.bounds(slot)
        result[index] = (
            low
            if slot in faces.lower
            else high
            if slot in faces.upper
            else values[index] + delta[slot]
        )
    checkpoint()
    return tuple(result)
