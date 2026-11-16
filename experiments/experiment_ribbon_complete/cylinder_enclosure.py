"""
Bound intrinsic cylinder coordinates on actual face enclosures without edge-curve correspondence.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from itertools import product

from .cylinder_coordinates import CylinderChart
from .cylinder_domain import CylinderWindowBound, certify_window, ratio_hull
from .exact_frame import Point, invert
from .native_flat_cylinder import NativeCylinderSnapshot


@dataclass(frozen=True)
class NativeFaceBox:
    """
    Own an enclosing parallelepiped returned for the SAME actual BRepFace by MeasureManager.

    The capturing adapter must retain the face/revision and all returned center,
    direction and extent fields. Half axes are returned directions times their
    corresponding half lengths; exact rational algebra never assumes that the
    captured floating direction coefficients are perfectly orthonormal.
    This is a trusted SDK face-enclosure contract, not sampled containment.
    """

    native: NativeCylinderSnapshot
    face_token: str
    center_mm: Point
    half_axes_mm: tuple[Point, ...]

    def __post_init__(self) -> None:
        """
        Require finite exact three-dimensional enclosure data and a discrete face owner.
        """
        if (
            not self.face_token
            or len(self.center_mm) != 3
            or any(type(x) is not Fraction for x in self.center_mm)
            or len(self.half_axes_mm) != 3
        ):
            raise ValueError("Complete actual face enclosure required")
        if invert(self.half_axes_mm).rows is None:
            raise ValueError("A nondegenerate actual face enclosure required")

    def corners(self) -> tuple[Point, ...]:
        """
        Return every vertex of the complete enclosing box using exact captured coefficients.
        """
        return tuple(
            tuple(
                self.center_mm[k]
                + sum(sign * axis[k] for sign, axis in zip(signs, self.half_axes_mm))
                for k in range(3)
            )
            for signs in product((-1, 1), repeat=3)
        )


@dataclass(frozen=True)
class EnclosedCylinderFace:
    """
    Retain the actual enclosure owner and its global intrinsic window, never material acceptance.
    """

    box: NativeFaceBox
    chart: CylinderChart
    radial_lower_mm: Fraction
    window: CylinderWindowBound

    def __post_init__(self) -> None:
        """
        Reject stale enclosure, chart or derived window replacements.
        """
        lower, interval = ratio_hull(self.chart, self.box.corners())
        if (
            self.box.native is not self.chart.reference.native
            or self.window.chart is not self.chart
            or lower != self.radial_lower_mm
            or max(map(abs, interval)) != self.window.maximum_abs_ratio
        ):
            raise ValueError("The SAME owned face enclosure and derived window required")


def certify_enclosure(
    box: NativeFaceBox, chart: CylinderChart, checkpoint: Callable[[], None]
) -> EnclosedCylinderFace:
    """
    Extend affine positive-branch and angular-ratio bounds from every box vertex to the whole face.

    Every box point is a convex combination of its eight vertices. Affine x
    stays positive; y/x is a positive-weight average of vertex ratios. The
    actual face is enclosed by the SDK box and lies on the SAME cylinder.
    Thus the global cylinder-window theorem applies to every actual face point,
    independent of trimming, holes, boundary conversion or native UV units.
    A loose enclosure may fail; that is unresolved evidence, not bad geometry.
    """
    checkpoint()
    if box.native is not chart.reference.native:
        raise ValueError("The SAME native cylinder face/chart enclosure required")
    lower, interval = ratio_hull(chart, box.corners())
    window = certify_window(chart, max(map(abs, interval)), checkpoint)
    checkpoint()
    return EnclosedCylinderFace(box, chart, lower, window)
