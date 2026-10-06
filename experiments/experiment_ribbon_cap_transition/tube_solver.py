"""
Generate one shared master-tube ribbon without conductor-length equalization.

No Fusion or production changes occur. Fixed input curves retain the original
continuous enclosing-radius certificate; final lanes and native loft remain
subject to separate diagnostic checks, not assumed compliant from that tube.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import difference, dot, magnitude, unit
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.contract import (
    certify_curvature,
    discrete_profile_reach,
)
from experiments.experiment_secure_discrete_ribbon.frames import ribbon_lane_points
from experiments.experiment_secure_discrete_ribbon.shape import (
    RibbonEndFit,
    RibbonShape,
    _maximum_pitch_ratio,
    _minimum_end_radius,
    ribbon_line_lengths,
)

from .ends import cap_direction
from .full_turn import FullTurnDiagnostic
from .master_frames import master_scaffold
from .prescribed_twist import PrescribedTwistDiagnostic


def solve_tube_ribbon(
    case: RibbonStressCase,
    start_fit: RibbonEndFit,
    end_fit: RibbonEndFit,
    *,
    twist: FullTurnDiagnostic | PrescribedTwistDiagnostic | None = None,
) -> RibbonShape:
    """
    Certify the master curve, author one bounded bank field and measure lane chords.

    One fixed table/pass, zero fold searches or independent lane repairs. Cap
    positions, plane normals, lobe directions and conductor ordering must match
    the fixed guides. First/last spans conservatively count as end treatment,
    except exact rigid translated lanes that need no authored end correction.
    Eased roll has zero endpoint derivative relative to ideal parallel transport;
    discrete transport/native flow and continuous conductor curvature are unknown.
    Endings retain the same external frozen reverse-loft plans for diagnostics.
    An explicit FullTurnDiagnostic replaces only the bounded bank decision with
    its declared winding/rate exception; default callers are unchanged.
    """
    certify_curvature(case.route, discrete_profile_reach(case.lines, case.diameter_mm))
    for fit, tangent in zip(
        (start_fit, end_fit),
        (case.route.curves[0].derivative(0), case.route.curves[-1].derivative(1)),
    ):
        if (
            fit.approach_normal is None
            or len(fit.centers) != case.lines
            or len(fit.normals) != case.lines
        ):
            raise ValueError("Master ribbon requires complete ordered caps and exact normals.")
        if any(
            not all(math.isfinite(v) for v in (p.x, p.y, p.z)) for p in (*fit.centers, *fit.normals)
        ):
            raise ValueError("Master cap centers and lobe normals must be finite.")
        if dot(cap_direction(fit.approach_normal, tangent), unit(tangent)) < 1 - 1e-7:
            raise ValueError("Master curve tangent does not match its fixed cap.")
    scaffold_inputs = (case.route, case.start_width, case.end_width, case.lines * case.diameter_mm)
    scaffold = (
        master_scaffold(*scaffold_inputs)
        if twist is None
        else master_scaffold(*scaffold_inputs, twist=twist)
    )
    frames = scaffold.frames
    lanes = ribbon_lane_points(frames, case.lines, case.diameter_mm)
    for index, fit in ((0, start_fit), (-1, end_fit)):
        if any(
            magnitude(difference(lane[index], target)) > 1e-8
            for lane, target in zip(lanes, fit.centers)
        ):
            raise ValueError("Master ribbon does not reach fixed ordered cap centers.")
        if any(
            magnitude(difference(normal, frames[index].thickness)) > 1e-8 for normal in fit.normals
        ):
            raise ValueError("Master ribbon cap lobe orientation changed.")
    lanes = tuple(
        (start_fit.centers[i], *lane[1:-1], end_fit.centers[i]) for i, lane in enumerate(lanes)
    )
    lengths = ribbon_line_lengths(lanes)
    lead = max(scaffold.distances_mm[1], scaffold.distances_mm[-1] - scaffold.distances_mm[-2])
    width = unit(case.start_width)
    translated = all(magnitude(difference(frame.width, width)) <= 1e-8 for frame in frames) and all(
        abs(dot(difference(b, a), width)) <= 1e-8
        for curve in case.route.curves
        for a, b in zip(
            (curve.start, curve.control_a, curve.control_b),
            (curve.control_a, curve.control_b, curve.end),
        )
    )
    if translated:
        # Rigid translated lanes need no authored cap correction region.
        lead = 0.0
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
        minimum_end_radius_mm=_minimum_end_radius(lanes, scaffold.distances_mm, lead, True, True),
    )
