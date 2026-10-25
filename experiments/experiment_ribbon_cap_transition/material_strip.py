"""
Evaluate a finite-width, isometric reference strip with explicit material lanes.

For center arc coordinate s and width v, rulings are W+eta*T with
W'=-eta*T'. Material longitudinal coordinate is x=s+v*eta(s). Thus
R(x,v)=r(s)+v*(W(s)+eta(s)*T(s)) has R_x=T and R_v=W. This differs from
straight perpendicular width sections; interior material cross-sections can curve.
It models an unstretched midsurface, not thick conductors or elastic equilibrium.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude

from .coupled_motion import ZERO, AngleLaw, CoupledMotion


def ruling_slope(motion: CoupledMotion) -> float:
    """
    Return the finite ruling slope demanded by a turning motion's bend/twist ratio.

    With angular axis a*T+b*W, compatibility requires eta=a/b. A nonzero
    rotation with b numerically zero is excluded from this reference family.
    Straight spans have independently prescribed ruling transitions instead.
    """
    if motion.angle == 0:
        raise ValueError("Straight spans require explicit endpoint ruling slopes.")
    bend = dot(motion.axis, motion.width)
    if abs(bend) <= 1e-10:
        raise ValueError("Pure twist has no finite compatible ruling in this reference.")
    return dot(motion.axis, motion.tangent) / bend


@dataclass(frozen=True)
class MaterialSpan:
    """
    Retain a turning span at constant ruling slope or a flat ruling transition.

    Ruling changes are linear only on straight spans, where the physical surface
    stays planar. On a turn the axis enforces W'=-eta*T'. Units are millimeters.
    """

    motion: CoupledMotion
    start_slope: float
    end_slope: float

    def __post_init__(self) -> None:
        """
        Reject nonfinite rulings and twisting incompatible with the selected surface.
        """
        if not all(math.isfinite(value) for value in (self.start_slope, self.end_slope)):
            raise ValueError("Ruling slopes must be finite.")
        if self.motion.angle != 0:
            slope = ruling_slope(self.motion)
            if max(abs(self.start_slope - slope), abs(self.end_slope - slope)) > 1e-10:
                raise ValueError("Turning span does not satisfy local developability.")

    def minimum_jacobian(self, half_width_mm: float) -> float:
        """
        Bound dx/ds across the complete width, excluding ruling intersections.
        """
        return 1 - half_width_mm * abs(self.end_slope - self.start_slope) / self.motion.length

    def maximum_principal_curvature(self) -> float:
        """
        Return the exact peak nonzero surface curvature within this span family.

        Turning spans have constant eta and k_surface=k_center*(1+eta^2).
        Flat transitions have zero curvature. This bounds the reference midsurface
        only; thickness, native interpolation and cable material remain unmeasured.
        """
        return self.motion.maximum_curvature() * (1 + self.start_slope**2)


@dataclass(frozen=True)
class MaterialStrip:
    """
    Connect compatible spans and expose ordered longitudinal material lanes.

    Zero terminal slopes preserve straight terminal width guides and their exact
    poses. Positive material Jacobians provide unique lane coordinates over the
    full finite width. Local isometry does not establish global self-clearance,
    finite conductor spacing, endpoint closure or manufacturability.
    """

    spans: tuple[MaterialSpan, ...]
    half_width_mm: float

    def __post_init__(self) -> None:
        """
        Validate finite-width regularity, terminal rulings and continuous joins.
        """
        if not self.spans or not math.isfinite(self.half_width_mm) or self.half_width_mm <= 0:
            raise ValueError("A strip needs spans and finite positive half width.")
        if self.spans[0].start_slope != 0 or self.spans[-1].end_slope != 0:
            raise ValueError("Fixed normal terminal caps require zero terminal ruling slopes.")
        if any(span.minimum_jacobian(self.half_width_mm) <= 0 for span in self.spans):
            raise ValueError(
                "Finite-width rulings intersect or lose material-coordinate regularity."
            )
        for left, right in zip(self.spans, self.spans[1:]):
            tangent, width = left.motion.frame(1)
            if (
                abs(left.end_slope - right.start_slope) > 1e-10
                or magnitude(difference(left.motion.jet(1)[0], right.motion.start)) > 1e-8
                or magnitude(difference(tangent, right.motion.tangent)) > 1e-8
                or magnitude(difference(width, right.motion.width)) > 1e-8
            ):
                raise ValueError(
                    "Material strip spans do not share one continuous pose and ruling."
                )

    @property
    def length_mm(self) -> float:
        """
        Return the common analytical reference length of every material lane.
        """
        return sum(span.motion.length for span in self.spans)

    def boundaries(self, offset_mm: float) -> tuple[float, ...]:
        """
        Return lane-specific longitudinal coordinates of the span joins.
        """
        if not math.isfinite(offset_mm) or abs(offset_mm) > self.half_width_mm:
            raise ValueError("Lane offset must lie within the reference strip width.")
        result, center_distance = [0.0], 0.0
        for span in self.spans:
            center_distance += span.motion.length
            result.append(center_distance + offset_mm * span.end_slope)
        return tuple(result)

    def jet(self, distance_mm: float, offset_mm: float = 0) -> tuple[Vector3, Vector3, Vector3]:
        """
        Return position and first/second derivatives with respect to material length.

        Lane-specific shifted span boundaries make inversion algebraic, with no
        nonlinear search. Every lane has unit speed; acceleration is orthogonal
        to its local material width. Endpoint poses are those of the supplied
        motion sequence; this evaluator never moves them to close a route.
        """
        boundaries = self.boundaries(offset_mm)
        if not math.isfinite(distance_mm) or not 0 <= distance_mm <= self.length_mm:
            raise ValueError("Material distance must lie within the strip length.")
        index = min(bisect_right(boundaries, distance_mm) - 1, len(self.spans) - 1)
        span = self.spans[index]
        denominator = boundaries[index + 1] - boundaries[index]
        u = (distance_mm - boundaries[index]) / denominator
        slope = span.start_slope + u * (span.end_slope - span.start_slope)
        tangent, width = span.motion.frame(u)
        center = span.motion.jet(u)[0]
        position = center.translated(width, offset_mm).translated(tangent, offset_mm * slope)
        _, rate, _ = span.motion.angle_jet(u)
        acceleration = ZERO.translated(cross(span.motion.axis, tangent), rate / denominator)
        return position, tangent, acceleration


def normal_section_peak_extension(motion: CoupledMotion, offset_mm: float) -> float:
    """
    Measure the old perpendicular-section lane's peak local metric extension.

    Under the no-edgewise-bend rule, |T+h*W_s|=sqrt(1+h^2*|W_s|^2).
    This diagnostic is not a calibrated material strain allowance or hard cutoff.
    """
    if not math.isfinite(offset_mm):
        raise ValueError("Lane offset must be finite.")
    peak_rate = abs(motion.angle) * (1.875 if motion.law is AngleLaw.EASED else 1)
    width_rate = peak_rate * magnitude(cross(motion.axis, motion.width)) / motion.length
    return math.hypot(1, offset_mm * width_rate) - 1
