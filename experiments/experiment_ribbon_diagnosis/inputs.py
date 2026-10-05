"""
Define independent analytic cap inputs for the controlled fixture-authoring comparison.
"""

from __future__ import annotations

from cable_bundler.routing import RibbonFrame
from cable_bundler.routing.geometry import cross, dot, unit
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase


def analytic_guide_frame(case: RibbonStressCase, at_start: bool) -> RibbonFrame:
    """
    Use the exact endpoint derivative and declared lane width, never solver samples.

    Reject an inconsistent authored width rather than silently projecting it.
    """
    curve = case.route.curves[0] if at_start else case.route.curves[-1]
    parameter = 0 if at_start else 1
    tangent = unit(curve.derivative(parameter))
    width = unit(case.start_width if at_start else case.end_width)
    if abs(dot(tangent, width)) > 1e-8:
        raise ValueError("The authored guide width is not perpendicular to its exact tangent.")
    return RibbonFrame(curve.point(parameter), tangent, width, unit(cross(tangent, width)))
