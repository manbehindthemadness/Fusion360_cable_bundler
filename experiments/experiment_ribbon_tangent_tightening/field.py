"""
Add smooth local bending freedoms to the retained compatible material field.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from experiments.experiment_ribbon_cap_transition.director_routing_field import RoutingField


@dataclass(frozen=True)
class TangentTightening:
    """
    Select independent start/end windows in normalized carrier coordinates.

    Zero disables an end; enabled windows occupy 1/16 through 1/4 of the carrier.
    These are search supports, not physical straight-lead lengths or bend limits.
    The minimum support spans four intervals on the retained coarse grid.
    """

    start_fraction: float = 0.25
    end_fraction: float = 0.25

    def __post_init__(self) -> None:
        """
        Reject nonfinite, unresolved or overlapping terminal search windows.
        """
        for fraction in (self.start_fraction, self.end_fraction):
            if (
                isinstance(fraction, bool)
                or not math.isfinite(fraction)
                or (fraction != 0 and not 1 / 16 <= fraction <= 1 / 4)
            ):
                raise ValueError("Terminal windows must be zero or within [1/16, 1/4].")

    @property
    def dimensions(self) -> int:
        """
        Count the base ten coordinates plus one amplitude per enabled end.
        """
        return 10 + int(self.start_fraction > 0) + int(self.end_fraction > 0)


def _bump(distance: float, extent: float) -> float:
    """
    Return a unit-peak pulse with zero value and two derivatives at both boundaries.
    """
    if extent == 0 or distance >= extent:
        return 0.0
    fraction = distance / extent
    return 64 * fraction**3 * (1 - fraction) ** 3


@dataclass(frozen=True)
class TerminalRoutingField(RoutingField):
    """
    Vary signed turn near either cap while preserving terminal ruling and cap turn.

    The added raw turn vanishes with two derivatives at each window boundary.
    CompatibleField still applies its original curvature/material map afterward;
    raw amplitudes do not grant a radius exemption. End pose remains a fit target.
    """

    tightening: TangentTightening = TangentTightening()
    start_turn: float = 0.0
    end_turn: float = 0.0

    def __post_init__(self) -> None:
        """
        Validate finite amplitudes and refuse active turn on a disabled end.
        """
        super().__post_init__()
        if not isinstance(self.tightening, TangentTightening):
            raise ValueError("Choose a terminal tightening policy.")
        for turn, extent in (
            (self.start_turn, self.tightening.start_fraction),
            (self.end_turn, self.tightening.end_fraction),
        ):
            if not math.isfinite(turn) or (extent == 0 and turn != 0):
                raise ValueError("Terminal turn must be finite and zero at disabled ends.")

    def sample(self, u: float) -> tuple[float, float, float]:
        """
        Add independent compact bend pulses without changing the ruling field.
        """
        curvature, eta, eta_s = super().sample(u)
        turn = self.start_turn * _bump(u, self.tightening.start_fraction)
        turn += self.end_turn * _bump(1 - u, self.tightening.end_fraction)
        return curvature + turn / self.length_mm, eta, eta_s
