"""
Draw a continuous boundary and only those companion paths permitted by its gates.
"""

from __future__ import annotations

from typing import Any, Callable

# noinspection PyUnresolvedReferences
import adsk.core

from cable_bundler.routing.geometry import Vector3

from . import coupled_native, event_display
from .edge_first import BoundaryCurve, EdgeCandidate, frame
from .edge_interpolation import cubic_controls
from .endpoint_first import evaluate
from .material_display import curves
from .trace_sweep_native import _point


def _curve(
    component: Any, name: str, jet: Callable[[float], tuple[Vector3, Vector3]], intervals: int
) -> None:
    """
    Approximate one full path by a bounded number of cubic Hermite intervals.

    Exact endpoint positions/derivatives are retained;interior cubic compliance
    remains unmeasured. Failure raises rather than substituting a different path.
    """
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketch.name = name + " - cubic display approximation"
    points, knots = cubic_controls(jet, intervals)
    native_points = [sketch.modelToSketchSpace(_point(p)) for p in points]
    native = adsk.core.NurbsCurve3D.createNonRational(native_points, 3, list(knots), False)
    if native is None or sketch.sketchCurves.sketchFixedSplines.addByNurbsCurve(native) is None:
        raise RuntimeError("Edge-first native curve construction failed.")
    sketch.isLightBulbOn = True


# noinspection PyProtectedMember
def draw(component: Any, candidate: EdgeCandidate, number: int, *, intervals: int = 64) -> None:
    """
    Show target guides and arrival edge,with companions only after compatibility.
    The default64interval display remains historical;higher resolutions require
    native interpolation checks. Retained analytic controls keep their old display.
    """
    case = candidate.case
    coupled_native._guides(component, case)
    if candidate.retained_control is not None:
        if not candidate.companion_allowed:
            raise RuntimeError("Retained control compatibility regression.")
        curves(component, candidate.retained_control.strip)
    else:
        curve = candidate.curve
        if curve is None:
            raise RuntimeError("Candidate lacks its reference boundary.")
        boundary_curve: BoundaryCurve = curve

        def edge_jet(u: float) -> tuple[Vector3, Vector3]:
            """
            Evaluate only boundary position and velocity for its independent display.
            """
            return evaluate(boundary_curve.derivatives[0], u), evaluate(
                boundary_curve.derivatives[1], u
            )

        _curve(component, "A boundary - endpoint-first", edge_jet, intervals)
        if candidate.companion_allowed:
            half_width = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1

            def center_jet(u: float) -> tuple[Vector3, Vector3]:
                """
                Evaluate the permitted center material lane from boundary A.
                """
                return frame(boundary_curve, u).lane(-half_width)

            def opposite_jet(u: float) -> tuple[Vector3, Vector3]:
                """
                Evaluate the permitted opposite material edge without identity swaps.
                """
                return frame(boundary_curve, u).lane(-2 * half_width)

            _curve(component, "Derived center", center_jet, intervals)
            _curve(component, "Derived B boundary", opposite_jet, intervals)
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketch.name = f"{number:02d} - edge arrival and compatibility status"
    event_display._text(sketch, f"{number:02d}", case.start.x / 10 - 3, case.start.y / 10 - 5, 0.9)
    caption = "COMPANIONS ALLOWED" if candidate.companion_allowed else "A ONLY - RIBBON REJECTED"
    event_display._text(sketch, caption, case.start.x / 10 - 3, case.start.y / 10 - 7, 0.35)
    sketch.isLightBulbOn = True
