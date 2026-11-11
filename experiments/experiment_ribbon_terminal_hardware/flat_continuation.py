"""
Retain one current closed flat crossing within the existing fixed-bend hardware domain.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .contact_addition import Addition, ContactPolicy
from .contact_addition import prepare as prepare_addition
from .feature_plane import SignedJoints
from .flat_separation import FlatSeparation
from .joint_handoff import JointHandoff
from .material_constraint import MaterialConstraint


class ContactContinuation(Enum):
    """
    Keep the default immediate handoff distinct from one opted-in complete flat constraint.
    """

    HANDOFF = "handoff"
    FIRST_FLAT = "first_flat"


@dataclass(frozen=True)
class ClosedFlatContinuation:
    """
    Retain current coordinates and strict closed evidence without granting clearance or another budget.
    """

    values: tuple[float, ...]
    state: JointHandoff
    addition: Addition

    @classmethod
    def prepare(
        cls,
        model: SignedJoints,
        route: FoldRoute,
        contact: ContactResult,
        values: tuple[float, ...],
    ) -> ClosedFlatContinuation | None:
        """
        Bind complete current-pose flat phases only; curved or uncertain evidence grants no retention.

        The original full checker supplies the strict witness. Its complete
        regions, fixed axis and chosen side are conservative guidance, never
        a reused certificate. Exact model-pose equality and both original inverse
        maps revalidate this same occupied point. The caller charges preparation
        and every later projection/proof to its existing allocation and constraint
        capacities.
        """
        if contact.status != "penetration" or contact.witness is None or contact.limit is not None:
            return None
        current = model.pieces(values)
        if route.targets != model.original.targets or tuple(
            (piece.pose, piece.geometry) for piece in current
        ) != tuple((piece.pose, piece.geometry) for piece in route.pieces):
            return None
        entry = prepare_addition(model, route, contact, values, ContactPolicy.RESTORATION)
        if (
            entry is None
            or not isinstance(entry.bound, MaterialConstraint)
            or not isinstance(entry.bound.bound, FlatSeparation)
        ):
            return None
        witness = contact.witness
        for index, expected in zip(witness.pieces, (witness.first, witness.second)):
            measured = occupied_coordinates(
                route.pieces[index], witness.point, route.targets.lines, route.targets.diameter_mm
            )
            if measured != expected:
                return None
        return cls(values, JointHandoff(route, contact), entry)

    def unchanged(self, values: tuple[float, ...], route: FoldRoute) -> bool:
        """
        Permit fallback only for the identical immutable closed state, never a witness after motion.
        """
        return values == self.values and route == self.state.route
