"""
Carry strictly verified current-pose material intrusion without transferring cap closure or acceptance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

RestorationStop = Literal["linear_projection_infeasible", "joint_no_descent", "new_material_return"]


@dataclass(frozen=True)
class RestorationHandoff:
    """
    Retain rejected restoration geometry and its unchanged strict material witness only.

    Caps remain uncertified. Two original inverse maps revalidate this same
    already measured point, including exact material coordinates. The caller
    charges validation and preparation to its original clock; this grants no
    new comparison pool, logical update, physical certificate or native attempt.
    An opted-in early transfer uses the same strict witness checks when its
    interval selects a distinct not-yet-reflected return before another update.
    """

    route: FoldRoute
    evidence: ContactResult
    stop_reason: RestorationStop

    def __post_init__(self) -> None:
        """
        Reject unknown, stale, malformed or nonmaterial evidence without requiring cap closure.
        """
        if self.stop_reason not in (
            "linear_projection_infeasible",
            "joint_no_descent",
            "new_material_return",
        ):
            raise ValueError(
                "Restoration handoff requires an ordinary stop or a strict new material return"
            )
        if not isinstance(self.evidence, ContactResult):
            raise ValueError("Restoration handoff requires material evidence only")
        witness = self.evidence.witness
        if (
            self.evidence.status != "penetration"
            or witness is None
            or self.evidence.limit is not None
        ):
            raise ValueError("Restoration handoff requires a strict material penetration")
        first, second = witness.pieces
        if any(type(index) is not int for index in witness.pieces) or not 0 <= first < second < len(
            self.route.pieces
        ):
            raise ValueError("Restoration witness must identify ordered existing material")
        for index, expected in zip(witness.pieces, (witness.first, witness.second)):
            if len(expected) != 3 or any(
                type(value) not in (int, float) or not math.isfinite(value) for value in expected
            ):
                raise ValueError("Restoration witness requires finite material coordinates")
            measured = occupied_coordinates(
                self.route.pieces[index],
                witness.point,
                self.route.targets.lines,
                self.route.targets.diameter_mm,
            )
            if measured is None or measured != expected:
                raise ValueError("Restoration witness must match this exact current material pose")
        if not math.isfinite(cap_error(self.route)) or not material_error(self.route) <= 1e-10:
            raise ValueError("Restoration handoff requires finite targets and consistent material")
