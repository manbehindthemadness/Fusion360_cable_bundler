"""
Preserve Fusion NURBS curve coefficients through explicit fields, including native vector collections.
"""

from __future__ import annotations

from typing import Any

from .native_spline_data import coefficients


def capture_nurbs_data(curve: Any) -> dict[str, Any]:
    """
    Capture documented NurbsCurve3D.getData fields without treating native arrays as Python lists.

    Fusion may return Point3DVector rather than list or tuple. Iterate that
    collection directly, retaining all original controls, knots and weights.
    This captures coefficients only; it grants no curve-domain, face-image,
    positive-basis, correspondence or material qualification.

    Raise ValueError for failed extraction, malformed dimensions or nonfinite
    coefficients. Negative weights remain evidence rather than being repaired.
    """
    data = coefficients(curve, ("x", "y", "z"))
    data["controls_cm"] = data.pop("controls")
    return data
