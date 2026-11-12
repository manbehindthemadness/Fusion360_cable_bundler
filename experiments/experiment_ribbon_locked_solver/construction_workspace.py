"""
Recognize strict construction returns contained in one closed local work area.
"""

from __future__ import annotations

from experiments.experiment_ribbon_fold_route.contact import Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_window import (
    Window,
    events,
    select,
)


def closed_return(source: FoldRoute, witness: Penetration) -> Window | None:
    """
    Prefer a local rewrite only when both colliders share travel and an outer bend can survive.

    Keep the existing deterministic window selector. A whole-route rewrite,
    nonlocal collision or absence of straight workspace retains ordinary
    reversal. This is strategy eligibility, not a feasibility or clearance
    claim. The adaptive planner must still revalidate both occupied preimages,
    and all changed geometry needs new complete contact/hardware certificates.
    """
    if not ordered_mating_caps(source.pieces, source.targets):
        return None
    window = select(source, witness.pieces)
    if not all(window.begin <= member < window.end for member in witness.pieces):
        return None
    pieces = source.pieces[window.begin : window.end]
    if not any(isinstance(piece.geometry, Straight) for piece in pieces):
        return None
    if not 0 < events(window.route) < events(source):
        return None
    return window
