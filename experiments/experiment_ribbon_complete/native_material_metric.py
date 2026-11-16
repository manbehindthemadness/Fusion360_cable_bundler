"""
Bound corresponding native/canonical longitudinal increments without cancellation or sample inference.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3216.basis import Basis

from .contact_junction_binding import RegionKey
from .native_material_chart import NativeMaterialChart
from .volume_boundary import RationalBoundaryResidual


def increment_upper(
    residual: RationalBoundaryResidual, basis: Basis, checkpoint: Callable[[], None]
) -> Fraction:
    """
    Bound integral abs(speed_native-speed_canonical), uniformly over the original profile parameter.

    For fixed V both curves share the clamped quintic U basis. Their control
    differences E_i=D_i/W² satisfy integral||E'|| <=sum||E_(i+1)-E_i||: the
    derivative's degree/knot factor cancels the integral of its nonnegative
    degree-four basis. Bounding each rational V difference by its Bernstein
    coefficients therefore covers the entire U interval and every subinterval.
    Reparameterizing U monotonically into physical material distance preserves
    the integral. No sampled derivative, endpoint cancellation or per-station
    accuracy allowance appears in this bound.
    """
    checkpoint()
    if len(residual.numerators) != basis.count:
        raise ValueError("The SAME complete global U control sequence and clamped basis required")
    total = Fraction(0)
    for first, second in zip(residual.numerators, residual.numerators[1:]):
        checkpoint()
        total += max(
            sum((abs(b - a) for a, b in zip(p, q)), Fraction(0)) for p, q in zip(first, second)
        )
    return total / min(residual.denominator)


@dataclass(frozen=True)
class NativeIncrementBound:
    """
    Retain same-chart construction fidelity, not native isometry or complete-conductor acceptance.

    The bound holds for every fixed original profile V and every longitudinal
    subinterval. Other regions and both serial endings still share the single
    complete-path0.01mm allowance; this receipt grants no additional allowance.
    """

    chart: NativeMaterialChart
    upper_mm: Fraction
    status: str

    def __post_init__(self) -> None:
        """
        Keep numeric bounds and qualification consistent with an owned native chart.
        """
        if type(self.upper_mm) is not Fraction or self.upper_mm < 0:
            raise ValueError("A nonnegative exact bound required")
        expected = (
            "within_local_increment_accuracy"
            if self.upper_mm <= Fraction(1, 100)
            else "unresolved_increment_accuracy"
        )
        if (
            self.status != expected
            or self.chart.correspondence is None
            or self.chart.status != "certified_native_material_parameter_chart"
        ):
            raise ValueError(
                "A nonnegative exact bound on the SAME qualified native chart required"
            )


def enclose(chart: NativeMaterialChart, checkpoint: Callable[[], None]) -> NativeIncrementBound:
    """
    Measure only a qualified, source-owned native material chart under the caller's allocation.
    """
    checkpoint()
    if chart.status != "certified_native_material_parameter_chart" or chart.correspondence is None:
        raise ValueError(
            "A qualified SAME-source native material chart with owned residual required"
        )
    upper = increment_upper(
        chart.correspondence.residual, chart.volume.source.surface.basis, checkpoint
    )
    return NativeIncrementBound(
        chart,
        upper,
        "within_local_increment_accuracy"
        if upper <= Fraction(1, 100)
        else "unresolved_increment_accuracy",
    )


@dataclass(frozen=True)
class TrunkChartIncrementBound:
    """
    Keep measured contributions and missing declared trunk regions explicit.

    Even complete declared trunk coverage does not include endings, internal
    midplane paths, contact, global native regularity or complete solver gates.
    The adapter must establish that expected_regions is the original full trunk.
    """

    expected_regions: tuple[RegionKey, ...]
    bounds: tuple[NativeIncrementBound, ...]
    missing_regions: tuple[RegionKey, ...]
    measured_upper_mm: Fraction
    complete_trunk_upper_mm: Fraction | None
    status: str


def enclose_trunk_chain(
    expected_regions: tuple[RegionKey, ...],
    bounds: tuple[NativeIncrementBound, ...],
    profile_label: str,
    native_revision: str,
    checkpoint: Callable[[], None],
) -> TrunkChartIncrementBound:
    """
    Sum each original region once and never turn absent measurements into zero contribution.

    Constant original profile V must retain the same arc geometry, label and
    native body revision across regions. Coverage comes from frozen original
    route/native ownership; unattempted flat or bend charts remain unknown.
    """
    checkpoint()
    if (
        not isinstance(profile_label, str)
        or not profile_label.strip()
        or not isinstance(native_revision, str)
        or not native_revision.strip()
        or not expected_regions
        or len(set(expected_regions)) != len(expected_regions)
        or any(
            type(i) is not int or i < 0 or kind not in ("before", "bend", "after", "straight")
            for i, kind in expected_regions
        )
    ):
        raise ValueError("A complete explicit original trunk region sequence required")
    seen = set()
    total = Fraction(0)
    original_arc = bounds[0].chart.arc if bounds else None
    for bound in bounds:
        checkpoint()
        chart = bound.chart
        key = chart.native.piece_index, "bend"
        if (
            key not in expected_regions
            or key in seen
            or chart.native.profile_label != profile_label
            or chart.native.revision != native_revision
            or chart.arc != original_arc
        ):
            raise ValueError(
                "Each SAME-profile/native original trunk region must be measured exactly once"
            )
        seen.add(key)
        total += bound.upper_mm
    missing = tuple(key for key in expected_regions if key not in seen)
    status = (
        "unresolved_missing_trunk_regions"
        if missing
        else "within_declared_trunk_increment_accuracy"
        if total <= Fraction(1, 100)
        else "unresolved_trunk_increment_accuracy"
    )
    return TrunkChartIncrementBound(
        expected_regions, bounds, missing, total, None if missing else total, status
    )
