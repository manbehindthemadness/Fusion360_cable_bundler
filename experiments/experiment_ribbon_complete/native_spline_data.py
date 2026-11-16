"""
Capture original native spline coefficients without assigning world or material units to parameter data.
"""

from __future__ import annotations

import math
from typing import Any


def coefficients(curve: Any, axes: tuple[str, ...]) -> dict[str, Any]:
    """
    Preserve iterable SDK control arrays and all original coefficients under explicit coordinate axes.

    The caller supplies the documented point dimensions. This parser checks
    finite coefficients and basic data shape, but preserves negative weights
    and does not infer positive-basis, trimming or parameter correspondence.
    """
    success, points, degree, knots, rational, weights, periodic = curve.getData()
    if not success:
        raise ValueError("Native NURBS extraction failed")
    controls = [[float(getattr(point, axis)) for axis in axes] for point in points]
    native_knots = [float(k) for k in knots]
    native_weights = [float(w) for w in weights]
    if (
        not axes
        or type(degree) is not int
        or degree < 1
        or len(controls) <= degree
        or type(rational) is not bool
        or type(periodic) is not bool
        or not native_knots
        or (rational and len(native_weights) != len(controls))
        or (not rational and len(native_weights) not in (0, len(controls)))
        or any(a > b for a, b in zip(native_knots, native_knots[1:]))
        or not all(
            math.isfinite(value)
            for value in [x for point in controls for x in point] + native_knots + native_weights
        )
    ):
        raise ValueError("Complete finite native NURBS coefficients required")
    return {
        "controls": controls,
        "degree": degree,
        "knots": native_knots,
        "rational": rational,
        "weights": native_weights,
        "periodic": periodic,
    }


def capture_trim_data(curve: Any) -> dict[str, Any]:
    """
    Retain original two-dimensional coedge NURBS coefficients in native surface parameter units.

    These are original trim curves, not fitted model-space curves. Their
    coefficients do not supply a native-UV-to-world or material-coordinate map.
    """
    if curve.objectType != "adsk::core::NurbsCurve2D":
        raise ValueError("An original native NurbsCurve2D trim required")
    data = coefficients(curve, ("x", "y"))
    data["controls_native_uv"] = data.pop("controls")
    return data
