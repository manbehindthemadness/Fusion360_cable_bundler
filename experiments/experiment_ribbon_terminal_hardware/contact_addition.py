"""
Prepare one complete material constraint while preserving each recovery entry's coverage policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from experiments.experiment_ribbon_feature_insertion.separation import Side
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .feature_plane import SignedJoints
from .flat_separation import FlatSeparation, ProfileExtent
from .material_constraint import MaterialConstraint


class ContactPolicy(Enum):
    """
    Retain legacy contact coverage and distinguish a current-pose restoration witness.
    """

    COUPLED = "coupled"
    MATERIAL_RETURN = "material_return"
    COMPLETE_FLAT = "complete_flat"
    ARC_FLAT = "arc_flat"
    RESTORATION = "restoration"


@dataclass(frozen=True)
class Addition:
    """
    Retain one derived bound, its separating direction and unchanged duplicate identity.
    """

    bound: FlatSeparation | MaterialConstraint
    side: Side
    key: tuple[Any, ...]
    witness: Penetration | None


def prepare(
    model: SignedJoints,
    route: FoldRoute,
    measurement: ContactResult,
    values: tuple[float, ...],
    policy: ContactPolicy,
) -> Addition | None:
    """
    Prepare guidance without mutating recovery state or claiming clearance.

    Legacy coupled and material-return paths retain their original complete
    coverage and axis selection. A restoration witness uses current coordinates
    for its axis and separating side, with stable full-region duplicate identity.
    """
    if not isinstance(policy, ContactPolicy):
        raise ValueError("Use an explicit material constraint policy")
    witness = measurement.witness
    bound: MaterialConstraint | FlatSeparation | None
    if policy is ContactPolicy.RESTORATION:
        if measurement.status != "penetration" or witness is None:
            return None
        bound = MaterialConstraint.from_witness(model, route, witness, axis_values=values)
    elif policy in (ContactPolicy.COUPLED, ContactPolicy.MATERIAL_RETURN):
        bound = MaterialConstraint.create(model, route, measurement)
    else:
        if witness is None:
            return None
        bound = FlatSeparation.create(
            model,
            route,
            witness,
            extent=ProfileExtent.COMPLETE
            if policy is ContactPolicy.COMPLETE_FLAT
            else ProfileExtent.ARC,
        )
    if bound is None:
        return None
    if policy in (ContactPolicy.COUPLED, ContactPolicy.RESTORATION):
        key = (bound.pair, bound.parts)
        reference = values
    else:
        if witness is None:
            return None
        key = (
            bound.pair,
            tuple(round(v, 8) for v in witness.first[:2]),
            tuple(round(v, 8) for v in witness.second[:2]),
        )
        reference = model.initial
    gaps = (bound.gap(reference, Side.BEFORE), bound.gap(reference, Side.AFTER))
    side = Side.AFTER if gaps[1] > gaps[0] else Side.BEFORE
    return Addition(bound, side, key, witness)
