"""
Author ordered lanes from shared planar sections, without individual lane repair.

This deterministic host-only strategy omits length equalization. Its explicit
interpolant is not Fusion's loft, and its continuous curvature/clearance remain
uncertified. It preserves input route nodes, not the continuous input centerline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, difference, dot, lerp, magnitude, unit
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame, ribbon_lane_points
from experiments.experiment_secure_discrete_ribbon.shape import (
    RibbonEndFit,
    RibbonShape,
    _maximum_pitch_ratio,
    _minimum_end_radius,
    ribbon_line_lengths,
)

from .solver import candidate_frames


@dataclass(frozen=True)
class SectionField:
    """
    Define C2 origin/width fields through an immutable banked node scaffold.

    Origin derivatives are node tangents with unit speed in chord-distance
    coordinates; second derivatives vanish at nodes. Unit width uses quintic
    easing with zero first/second derivatives at nodes. Thus every lane shares
    the exact cap tangent. Stop if interpolated width degenerates; no fallback.
    Width easing at every node is a deliberate first-candidate limitation.
    """

    frames: tuple[RibbonFrame, ...]
    diameter_mm: float
    lines: int

    def __post_init__(self) -> None:
        """
        Require finite, nondegenerate unit-width sections with usable spans.
        """
        if len(self.frames) < 2 or self.lines < 1:
            raise ValueError("Section fields require two nodes and positive conductor count.")
        if not math.isfinite(self.diameter_mm) or self.diameter_mm <= 0:
            raise ValueError("Section fields require a positive finite diameter.")
        for frame in self.frames:
            vectors = (frame.origin, frame.width, frame.tangent, frame.thickness)
            if any(not all(math.isfinite(v) for v in (p.x, p.y, p.z)) for p in vectors):
                raise ValueError("Section fields require finite frame vectors.")
            if abs(magnitude(frame.width) - 1) > 1e-8 or magnitude(frame.tangent) <= 1e-8:
                raise ValueError("Section fields require unit width and nonzero tangent.")
            if abs(dot(frame.width, unit(frame.tangent))) > 1e-8:
                raise ValueError("Node width must lie in its section plane.")
        for left, right in zip(self.frames, self.frames[1:]):
            if magnitude(difference(right.origin, left.origin)) <= 1e-8:
                raise ValueError("Section fields require positive node spans.")
            if magnitude(lerp(left.width, right.width, 0.5)) <= 1e-8:
                raise ValueError("Section width interpolation degenerates; no fallback.")

    def lane_point(self, segment: int, fraction: float, lane: int) -> Vector3:
        """
        Evaluate one lane on a nominally spaced shared section between two nodes.

        Intermediate sections are planar but need not be perpendicular to the
        interpolated centerline. All fields have matching C2 node jets.
        """
        if not 0 <= segment < len(self.frames) - 1 or not 0 <= lane < self.lines:
            raise ValueError("Section field index is outside its scaffold.")
        if not math.isfinite(fraction) or not 0 <= fraction <= 1:
            raise ValueError("Section fraction must be finite and within [0, 1].")
        left, right = self.frames[segment : segment + 2]
        span = magnitude(difference(right.origin, left.origin))
        u = fraction
        ease = 10 * u**3 - 15 * u**4 + 6 * u**5
        start_derivative = u - 6 * u**3 + 8 * u**4 - 3 * u**5
        end_derivative = -4 * u**3 + 7 * u**4 - 3 * u**5
        origin = (
            lerp(left.origin, right.origin, ease)
            .translated(unit(left.tangent), span * start_derivative)
            .translated(unit(right.tangent), span * end_derivative)
        )
        blended_width = lerp(left.width, right.width, ease)
        if magnitude(blended_width) <= 1e-8:
            raise ValueError("Section width interpolation degenerates; no fallback.")
        return origin.translated(
            unit(blended_width), (lane - (self.lines - 1) / 2) * self.diameter_mm
        )


def solve_authored_sections(
    case: RibbonStressCase, start_fit: RibbonEndFit, end_fit: RibbonEndFit
) -> RibbonShape:
    """
    Generate 32 shared sections with exact cap targets and nominal conductor pitch.

    No fold, lane blend, reroute, search or post-generation projection occurs.
    Both cap arrays must agree with scaffold ordering; reject rather than repair.
    The cap-specific origin derivative treatment occupies the first/last spans;
    their larger length is conservatively used for both end-allowance checks.
    Finite chord curvature/length metrics are not continuous-field certificates.
    """
    frames = candidate_frames(case, start_fit, end_fit)
    SectionField(frames, case.diameter_mm, case.lines)
    lanes = ribbon_lane_points(frames, case.lines, case.diameter_mm)
    for index, fit in ((0, start_fit), (-1, end_fit)):
        if len(fit.centers) != case.lines or len(fit.normals) != case.lines:
            raise ValueError("Section caps must provide every ordered conductor.")
        if any(
            magnitude(difference(lane[index], target)) > 1e-8
            for lane, target in zip(lanes, fit.centers)
        ):
            raise ValueError("Section scaffold does not match the fixed cap targets.")
    # Preserve the authoritative endpoint objects, not merely close coordinates.
    lanes = tuple(
        (start_fit.centers[i], *lane[1:-1], end_fit.centers[i]) for i, lane in enumerate(lanes)
    )
    distances = [0.0]
    for left, right in zip(frames, frames[1:]):
        distances.append(distances[-1] + magnitude(difference(right.origin, left.origin)))
    lead = max(distances[1], distances[-1] - distances[-2])
    lengths = ribbon_line_lengths(lanes)
    return RibbonShape(
        frames=frames,
        lanes=lanes,
        lengths_mm=lengths,
        spread=(max(lengths) - min(lengths)) / max(lengths),
        folded=False,
        maximum_pitch_ratio=_maximum_pitch_ratio(lanes, case.diameter_mm),
        start_fit=start_fit,
        end_fit=end_fit,
        end_lead_mm=lead,
        minimum_end_radius_mm=_minimum_end_radius(lanes, tuple(distances), lead, True, True),
    )
