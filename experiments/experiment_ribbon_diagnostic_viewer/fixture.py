"""
Define a compound S-bend whose heading turns ninety degrees along the whole path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.inspection.geometry import LocalFrame, local_frame
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase


@dataclass(frozen=True)
class Tightness:
    """
    Declare the retained single-conductor bend scalar separately from utilization.

    This is the existing 3D experiment rule for one circular conductor. It does
    not resolve the disputed wide-ribbon centre/edge ratio or clearance flex rule.
    """

    diameter_mm: float = 1.5
    radius_diameters: float = 3.0
    utilization: float = 1.0

    def __post_init__(self) -> None:
        """
        Require physical dimensions and utilization within the declared bend limit.
        """
        if (
            any(
                isinstance(v, bool) or not math.isfinite(v) or v <= 0
                for v in (self.diameter_mm, self.radius_diameters, self.utilization)
            )
            or self.utilization > 1
        ):
            raise ValueError("Tightness needs positive dimensions and utilization within (0,1].")

    @property
    def minimum_radius_mm(self) -> float:
        """
        Return the declared minimum centre radius for this circular cable.
        """
        return self.diameter_mm * self.radius_diameters


@dataclass(frozen=True)
class SpatialSBend:
    """
    Freeze a forward-authored reference, with exact tangent and analytic bend bound.

    Pitch is pi/4*sin(pi*u), so its signed vertical turning reverses at the
    midpoint. Yaw is pi*u/2 over the same path, rather than a separate elbow.
    Position uses fixed 512-interval Simpson quadrature. Target poses derive from
    this reference before solving; it is one development case, not a holdout.
    """

    tightness: Tightness = Tightness()
    _positions: tuple[Vector3, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """
        Integrate fixed geometry independently of solver success or coefficient fitting.
        """
        positions = [Vector3(0, 0, 0)]
        for i in range(512):
            positions.append(self._advance(positions[-1], i / 512, (i + 1) / 512))
        object.__setattr__(self, "_positions", tuple(positions))

    @property
    def length_mm(self) -> float:
        """
        Scale arc length so the analytic peak curvature attains the requested utilization.
        """
        peak_turn = math.hypot(math.pi**2 / 4, math.pi / 2)
        return peak_turn * self.tightness.minimum_radius_mm / self.tightness.utilization

    @staticmethod
    def tangent(u: float) -> Vector3:
        """
        Return the exact unit tangent, starting at +Z and ending at +X.
        """
        if not math.isfinite(u) or not 0 <= u <= 1:
            raise ValueError("Fixture fraction must lie within [0,1].")
        pitch, yaw = math.pi / 4 * math.sin(math.pi * u), math.pi / 2 * u
        return Vector3(
            math.cos(pitch) * math.sin(yaw), math.sin(pitch), math.cos(pitch) * math.cos(yaw)
        )

    def curvature(self, u: float) -> float:
        """
        Measure exact curvature; both squared terms attain their maximum at the ends.
        """
        self.tangent(u)
        pitch = math.pi / 4 * math.sin(math.pi * u)
        return (
            math.hypot(math.pi**2 / 4 * math.cos(math.pi * u), math.pi / 2 * math.cos(pitch))
            / self.length_mm
        )

    def _advance(self, origin: Vector3, a: float, b: float) -> Vector3:
        """
        Apply fixed Simpson quadrature to an arc-length-scaled analytic tangent.
        """
        scale = self.length_mm * (b - a) / 6
        return (
            origin.translated(self.tangent(a), scale)
            .translated(self.tangent((a + b) / 2), 4 * scale)
            .translated(self.tangent(b), scale)
        )

    def jet(self, u: float) -> tuple[Vector3, Vector3]:
        """
        Return quadrature position and analytic normalized-parameter derivative.
        """
        tangent = self.tangent(u)
        index = min(511, int(u * 512))
        position = self._advance(self._positions[index], index / 512, u)
        return position, Vector3(0, 0, 0).translated(tangent, self.length_mm)

    def frame(self, u: float) -> LocalFrame:
        """
        Choose a smooth horizontal across axis; a circle has no material wide axis.
        """
        yaw = math.pi / 2 * u
        return local_frame(
            self.jet(u)[0], self.tangent(u), Vector3(math.cos(yaw), 0, -math.sin(yaw))
        )

    def targets(self) -> EndpointCase:
        """
        Freeze both prescribed end poses before any routing algorithm runs.
        """
        start, end = self.frame(0), self.frame(1)
        return EndpointCase(
            "S001 single conductor spatial S / lateral 90",
            start.origin,
            end.origin,
            start.z,
            end.z,
            start.x,
            end.x,
            1,
            self.tightness.diameter_mm,
        )
