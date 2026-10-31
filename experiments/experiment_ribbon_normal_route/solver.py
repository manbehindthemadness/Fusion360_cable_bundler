"""
Connect fixed poses with one prescribed polynomial family and certified curvature.

This is a bounded endpoint construction, not a universal feasibility procedure.
The two guides are offsets of one perpendicular profile, never separate fits.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from devtools.ribbon_analysis.bernstein import septic_cap_controls
from devtools.ribbon_analysis.contracts import TargetPose, Targets
from devtools.ribbon_analysis.pinch import PinchLimit
from devtools.ribbon_analysis.polynomial_certificate import CurvatureCertificate, certify_curvature
from experiments.experiment_ribbon_cap_transition.edge_first import BoundaryCurve

from .compatibility import planar_controls

ZERO = Vector3(0, 0, 0)
DEFAULT_LIMIT = PinchLimit()


@dataclass(frozen=True)
class NormalRoute:
    """
    Evaluate a shared centerline and its constant perpendicular profile guides.
    """

    targets: Targets
    curve: BoundaryCurve
    constant_width: Vector3 | None

    @property
    def half_width_mm(self) -> float:
        """
        Retain the existing profile's outer side-cap extent.
        """
        return self.targets.lines * self.targets.diameter_mm / 2 + self.targets.diameter_mm * 0.1

    @property
    def preserves_material_lengths(self) -> bool:
        """
        Test equal material increments under this rigid normal-profile model.

        A regular speed/frame certificate remains a separate prerequisite.
        Nonplanarity here is a representation failure, not impossible routing.
        """
        return self.constant_width is not None or planar_controls(self.curve.points)

    def frame(self, u: float) -> tuple[Vector3, Vector3, Vector3, Vector3]:
        """
        Return position, velocity, width, and width derivative at a regular station.
        """
        position, velocity, acceleration, jerk, _ = self.curve.jet(u)
        if self.constant_width is not None:
            return position, velocity, self.constant_width, ZERO
        binormal = cross(velocity, acceleration)
        norm = magnitude(binormal)
        if norm <= 0:
            raise ValueError("The polynomial has a singular bend frame.")
        width = unit(binormal)
        rate = cross(velocity, jerk)
        width_rate = ZERO.translated(rate, 1 / norm).translated(width, -dot(width, rate) / norm)
        return position, velocity, width, width_rate

    def lane(self, u: float, offset_mm: float) -> tuple[Vector3, Vector3]:
        """
        Offset the same normal profile and differentiate its actual guide position.
        """
        position, velocity, width, width_rate = self.frame(u)
        return position.translated(width, offset_mm), velocity.translated(width_rate, offset_mm)


@dataclass(frozen=True)
class RouteResult:
    """
    Preserve every scalar probe and separate family exhaustion from impossibility.
    """

    status: str
    route: NormalRoute | None
    scale: float | None
    certificate: CurvatureCertificate | None
    probes: tuple[tuple[float, CurvatureCertificate], ...]
    reason: str


def _checked_result(
    route: NormalRoute,
    scale: float,
    certificate: CurvatureCertificate,
    probes: list[tuple[float, CurvatureCertificate]],
    reason: str,
) -> RouteResult:
    """
    Require equal material lengths separately from the retained curvature proof.
    """
    if certificate.status != "certified":
        return RouteResult("unresolved", route, scale, certificate, tuple(probes), reason)
    if not route.preserves_material_lengths:
        return RouteResult(
            "length_incompatible",
            route,
            scale,
            certificate,
            tuple(probes),
            "Curvature certified, but rotating rigid normal sections lengthen both edges. "
            "A material bank/fold representation is required; other routing remains unresolved.",
        )
    return RouteResult("certified", route, scale, certificate, tuple(probes), reason)


def _controls(targets: Targets) -> tuple[Vector3, ...]:
    """
    Prescribe cap jets using only endpoint positions and ordered frame directions.
    """
    distance = magnitude(difference(targets.end, targets.start))
    if distance <= 1e-8:
        raise ValueError("Coincident endpoints need a different construction; no fallback.")
    first = septic_cap_controls(
        targets.start,
        ZERO.translated(targets.start_tangent, distance),
        ZERO.translated(cross(targets.start_width, targets.start_tangent), distance),
        ZERO.translated(targets.start_tangent, -distance),
    )
    last = septic_cap_controls(
        targets.end,
        ZERO.translated(targets.end_tangent, -distance),
        ZERO.translated(cross(targets.end_width, targets.end_tangent), distance),
        ZERO.translated(targets.end_tangent, distance),
    )
    return first + tuple(reversed(last))


def _constant_width(targets: Targets, controls: tuple[Vector3, ...]) -> Vector3 | None:
    """
    Detect an exactly planar profile frame, including planar curvature reversals.

    Rational dot products prevent a tolerance from silently admitting lateral bend.
    Other routes use the regular Frenet binormal and must certify its existence.
    """
    if targets.start_width != targets.end_width:
        return None
    width = targets.start_width
    for point in controls:
        value = sum(
            (
                Fraction(w) * (Fraction(p) - Fraction(s))
                for w, p, s in zip(
                    (width.x, width.y, width.z),
                    (point.x, point.y, point.z),
                    (targets.start.x, targets.start.y, targets.start.z),
                )
            ),
            Fraction(0),
        )
        if value != 0:
            return None
    return width


def solve(
    source: TargetPose,
    limit: PinchLimit = DEFAULT_LIMIT,
    *,
    maximum_probes: int = 36,
    checkpoint: Callable[[], None] | None = None,
) -> RouteResult:
    """
    Bracket a certified boundary within one endpoint-anchored septic family.

    The scale multiplies cap jets around a zero-jet bridge, preserving fixed poses.
    Halving/doubling and bisection are bounded scalar continuation, with no route
    bank, random initialization, or retired discovery call. Monotonic feasibility,
    global minimum length, and existence outside this family are not established.
    """
    if (
        isinstance(maximum_probes, bool)
        or not isinstance(maximum_probes, int)
        or maximum_probes < 2
    ):
        raise ValueError("At least two finite scalar probes are required.")
    targets = Targets.capture(source)
    controls = _controls(targets)
    chord = unit(difference(targets.end, targets.start))
    straight = (
        magnitude(difference(chord, targets.start_tangent)) < 1e-12
        and targets.start_tangent == targets.end_tangent
        and targets.start_width == targets.end_width
    )
    if straight:
        controls = tuple(
            targets.start.translated(difference(targets.end, targets.start), i / 7)
            for i in range(8)
        )
    bridge = (targets.start,) * 4 + (targets.end,) * 4
    maximum = Fraction(str(limit.percent)) / 100 / (Fraction(str(targets.diameter_mm)) / 2)
    probes: list[tuple[float, CurvatureCertificate]] = []

    def probe(trial_scale: float) -> tuple[NormalRoute, CurvatureCertificate]:
        """
        Record one geometric continuation step and its entire-interval certificate.
        """
        if checkpoint is not None:
            checkpoint()
        points = tuple(
            b.translated(difference(p, b), trial_scale) for p, b in zip(controls, bridge)
        )
        width = _constant_width(targets, points)
        trial_route = NormalRoute(targets, BoundaryCurve(points), width)
        trial_certificate = certify_curvature(
            points, maximum, require_frame=width is None, checkpoint=checkpoint
        )
        probes.append((trial_scale, trial_certificate))
        return trial_route, trial_certificate

    scale = 1.0
    route, certificate = probe(scale)
    if straight:
        return _checked_result(
            route,
            scale,
            certificate,
            probes,
            "Straight endpoint control; no added loop.",
        )
    while certificate.status != "certified" and len(probes) < min(9, maximum_probes):
        scale *= 2
        route, certificate = probe(scale)
    if certificate.status != "certified":
        return RouteResult(
            "unresolved",
            route,
            scale,
            certificate,
            tuple(probes),
            "No certified member in bounded continuation; not an impossibility claim.",
        )
    best, passing, high = route, certificate, scale
    low = scale / 2
    while len(probes) < maximum_probes:
        route, certificate = probe(low)
        if certificate.status != "certified":
            break
        best, passing, high = route, certificate, low
        low /= 2
    else:
        return _checked_result(
            best,
            high,
            passing,
            probes,
            "Certified member retained; contraction budget exhausted.",
        )
    while len(probes) < maximum_probes and high - low > 1e-7 * max(1, high):
        middle = (low + high) / 2
        route, certificate = probe(middle)
        if certificate.status == "certified":
            best, passing, high = route, certificate, middle
        else:
            low = middle
    return _checked_result(
        best,
        high,
        passing,
        probes,
        "Retained certified family boundary; no global optimality or physical certification.",
    )
