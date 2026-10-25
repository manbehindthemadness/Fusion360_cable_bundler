"""
Prepare seven developable spans with finite-width and principal-curvature floors.

The original normal-section reference remains historical. This policy explicitly
changes interior material-section geometry while keeping terminal normal sections.
No endpoint solve, native geometry or automatic experiment is performed here.
"""

from __future__ import annotations

import math
from dataclasses import replace

from cable_bundler.routing.geometry import dot

from .banked_schedule import TurnSchedule
from .conductor_allocation import minimum_travel as previous_minimum_travel
from .coupled_motion import AngleLaw, CoupledMotion
from .endpoint_first import EndpointCase
from .material_strip import MaterialSpan, MaterialStrip, ruling_slope


def prototypes(selected: TurnSchedule) -> tuple[MaterialSpan, ...]:
    """
    Add continuous rulings to the same three-turn/four-straight ordering.

    Straight spans change ruling slope on a flat surface; turning spans retain
    the unique finite slope required by their angular axes. Zero rotations use
    zero slope. This does not introduce a different turn family or move targets.
    """
    motions = selected.motions
    if len(motions) != 7 or any(motions[index].angle != 0 for index in (0, 2, 4, 6)):
        raise ValueError("Material policy requires three turns interleaved with four straights.")
    slopes = (0.0, *(ruling_slope(m) if m.angle != 0 else 0.0 for m in motions[1::2]), 0.0)
    result = []
    for index, motion in enumerate(motions):
        if index % 2:
            slope = slopes[(index + 1) // 2]
            result.append(MaterialSpan(motion, slope, slope))
        else:
            slot = index // 2
            result.append(MaterialSpan(motion, slopes[slot], slopes[slot + 1]))
    return tuple(result)


def minimum_travel(case: EndpointCase, spans: tuple[MaterialSpan, ...]) -> tuple[float, ...]:
    """
    Retain prior floors and add finite-width regularity and surface curvature.

    Principal curvature is peak angle rate/(L*|axis dot width|), which grows
    without bound for fixed travel as bending vanishes relative to twist. The
    same0.8 enclosing-reach budget is applied conservatively to that curvature.
    Flat transitions require L>half_width*|delta_eta|. A relative1e-12 guard
    makes both floors conservative; no material strain tolerance is invented.
    """
    half_width = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    reach = math.hypot(half_width, case.diameter_mm / 2)
    previous = previous_minimum_travel(case, tuple(span.motion for span in spans))
    result = []
    for span, old in zip(spans, previous):
        motion = span.motion
        if motion.angle == 0:
            extra = half_width * abs(span.end_slope - span.start_slope)
        else:
            peak = abs(motion.angle) * (1.875 if motion.law is AngleLaw.EASED else 1)
            extra = peak / abs(dot(motion.axis, motion.width)) * reach / 0.8
        result.append(max(old, extra * (1 + 1e-12)))
    return tuple(result)


def place(
    case: EndpointCase, spans: tuple[MaterialSpan, ...], lengths: tuple[float, ...]
) -> MaterialStrip:
    """
    Position one explicitly supplied forward allocation and validate its rulings.

    Zero-length flat spans with unchanged rulings may be omitted. The resulting
    end position is authoritative even when it misses the fixed external target.
    Allocation and classification belong to a separate bounded solver.
    """
    if len(spans) != len(lengths):
        raise ValueError("Every material span requires a paired travel length.")
    result, start = [], case.start
    for span, length in zip(spans, lengths):
        if not math.isfinite(length) or length < 0:
            raise ValueError("Material travel must be finite and nonnegative.")
        if length == 0:
            if span.motion.angle != 0 or span.start_slope != span.end_slope:
                raise ValueError("A turning or changing ruling span needs positive travel.")
            continue
        motion: CoupledMotion = replace(span.motion, start=start, length=length)
        result.append(MaterialSpan(motion, span.start_slope, span.end_slope))
        start = motion.jet(1)[0]
    half_width = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    return MaterialStrip(tuple(result), half_width)
