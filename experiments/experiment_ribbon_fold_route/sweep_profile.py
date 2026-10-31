"""
Describe the unchanged joined-lobe profile as exact arcs for rigid-sweep analysis.
"""

from __future__ import annotations

import math

from .sweep_transport import ProfileArc


def joined_profile_arcs(lines: int, diameter_mm: float) -> tuple[ProfileArc, ...]:
    """
    Reproduce the existing three-point lobe and end-cap geometry analytically.

    This returns contour mathematics only. It does not author a native sketch,
    replace ribbon_builder._add_section, alter pitch or create conductor bodies.
    Valley and end extension retain the builder's0.6h and0.2h dimensions.
    """
    if (
        isinstance(lines, bool)
        or not isinstance(lines, int)
        or lines < 1
        or isinstance(diameter_mm, bool)
        or not isinstance(diameter_mm, (int, float))
        or not math.isfinite(diameter_mm)
        or diameter_mm <= 0
    ):
        raise ValueError("A joined profile needs positive conductor count and diameter.")
    half = diameter_mm / 2
    valley = 0.6 * half
    extension = 0.2 * half
    nominal = lines * diameter_mm / 2
    lobe_radius = (half**2 + (half - valley) ** 2) / (2 * (half - valley))
    cy = half - lobe_radius
    low = math.atan2(valley - cy, half)
    high = math.atan2(valley - cy, -half)
    arcs = []
    for index in range(lines):
        center = -nominal + (index + 0.5) * diameter_mm
        arcs.extend(
            (
                ProfileArc((center, cy), lobe_radius, low, high),
                ProfileArc((center, -cy), lobe_radius, -high, -low),
            )
        )
    cap_radius = (extension**2 + valley**2) / (2 * extension)
    cx = nominal + extension - cap_radius
    phase = math.atan2(valley, nominal - cx)
    arcs.extend(
        (
            ProfileArc((cx, 0), cap_radius, -phase, phase),
            ProfileArc((-cx, 0), cap_radius, math.pi - phase, math.pi + phase),
        )
    )
    return tuple(arcs)
