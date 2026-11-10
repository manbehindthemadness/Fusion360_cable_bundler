"""
Retain complete flat phases or analytic whole-piece bounds in one coupled material correction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from experiments.experiment_ribbon_feature_insertion.separation import Region, Separation, Side
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .feature_plane import SignedJoints
from .flat_separation import FlatPart, FlatSeparation, ProfileExtent


@dataclass(frozen=True)
class MaterialConstraint:
    """
    Keep the shared complete-material projection as conservative guidance, never a clearance certificate.
    """

    bound: FlatSeparation | Separation

    @classmethod
    def create(
        cls, model: SignedJoints, route: FoldRoute, measurement: ContactResult
    ) -> MaterialConstraint | None:
        """
        Prefer complete flat phases; strict curved witnesses may guide complete analytic pieces.

        Mixed depth uncertainty remains unsupported. Whole-piece guidance retains
        all curved and flat material on both identified pieces; it never shrinks
        to a witness neighborhood or substitutes a sampled display mesh.
        """
        witness = measurement.witness
        if measurement.status != "penetration" or witness is None:
            flat = FlatSeparation.from_measurement(model, route, measurement)
            return None if flat is None else cls(flat)
        return cls.from_witness(model, route, witness)

    @classmethod
    def from_witness(
        cls,
        model: SignedJoints,
        route: FoldRoute,
        witness: Penetration,
        *,
        axis_values: tuple[float, ...] | None = None,
    ) -> MaterialConstraint | None:
        """
        Bind an existing strict witness to complete material guidance without inventing another measurement.

        An explicit working pose orients the existing flat SAT choice after a
        prescribed joint rewrite. Original witness regions, phases and complete
        coverage stay unchanged. Curved whole-piece guidance retains its original
        witness normal and does not use this flat-axis option.
        """
        first, second = witness.pieces
        if any(type(i) is not int for i in witness.pieces) or not 0 <= first < second < len(
            route.pieces
        ):
            return None
        for coordinates in (witness.first, witness.second):
            if len(coordinates) != 3 or any(
                type(value) not in (int, float) or not math.isfinite(value) for value in coordinates
            ):
                return None
            u, q, height = coordinates
            if not (
                0 <= u <= 1
                and abs(q) <= route.half_width_mm
                and abs(height) <= route.targets.diameter_mm / 2
            ):
                return None
        flat = FlatSeparation.create(
            model, route, witness, extent=ProfileExtent.COMPLETE, axis_values=axis_values
        )
        return cls(Separation.create(model, route, witness) if flat is None else flat)

    @property
    def pair(self) -> tuple[Region, Region]:
        """
        Preserve stable ordered material identities while independent straight slots appear.
        """
        return self.bound.pair

    @property
    def parts(self) -> tuple[FlatPart, ...]:
        """
        Describe flat phases, using an empty tuple to identify whole-piece curved guidance.
        """
        return self.bound.parts if isinstance(self.bound, FlatSeparation) else ()

    def gap(self, values: tuple[float, ...], side: Side) -> float:
        """
        Re-enclose complete material under current joint coordinates using the retained separating axis.
        """
        return self.bound.gap(values, side)
