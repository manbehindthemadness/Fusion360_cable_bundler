"""
Share bounded exact joint evaluations while actual constraint changes invalidate only equations.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable


class JointEvaluation:
    """
    Own at most64equation and64domain results for one immutable joint model.

    Exact coordinate tuples retain the original floating-point equations and
    domain decisions. Call constraints_changed after adding a measured bound or
    changing the quality equation; domain results remain valid for this fixed
    model. This grants no new probes, strategies, work or physical tolerances.
    Caller checkpoints remain outside these pure callbacks and are never cached.
    """

    def __init__(
        self,
        equations: Callable[[tuple[float, ...]], tuple[float, ...]],
        admissible: Callable[[tuple[float, ...]], bool],
    ) -> None:
        """
        Bind pure callbacks to one recovery action without retaining other models globally.
        """
        self._equations = lru_cache(maxsize=64)(equations)
        self._admissible = lru_cache(maxsize=64)(admissible)

    def equations(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Return the exact raw equations for these coordinates and current constraint state.
        """
        return self._equations(values)

    def admissible(self, values: tuple[float, ...]) -> bool:
        """
        Preserve the fixed model's exact material-domain decision at these coordinates.
        """
        return self._admissible(values)

    def constraints_changed(self) -> None:
        """
        Discard all old equations after actual bound or quality-policy changes.
        """
        self._equations.cache_clear()
