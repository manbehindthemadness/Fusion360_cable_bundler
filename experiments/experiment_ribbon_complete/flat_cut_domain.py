"""
Bound original longitudinal material cuts over complete actual native faces using oriented enclosures.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction

from .cylinder_enclosure import NativeFaceBox
from .exact_frame import FrameInverse, Point, invert
from .flat_chart import FlatCoordinateProof, FlatRegion, MaterialCut, certify


class CutSide(Enum):
    """
    Identify the original lower and upper material-domain inequalities explicitly.
    """

    LOW = "low"
    HIGH = "high"


@dataclass(frozen=True)
class FlatCutFrame:
    """
    Retain exact affine cut geometry without requiring unrelated bend tensor extraction.

    Adapters establish original metadata provenance before constructing this
    port. Geometry alone does not certify a bend, transverse profile, face
    membership or material correspondence. The full-chart adapter below uses
    these same invariants and arithmetic rather than a second implementation.
    """

    region: FlatRegion
    origin: Point
    columns: tuple[Point, ...]
    low: MaterialCut
    high: MaterialCut
    inverse: FrameInverse = field(init=False)

    def __post_init__(self) -> None:
        """
        Derive an owned positive and conditioned inverse from complete exact captured coefficients.
        """
        if (
            not isinstance(self.region, FlatRegion)
            or len(self.origin) != 3
            or any(type(x) is not Fraction for x in self.origin)
            or not isinstance(self.low, MaterialCut)
            or not isinstance(self.high, MaterialCut)
        ):
            raise ValueError("Complete original affine cut geometry required")
        inverse = invert(self.columns)
        if (
            inverse.determinant <= 0
            or inverse.inverse_norm is None
            or inverse.norm * inverse.inverse_norm > 1024
        ):
            raise ValueError("Positive conditioned original affine cut frame required")
        object.__setattr__(self, "inverse", inverse)


def from_chart(frame: FlatCoordinateProof) -> FlatCutFrame:
    """
    Preserve the original full-chart qualification when adapting to endpoint-only cut geometry.
    """
    if frame != certify(frame.chart) or frame.status != "certified_affine_material_chart":
        raise ValueError("The SAME certified original flat frame required")
    chart = frame.chart
    return FlatCutFrame(chart.region, chart.origin, chart.columns, chart.low, chart.high)


def frame_direction(frame: FlatCutFrame, side: CutSide) -> Point:
    """
    Derive the exact world gradient of the original signed material gap without fitting geometry.
    """
    if not isinstance(side, CutSide):
        raise ValueError("An explicit original material cut side required")
    rows = frame.inverse.rows
    assert rows is not None
    cut = frame.low if side is CutSide.LOW else frame.high
    sign = 1 if side is CutSide.LOW else -1
    return tuple(sign * (a - cut.slope * b) for a, b in zip(rows[0], rows[1]))


def direction(frame: FlatCoordinateProof, side: CutSide) -> Point:
    """
    Retain the source-owned full-chart entry while sharing the endpoint-only gradient implementation.
    """
    return frame_direction(from_chart(frame), side)


def minimum_frame_gap(frame: FlatCutFrame, box: NativeFaceBox, side: CutSide) -> Fraction:
    """
    Bound every face point using exact affine extrema at all vertices of its enclosing box.

    Evaluated box vertices need not lie on the face. The affine functional is
    defined on the entire box; no point/box/native membership is inferred.
    """
    gradient = frame_direction(frame, side)
    if frame.region.value != box.native.region:
        raise ValueError("The SAME original flat region and native face required")
    offset = -frame.low.offset if side is CutSide.LOW else frame.high.offset
    return min(
        offset + sum((g * (p - o) for g, p, o in zip(gradient, point, frame.origin)), Fraction(0))
        for point in box.corners()
    )


def minimum_gap(frame: FlatCoordinateProof, box: NativeFaceBox, side: CutSide) -> Fraction:
    """
    Preserve full-chart cut-gap inspection through the shared affine-frame port.
    """
    return minimum_frame_gap(from_chart(frame), box, side)


@dataclass(frozen=True)
class FlatCutDomain:
    """
    Retain whole-face cut bounds without granting transverse profile or complete-trim acceptance.
    """

    frame: FlatCutFrame
    low_box: NativeFaceBox
    high_box: NativeFaceBox
    minimum_gaps_mm: tuple[Fraction, Fraction]
    excursion_upper_mm: Fraction

    def __post_init__(self) -> None:
        """
        Reject foreign native owners and stale frames, enclosures or derived bounds.
        """
        if self.low_box.native is not self.high_box.native:
            raise ValueError("The SAME actual native face required for both cuts")
        expected = (
            minimum_frame_gap(self.frame, self.low_box, CutSide.LOW),
            minimum_frame_gap(self.frame, self.high_box, CutSide.HIGH),
        )
        excursion = sum((max(Fraction(0), -gap) for gap in expected), Fraction(0))
        if self.minimum_gaps_mm != expected or self.excursion_upper_mm != excursion:
            raise ValueError("The SAME owned material cuts and derived enclosure bounds required")

    @property
    def status(self) -> str:
        """
        Apply one combined inclusive dimensional allowance across both end inequalities.
        """
        return (
            "within_native_flat_longitudinal_domain"
            if self.excursion_upper_mm <= Fraction(1, 100)
            else "unresolved_native_flat_longitudinal_domain"
        )


def certify_frame_domain(
    frame: FlatCutFrame,
    low_box: NativeFaceBox,
    high_box: NativeFaceBox,
    checkpoint: Callable[[], None],
) -> FlatCutDomain:
    """
    Check complete native-face longitudinal bounds using original metadata-only affine geometry.
    """
    checkpoint()
    gaps = (
        minimum_frame_gap(frame, low_box, CutSide.LOW),
        minimum_frame_gap(frame, high_box, CutSide.HIGH),
    )
    excursion = sum((max(Fraction(0), -gap) for gap in gaps), Fraction(0))
    checkpoint()
    return FlatCutDomain(frame, low_box, high_box, gaps, excursion)


def certify_domain(
    frame: FlatCoordinateProof,
    low_box: NativeFaceBox,
    high_box: NativeFaceBox,
    checkpoint: Callable[[], None],
) -> FlatCutDomain:
    """
    Preserve the qualified full-chart entry while sharing exact endpoint-only cut-domain arithmetic.
    """
    checkpoint()
    return certify_frame_domain(from_chart(frame), low_box, high_box, checkpoint)
