"""
Keep legacy route closure distinct from proof-ready actual mating precision during bounded reclosure.
"""

from __future__ import annotations

from enum import Enum

from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.mating import MATING_FRAME_LIMIT, ordered_mating_caps


class ClosureGoal(Enum):
    """
    Select the stopping precondition without renewing corrections or relaxing any allocation contract.
    """

    ROUTE = "route"
    MATING = "mating"

    @property
    def minimum_angular_norm(self) -> float:
        """
        Keep the legacy angular floor; requested mating work must reach actual pose precision instead.
        """
        return 0.0 if self is ClosureGoal.MATING else 1e-12

    def normalized_limit(self, diameter_mm: float) -> float:
        """
        Convert the requested positional precision into the closure residual's existing diameter units.
        """
        return (MATING_FRAME_LIMIT if self is ClosureGoal.MATING else 1e-7) / diameter_mm

    def improves(self, before: float, after: float, diameter_mm: float) -> bool:
        """
        Preserve the original gain floor, bounded by half the remaining mating defect when requested.

        A diameter-normalized absolute floor cannot veto the smaller correction
        needed by a fixed millimeter proof criterion. The strict decrease and
        original halving/correction limits still govern every accepted step.
        """
        gain = 1e-10
        if self is ClosureGoal.MATING:
            gain = min(gain, max(0.0, (before - self.normalized_limit(diameter_mm)) / 2))
        return after < before - gain

    def accepts(self, route: FoldRoute) -> bool:
        """
        Apply the requested extra mating precondition only after original allocation validation.

        ROUTE adds no new work or gate to legacy validated allocations. MATING
        checks actual ordered cap poses; this grants no contact or hardware proof.
        """
        return self is ClosureGoal.ROUTE or ordered_mating_caps(route.pieces, route.targets)
