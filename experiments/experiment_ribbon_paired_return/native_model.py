"""
Compensate signed material joints at external caps while retaining native straight floors.
"""

from __future__ import annotations

from functools import cached_property

from experiments.experiment_ribbon_fold_relaxation.steps import MAXIMUM_ANGULAR_STEP_RADIANS
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.native_length import minimum_coordinate
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints


class NativeJoints(SignedJoints):
    """
    Keep original fold signs/radii and external cap equations without fixing internal frames.

    Positive source straights retain the unchanged strict native minimum. Newly
    activated subminimum slots may be extended and pinned by the existing native
    slot policy, then reclosed within the same remaining numerical allocation.
    No source material is deleted and no event or radius coordinate is added.
    """

    native_floor: float
    native_pins: dict[int, float]

    def __init__(self, original: FoldRoute, minimum_straight_mm: float) -> None:
        """
        Bind the original native minimum before any derivative or motion proposal.
        """
        super().__init__(original)
        floor = minimum_coordinate(minimum_straight_mm, self.scale)
        if floor is None:
            raise ValueError("Use a representable positive native floor")
        object.__setattr__(self, "native_floor", floor)
        object.__setattr__(self, "native_pins", {})

    @cached_property
    def bank_indices(self) -> tuple[int, ...]:
        """
        Identify all existing independent material banks for diagnostic reporting.
        """
        return tuple(i for i, index in enumerate(self.indices) if index % 4 == 2)

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Preserve native floors and exact positive extension pins alongside original material bounds.
        """
        low, high = super().bounds(index)
        if index in self.native_pins:
            value = self.native_pins[index]
            return value, value
        if index in self.straight_indices and self.initial[index] > 0:
            low = max(low, self.native_floor)
        return low, high

    def allows_step(self, before: tuple[float, ...], after: tuple[float, ...]) -> bool:
        """
        Apply the original angular motion ceiling to every signed angle and bank.
        """
        return all(
            abs(a - b) <= MAXIMUM_ANGULAR_STEP_RADIANS
            for i, (a, b) in enumerate(zip(before, after))
            if i not in self.straight_indices
        )
