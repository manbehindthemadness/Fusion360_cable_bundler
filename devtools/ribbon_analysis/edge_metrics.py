"""
Measure the proposed width-based macaroni proxy at both material boundaries.

This opt-in diagnostic does not revise inherited acceptance rules. In the regular
director model k_edge=k/J;nonpositive/tinyJmakes that formula unavailable.
"""

from __future__ import annotations

import math
from typing import Callable

from .contracts import RibbonPath
from .provenance import mark_loaded
from .regions import Sample, Series


def boundary_macaroni(
    path: RibbonPath, checkpoint: Callable[[], None] = lambda: None, *, intervals: int = 512
) -> tuple[Series, Series]:
    """
    Return frozen A/Bseries using original center-profile reach and proposed.8limit.

    Uses16..1024bounded intervals. Missing curvature atJ<=1e-9never becomes a
    pass;inspect materialJseparately. This is intrinsic-model curvature,not native
    spline curvature,an edge-anchored envelope proof or a calibrated physical law.
    The caller may append these series/regions before api.freeze for shared views.
    """
    if isinstance(intervals, bool) or not isinstance(intervals, int) or not 16 <= intervals <= 1024:
        raise ValueError("Use16..1024bounded boundary intervals.")
    half = path.field.half_width_mm
    reach = math.hypot(half, path.field.diameter_mm / 2)
    if not math.isfinite(reach) or half <= 0 or path.field.diameter_mm <= 0:
        raise ValueError("Boundary dimensions must be finite and positive.")
    output = []
    for number, q in ((-1, half), (-2, -half)):
        samples = []
        for i in range(intervals + 1):
            if i % 32 == 0:
                checkpoint()
            u = i / intervals
            k, _, gradient = path.field.sample(u)
            point, _ = path.lane(u, q)
            if not all(math.isfinite(v) for v in (k, gradient, point.x, point.y, point.z)):
                raise ValueError("Boundary measurements must be finite.")
            jacobian = 1 + q * gradient
            if not math.isfinite(jacobian):
                raise ValueError("Boundary Jacobian overflowed.")
            value = abs(k) * reach / jacobian if jacobian > 1e-9 else None
            if value is not None and not math.isfinite(value):
                raise ValueError("Boundary curvature overflowed.")
            samples.append(Sample(u, point, value))
        output.append(
            Series("proposed edge macaroni", number, q, 0.8, "upper", 0.08, tuple(samples))
        )
    return output[0], output[1]


mark_loaded(__file__)
