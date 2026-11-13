"""
Derive only local algebraic roots under one shared, nonrenewable choice budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from experiments.experiment_ribbon_feature_insertion.allocation import fit
from experiments.experiment_ribbon_feature_insertion.deviation_guide import DeviationGuide
from experiments.experiment_ribbon_feature_insertion.features import Chain, chains
from experiments.experiment_ribbon_feature_insertion.reclosure import ReclosureAllocation
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps
from experiments.experiment_ribbon_joint_route.boundary import Boundary

from .adaptive_event_plan import Proposal
from .deviation_closure import close


@dataclass
class Roots:
    """
    Count all fitted choices across local windows without resetting at a topology rewrite.
    """

    attempted: int = 0
    declined: int = 0
    newton_steps: int = 0
    newton_limit: int = 24
    reclosures: int = 0

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
        if (
            any(
                type(value) is not int
                for value in (self.newton_steps, self.newton_limit, self.reclosures)
            )
            or not 0 <= self.newton_steps <= self.newton_limit <= 24
            or not 0 <= self.reclosures <= 4
        ):
            raise ValueError("Retain the original shared correction accounting")


def construct(
    proposal: Proposal,
    minimum_straight_mm: float,
    roots: Roots,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> FoldRoute | None:
    """
    Construct the guide's actual steering stages and stop at the first boundary-closed allocation.

    Each local stage has at most six folds/eight roots/128 straight masks. The
    parent route has no event-count cap. Eight fitted choices are shared across
    all windows. If exact fits decline, one closest actually attempted root can
    use at most four remaining angle corrections inside this charged update.
    Measured native-cone closure avoids renewed guide masks; no new root,
    offset or alternative family follows a failed correction.
    Full-route acceptance and optional module removal belong to the controller.
    Finite correction may change the material bend branch. Optimizer trajectory
    continuity grants no physical acceptance; full-route proofs remain required.
    A deviation uses its two analytic slope extrema. Its midpoint has zero
    added tangent and cannot describe the bump's outward-and-return headings.
    Ordinary guides retain their midpoint reference. Fewer folds are preferred
    among exact factorizations of the selected stages, not by discarding them.
    """
    local = proposal.window.route
    boundary = Boundary(local.targets, local.radius_mm)
    attempted: list[Chain] = []

    def local_record(event: dict[str, Any]) -> None:
        """
        Mark local algebra separately from original global construction evidence.
        """
        if event.get("stage") == "feature_reclosure_step" and event.get("status") == "started":
            if roots.newton_steps >= roots.newton_limit:
                raise ArithmeticError("Local correction renewed its original allowance")
            roots.newton_steps += 1
        record({**event, "adaptive_window": [proposal.window.begin, proposal.window.end]})

    stages = (
        (DeviationGuide.stations(),)
        if isinstance(proposal.frames.guide, DeviationGuide)
        else ((0.5,),)
    )
    for parameters in stages:
        checkpoint()
        if roots.attempted >= 8:
            break
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
                break
            checkpoint()
            roots.attempted += 1
            attempted.append(chain)
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
    if attempted:
        roots.reclosures += 1
        repaired = close(
            boundary,
            attempted,
            minimum_straight_mm,
            proposal.frames.guide.distances[-1],
            checkpoint,
            local_record,
            maximum_steps=min(4, roots.newton_limit - roots.newton_steps),
            allocation_policy=ReclosureAllocation.MEASURED,
        )
        if repaired is not None and ordered_mating_caps(repaired.route.pieces, local.targets):
            roots.declined -= 1
            local_record(
                {
                    "stage": "adaptive_local_closure",
                    "status": "closed",
                    "extra_guide_mask_enumerations": 0,
                    "roots": repaired.chain.roots,
                }
            )
            return repaired.route
    return None
