"""
Keep bounded exact placement queries private to a model without retaining that model through a cycle.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable, TypeVar
from weakref import ref

from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece

Owner = TypeVar("Owner")
Coordinates = tuple[float, ...]
Placement = tuple[PlacedPiece, ...]


def placement_cache(
    owner: Owner, place: Callable[[Owner, Coordinates], Placement]
) -> Callable[[Coordinates], Placement]:
    """
    Retain at most64exact queries without a strong reference back to the owning model.

    Supply the original unbound implementation, preserving subclass dispatch at
    binding time. A call holds its owner strongly for its entire computation.
    An externally retained cache can still return immutable hits after owner
    release; a miss then raises ReferenceError rather than recreating a model.
    """
    owner_reference = ref(owner)

    @lru_cache(maxsize=64)
    def query(values: Coordinates) -> Placement:
        """
        Evaluate the unchanged placement only while its model is alive; failed queries are never cached.
        """
        current = owner_reference()
        if current is None:
            raise ReferenceError("Placement query outlived its owning model")
        return place(current, values)

    return query
