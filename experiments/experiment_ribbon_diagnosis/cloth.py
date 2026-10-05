"""
Measure paired native longitudinal seam rails of the compact planar fixture.
"""

from __future__ import annotations

import math

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.contract import discrete_profile_reach


def side_lengths(body: adsk.fusion.BRepBody, case: RibbonStressCase) -> dict[str, object]:
    """
    Require one continuous native rail per side and thickness band before comparison.

    This is restricted to the new constant-Y planar fixtures. It measures the
    four longitudinal seams at the side/lobe joins, not sampled lane lengths
    or a full inextensible-surface certificate. Ambiguous topology cannot pass.
    """
    half_width = case.lines * case.diameter_mm / 2
    radius = discrete_profile_reach(case.lines, case.diameter_mm) / 0.8 * 1.001
    rails: dict[tuple[int, int], list[float]] = {(s, b): [] for s in (-1, 1) for b in (-1, 1)}
    expected_angle = math.radians(int(case.family.rsplit("_", 1)[1]))
    for edge in body.edges:
        evaluator = edge.evaluator
        ok, start, end = evaluator.getParameterExtents()
        if not ok or not all(math.isfinite(value) for value in (start, end)):
            raise RuntimeError("Could not measure native edge parameter range.")
        lower, upper = min(start, end), max(start, end)
        points = []
        for index in range(9):
            fraction = index / 8
            parameter = (
                start
                if index == 0
                else end
                if index == 8
                else min(upper, max(lower, (1 - fraction) * start + fraction * end))
            )
            ok, point = evaluator.getPointAtParameter(parameter)
            if not ok:
                raise RuntimeError("Could not inspect native rail geometry.")
            points.append(point)
        for side in (-1, 1):
            if not all(abs(point.y * 10 - side * half_width) <= 1e-5 for point in points):
                continue
            angles = [math.atan2(point.x * 10, radius - point.z * 10) for point in points]
            if abs(abs(angles[-1] - angles[0]) - expected_angle) > 1e-3:
                continue
            middle = points[4]
            band = 1 if math.hypot(middle.x * 10, middle.z * 10 - radius) > radius else -1
            rails[side, band].append(edge.length * 10)
    if any(len(lengths) != 1 for lengths in rails.values()):
        return {
            "status": "unmeasured",
            "rail_counts": {str(key): len(value) for key, value in rails.items()},
        }
    spreads = tuple(
        abs(rails[-1, band][0] - rails[1, band][0]) / max(rails[-1, band][0], rails[1, band][0])
        for band in (-1, 1)
    )
    return {
        "status": "passed" if max(spreads) <= 0.01 else "failed",
        "limit": 0.01,
        "maximum_relative_spread": max(spreads),
        "rail_lengths_mm": {str(key): value[0] for key, value in rails.items()},
        "scope": "Native paired side/lobe seam rails; not a full cloth-metric certificate.",
    }
