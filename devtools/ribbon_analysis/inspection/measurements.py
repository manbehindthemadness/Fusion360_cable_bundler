"""
Expose scoped geometry measurements without reviving withdrawn physical acceptance.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import cross, difference, dot, magnitude, unit

from ..contracts import TargetPose, Targets
from .archive import RuleObservation
from .geometry import PathSnapshot


def observations(
    snapshot: PathSnapshot, targets: TargetPose, minimum_radius_mm: float
) -> tuple[RuleObservation, ...]:
    """
    Sample frozen cubics and keep missing continuous/native rules explicitly visible.

    Radius utilization is sampled at four fractions of each cubic, including both
    sides of joins. This measures the displayed interpolation, not a continuum
    certificate, a calibrated wide-ribbon rule or an overall physical decision.
    """
    if not math.isfinite(minimum_radius_mm) or minimum_radius_mm <= 0:
        raise ValueError("Declare a positive finite radius for diagnostic measurements.")
    targets = Targets.capture(targets)
    center = next(g for g in snapshot.guides if g.number == 0)
    peak = 0.0
    reach = math.hypot(
        targets.lines * targets.diameter_mm / 2 + targets.diameter_mm * 0.1, targets.diameter_mm / 2
    )
    for curve in center.curves:
        for u in (0.0, 1 / 3, 2 / 3, 1.0):
            velocity = curve.derivative(u)
            speed = magnitude(velocity)
            if speed < 1e-12:
                raise ValueError("Frozen path contains a stationary sampled centre tangent.")
            curvature = magnitude(cross(velocity, curve.second_derivative(u))) / speed**3
            peak = max(peak, curvature * minimum_radius_mm)
    gap = max(
        magnitude(difference(center.controls[0], targets.start)),
        magnitude(difference(center.controls[-1], targets.end)),
    )
    angle = max(
        math.degrees(math.acos(max(-1.0, min(1.0, dot(unit(curve.derivative(u)), tangent)))))
        for curve, u, tangent in (
            (center.curves[0], 0, targets.start_tangent),
            (center.curves[-1], 1, targets.end_tangent),
        )
    )
    circle = snapshot.lines == 1
    guide_peak = 0.0
    for guide in snapshot.guides:
        for curve in guide.curves:
            for u in (0.0, 1 / 3, 2 / 3, 1.0):
                velocity = curve.derivative(u)
                speed = magnitude(velocity)
                if speed < 1e-12:
                    raise ValueError("Frozen guide contains a stationary sampled tangent.")
                curvature = magnitude(cross(velocity, curve.second_derivative(u))) / speed**3
                guide_peak = max(guide_peak, curvature * 3.1 * targets.diameter_mm)
    width_angle = math.degrees(
        math.acos(max(-1.0, min(1.0, dot(snapshot.sections[-1].frame.x, targets.end_width))))
    )
    return (
        RuleObservation(
            "Cross-section and thickness",
            "measured",
            f"{snapshot.lines} conductor(s), D={snapshot.diameter_mm:g}mm. "
            + (
                "One circular cable profile; no separate conductor bodies."
                if circle
                else "Open material rulings only; bonded full-thickness contour is not supplied."
            ),
            snapshot.diameter_mm,
        ),
        RuleObservation(
            "Displayed centre bend / declared tightness",
            "failed" if peak > 1 else "measured",
            f"Sampled cubic curvature × declared minimum radius {minimum_radius_mm:g}mm; no interpolation repair. Analytic reference and native curvature are separate measurements.",
            peak,
            1.0,
        ),
        RuleObservation(
            "Fixed endpoint position",
            "failed" if gap > targets.diameter_mm / 2 else "measured",
            "Largest start/end centre gap in mm; targets stay fixed.",
            gap,
            targets.diameter_mm / 2,
        ),
        RuleObservation(
            "Fixed endpoint tangent",
            "measured",
            "Largest endpoint tangent deviation in degrees; no new angular allowance.",
            angle,
        ),
        RuleObservation(
            "Terminal width frame",
            "measured",
            "Actual terminal projected width deviation in degrees; the prescribed target remains fixed.",
            width_angle,
        ),
        RuleObservation(
            "Legacy centre reach cap",
            "failed" if peak * reach / minimum_radius_mm / 0.78 > 1 else "legacy",
            "Sampled centre curvature times the compatible chart's declared padded reach /0.78. Historical conservative search rule, not the unresolved physical radius-ratio policy.",
            peak * reach / minimum_radius_mm / 0.78,
            1.0,
        ),
        RuleObservation(
            "Material-guide bend cap",
            "failed" if guide_peak > 1 else "legacy",
            "Sampled frozen centre/edge curvature times3.1D, matching the compatible chart's historical lane search limit. Independent of whether that search constraint was disabled.",
            guide_peak,
            1.0,
        ),
        RuleObservation(
            "Local XYZ",
            "measured",
            "Right-handed orthonormal frames. X across, Y thickness, +Z actual positive path derivative.",
        ),
        RuleObservation(
            "Macaroni ratio and flex",
            "not_applicable" if circle else "unmeasured",
            "Wide-ribbon centre/edge radius ratio, scalar and clearance flex remain unresolved; no inherited green acceptance.",
        ),
        RuleObservation(
            "No wide-axis bending",
            "not_applicable" if circle else "unmeasured",
            "A circular single conductor has no distinguished material wide axis."
            if circle
            else "Stored frames alone do not certify the banking invariant or native interpolation.",
        ),
        RuleObservation(
            "Material map / J",
            "not_applicable" if circle else "legacy",
            "Circular reference does not invent eta or J."
            if circle
            else "Inherited material-map constraints need independent physical review.",
        ),
        RuleObservation(
            "Full-thickness self-collision",
            "unmeasured",
            "Sampled material rulings previously missed collisions. No continuous solid collision certificate is implemented.",
        ),
        RuleObservation(
            "Spacing and conductor order",
            "not_applicable" if circle else "unmeasured",
            "One conductor."
            if circle
            else "Guide order is stored; full-thickness spacing is not certified.",
        ),
        RuleObservation(
            "Signed twist",
            "not_applicable" if circle else "unmeasured",
            "Circular cross-section has no material roll target."
            if circle
            else "No 180-degree roll limiter; native twist is unmeasured.",
        ),
        RuleObservation(
            "Length balance goal",
            "not_applicable" if circle else "unmeasured",
            "One conductor has no inter-conductor length spread."
            if circle
            else "The 1% comparison is a mechanical goal, not acceptance.",
        ),
        RuleObservation(
            "Extra-loop necessity",
            "unmeasured",
            "Requires valid alternative routes with fixed targets and constraints; failed shortening is not proof.",
        ),
        RuleObservation(
            "Sphere occupancy stress test",
            "unmeasured",
            "Separate stress measurement; no sphere feeds this inspection or changes a route.",
        ),
        RuleObservation(
            "Native construction / audit",
            "unmeasured",
            "0 native solid attempts. Diagnostic curves and section envelopes are not a physical audit.",
        ),
    )
