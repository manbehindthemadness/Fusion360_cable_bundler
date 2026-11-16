"""
Intersect original flat cut constraints with the unchanged profile and bound witnesses on that actual source domain.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction

from .flat_cut_domain import FlatCutDomain, FlatCutFrame
from .native_profile_accuracy import NativeProfileAccuracy
from .profile_conic import EllipseArc
from .profile_continuity import ProfileContinuity


@dataclass(frozen=True)
class ClippedProfileDomain:
    """
    Retain exactly those original profile q values where the original longitudinal cut interval is nonempty.

    An affine width has at most one crossing. Its exact interval intersection
    does not alter the conic, control points, original cut equations or targets.
    Empty or point-only domains require another construction and stay unsupported.
    The retained q shift bounds later proof witnesses; it is not a coordinate repair.
    """

    continuity: ProfileContinuity
    frame: FlatCutFrame
    checkpoint: InitVar[Callable[[], None]]
    interval: tuple[Fraction, Fraction] = field(init=False)
    minimum_source_width_mm: Fraction = field(init=False)
    witness_q_shift_mm: Fraction = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Intersect the original q graph with the exact signed affine width inequality once.
        """
        checkpoint()
        original_low, original_high = self.continuity.interval
        low, high = original_low, original_high
        offset = self.frame.high.offset - self.frame.low.offset
        slope = self.frame.high.slope - self.frame.low.slope
        if slope > 0:
            low = max(low, -offset / slope)
        elif slope < 0:
            high = min(high, -offset / slope)
        elif offset < 0:
            raise ValueError("A nonempty original clipped profile domain required")
        if low >= high:
            raise ValueError("A nonempty original clipped profile domain required")
        width = min(offset + slope * q for q in (low, high))
        if max(offset + slope * q for q in (low, high)) <= 0:
            raise ValueError("A positive-area original clipped profile domain required")
        assert width >= 0
        object.__setattr__(self, "interval", (low, high))
        object.__setattr__(self, "minimum_source_width_mm", width)
        object.__setattr__(
            self, "witness_q_shift_mm", max(low - original_low, original_high - high)
        )
        checkpoint()

    @property
    def conic(self) -> EllipseArc:
        """
        Expose the same original source ellipse without fitting new clipped control points.
        """
        return self.continuity.conic


@dataclass(frozen=True)
class ClippedNativeFlatDomainAccuracy:
    """
    Bound native-to-original-domain distance after accounting for the exact cut/profile intersection.

    The original full-arc witness costs D. Moving its q into the intersection
    costs at most the retained q shift plus ProfileContinuity's b variation,
    in both material and world coordinates. Original cut excursions plus the
    cut slopes times D and that q shift then bound the required s witness.
    Every term shares one allowance; no actual source/native coordinate moves.
    """

    profile: NativeProfileAccuracy
    cuts: FlatCutDomain
    clipped: ClippedProfileDomain
    checkpoint: InitVar[Callable[[], None]]
    distance_upper_mm: Fraction | None = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Require identical source/native owners and derive the complete joint witness bound without rounding away a cut.
        """
        checkpoint()
        frame = self.clipped.frame
        if (
            self.profile.frame is not frame
            or self.cuts.frame is not frame
            or self.profile.conic is not self.clipped.conic
            or any(box.native is not self.cuts.low_box.native for box in self.profile.boxes)
        ):
            raise ValueError(
                "The SAME original clipped source and native forward-domain owners required"
            )
        error = self.profile.distance_upper_mm
        distance = None
        if error is not None:
            q_shift = self.clipped.witness_q_shift_mm
            b_shift = self.clipped.continuity.variation(q_shift)
            scales = tuple(sum(map(abs, column)) for column in frame.columns)
            profile_shift = max(q_shift + b_shift, scales[1] * q_shift + scales[2] * b_shift)
            slope = max(abs(frame.low.slope), abs(frame.high.slope))
            longitudinal = self.cuts.excursion_upper_mm + slope * (error + q_shift)
            distance = error + profile_shift + max(Fraction(1), scales[0]) * longitudinal
        object.__setattr__(self, "distance_upper_mm", distance)
        checkpoint()

    @property
    def status(self) -> str:
        """
        Require one inclusive joint material/world witness allowance without granting filled coverage or physical acceptance.
        """
        return (
            "within_native_original_flat_domain_accuracy"
            if self.distance_upper_mm is not None and self.distance_upper_mm <= Fraction(1, 100)
            else "unresolved_native_original_flat_domain_accuracy"
        )
