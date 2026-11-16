"""
Combine original profile and longitudinal-cut bounds into one whole native-face domain accuracy allowance.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction

from .flat_cut_domain import FlatCutDomain
from .native_profile_accuracy import NativeProfileAccuracy


@dataclass(frozen=True)
class NativeFlatDomainAccuracy:
    """
    Bound distance to the ORIGINAL trimmed flat domain without changing actual coordinates or geometry.

    A profile witness at the same s has combined material/world L1 error D.
    Moving that witness into its original nonempty longitudinal interval costs
    at most E+max(abs(cut slopes))*D in physical s, where E is the owned combined
    cut excursion. Multiplying by max(1,world L1 norm of the s column) bounds
    both material and world error. The sum shares ONE dimensional allowance.
    This is a distance witness, not coordinate clamping, material isometry or
    proof that an ideal source domain is exactly equal to the native trim.
    """

    profile: NativeProfileAccuracy
    cuts: FlatCutDomain
    checkpoint: InitVar[Callable[[], None]]
    minimum_source_width_mm: Fraction = field(init=False)
    distance_upper_mm: Fraction | None = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Bind SAME native/source owners and preserve zero tips while refusing an unproved nonempty source domain.
        """
        checkpoint()
        frame = self.profile.frame
        if self.cuts.frame is not frame or any(
            box.native is not self.cuts.low_box.native for box in self.profile.boxes
        ):
            raise ValueError("The SAME original frame and native face required")
        width = min(
            frame.high.at(Fraction(q)) - frame.low.at(Fraction(q))
            for q, _ in self.profile.conic.arc.controls
        )
        distance = None
        profile_error = self.profile.distance_upper_mm
        if width >= 0 and profile_error is not None:
            slope = max(abs(frame.low.slope), abs(frame.high.slope))
            longitudinal = self.cuts.excursion_upper_mm + slope * profile_error
            scale = max(Fraction(1), sum(map(abs, frame.columns[0])))
            distance = profile_error + scale * longitudinal
        checkpoint()
        object.__setattr__(self, "minimum_source_width_mm", width)
        object.__setattr__(self, "distance_upper_mm", distance)

    @property
    def status(self) -> str:
        """
        Require one inclusive combined accuracy bound without granting full-path or volume/material acceptance.
        """
        return (
            "within_native_original_flat_domain_accuracy"
            if self.distance_upper_mm is not None and self.distance_upper_mm <= Fraction(1, 100)
            else "unresolved_native_original_flat_domain_accuracy"
        )
