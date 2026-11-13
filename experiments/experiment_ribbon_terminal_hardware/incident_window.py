"""
Restrict a closed departure reversal to its witnessed material interval and boundary runways.
"""

from __future__ import annotations

from enum import Enum
from functools import cached_property
from typing import cast

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact import Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps

from .incident_model import IncidentJoints
from .material_return_selection import select_fold


class ReturnCoordinates(Enum):
    """
    Select the original global joints or one actual closed departure interval before correction.
    """

    GLOBAL = "global"
    WITNESSED_INTERVAL = "witnessed_interval"


class IncidentWindow(IncidentJoints):
    """
    Reflect the outgoing carrier while holding remote material coordinates unchanged.

    The actual first and last occupied pieces determine the movable fold span.
    Both bounding straight slots remain free, including absent zero slots. No
    event-count limit or new event is introduced. Endpoint closure, separation
    and terminal proofs remain the original caller's responsibility; a local
    decline does not authorize widening or another optimizer.
    """

    window: tuple[int, int]

    def __init__(self, original: FoldRoute, selected: int, witness: Penetration) -> None:
        """
        Require a closed outgoing witness carried by the selected existing base fold.
        """
        select_fold(original, witness)
        first, last = witness.pieces
        geometry = original.pieces[first].geometry
        if type(geometry) is not CylindricalFold or not ordered_mating_caps(
            original.pieces, original.targets
        ):
            raise ValueError("Local reversal requires a closed base-fold departure")
        _, exit_fraction = cast(CylindricalFold, geometry).bend_interval(witness.first[1])
        first_fold = sum(
            isinstance(piece.geometry, CylindricalFold) for piece in original.pieces[:first]
        )
        last_fold = (
            sum(
                isinstance(piece.geometry, CylindricalFold) for piece in original.pieces[: last + 1]
            )
            - 1
        )
        if selected != first_fold or witness.first[0] < exit_fraction:
            raise ValueError("Local reversal must select the witnessed outgoing carrier")
        super().__init__(original, selected)
        object.__setattr__(self, "window", (first_fold, last_fold))

    @cached_property
    def indices(self) -> tuple[int, ...]:
        """
        Keep actual interval joints and both bordering straight slots in full material order.
        """
        first, last = self.window
        return tuple(index for index in super().indices if 4 * first <= index <= 4 * (last + 1))
