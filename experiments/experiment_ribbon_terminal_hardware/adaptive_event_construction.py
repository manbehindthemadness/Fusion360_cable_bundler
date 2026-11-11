"""
Derive only local algebraic roots under one shared, nonrenewable choice budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from experiments.experiment_ribbon_feature_insertion.allocation import fit
from experiments.experiment_ribbon_feature_insertion.deviation_guide import DeviationGuide
from experiments.experiment_ribbon_feature_insertion.features import chains
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps
from experiments.experiment_ribbon_joint_route.boundary import Boundary

from .adaptive_event_plan import Proposal


@dataclass
class Roots:
    """
    Count all fitted choices across local windows without resetting at a topology rewrite.
    """

    attempted: int = 0
    declined: int = 0

    def __post_init__(self) -> None:
        """
        Refuse malformed or already enlarged choice accounting.
        """
        if (
            type(self.attempted) is not int
            or type(self.declined) is not int
            or not 0 <= self.declined <= self.attempted <= 8
        ):
            raise ValueError("Retain at most eight previously charged local roots")


def construct(
    proposal: Proposal,
    minimum_straight_mm: float,
    roots: Roots,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> FoldRoute | None:
    """
    Prefer fewer local bends and stop at the first fully boundary-closed allocation.

    Each local stage has at most six folds/eight roots/128 straight masks. The
    parent route has no event-count cap. Eight fitted choices are shared across
    all windows; no nonlinear reclosure or alternative offset search is added.
    Full-route acceptance and optional module removal belong to the controller.
    """
    local = proposal.window.route
    boundary = Boundary(local.targets, local.radius_mm)

    def local_record(event: dict[str, Any]) -> None:
        """
        Mark local algebra separately from original global construction evidence.
        """
        record({**event, "adaptive_window": [proposal.window.begin, proposal.window.end]})

    for parameters in ((0.5,), DeviationGuide.stations()):
        checkpoint()
        options = chains(boundary, proposal.frames, parameters, checkpoint, local_record)
        for chain in sorted(
            options,
            key=lambda c: (
                len(c.topology.folds),
                sum(f.material_length_mm for f in c.topology.folds),
                c.roots,
            ),
        ):
            if roots.attempted >= 8:
                return None
            checkpoint()
            roots.attempted += 1
            allocated = fit(
                boundary,
                chain,
                minimum_straight_mm,
                checkpoint,
                local_record,
                maximum_straight_mm=proposal.frames.guide.distances[-1],
            )
            if allocated is not None and ordered_mating_caps(allocated.route.pieces, local.targets):
                return allocated.route
            roots.declined += 1
    return None
