"""
Distinguish normalized restoration progress from measured ordered mating-cap completion.
"""

from __future__ import annotations

import math

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute


def ordered_caps_complete(route: FoldRoute, residual: tuple[float, ...]) -> bool:
    """
    Permit ordinary physical certification under the existing actual-cap and inequality gates.

    The first six normalized terms guide Newton restoration; they are not a
    world-space mating tolerance. Check both ordered side lanes and the center,
    including their actual position and frame, against the unchanged1e-7cap
    contract. Every represented inequality must still satisfy the original
    strict1e-13restoration gate. Nonfinite or incomplete equations fail closed.
    This grants no material, slot-size, topology, hardware or contact acceptance:
    those checks, their counters and the original recovery allowance still apply.
    """
    if len(residual) < 6 or any(not math.isfinite(term) for term in residual):
        return False
    if any(term >= 1e-13 for term in residual[6:]):
        return False
    error = cap_error(route)
    return math.isfinite(error) and error <= 1e-7
