"""
Reuse exact immutable material prefixes while keeping full-coordinate validation authoritative.
"""

from __future__ import annotations

from functools import cached_property, lru_cache
from typing import Callable

from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece

from .flexible import FlexibleModel


class PrefixModel(FlexibleModel):
    """
    Retain at most64exact coordinate-prefix placements within one immutable model.

    Late derivative probes reuse unchanged leading material. Every full request
    still validates every original coordinate bound; no solver step, checkpoint,
    geometry tolerance or arithmetic decision is replaced by cache lookup.
    Separate models own separate caches, with no global retention of routes.
    """

    @cached_property
    def _prefixes(self) -> Callable[[tuple[float, ...]], tuple[PlacedPiece, ...]]:
        """
        Bind bounded prefix reuse to this model's fixed original targets and material.
        """
        return lru_cache(maxsize=64)(self._prefix)

    def pieces(self, values: tuple[float, ...]) -> tuple[PlacedPiece, ...]:
        """
        Validate complete coordinates before reusing their exact immutable prefixes.
        """
        self._validate_values(values)
        return self._prefixes(values)

    def _prefix(self, values: tuple[float, ...]) -> tuple[PlacedPiece, ...]:
        """
        Extend an already validated prefix through one fold or the final runway slot.
        """
        index = (len(values) - 1) // 4
        previous = values[: 4 * index]
        output = list(self._prefixes(previous)) if previous else []
        self._append_segment(output, index, values)
        return tuple(output)
