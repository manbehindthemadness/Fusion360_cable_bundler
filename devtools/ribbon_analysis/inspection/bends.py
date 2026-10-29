"""
Measure centre and edge bending on the exact frozen guides currently being viewed.
"""

from __future__ import annotations

import math
from typing import Any

from cable_bundler.routing.geometry import cross, magnitude

from ..traces import TracePath
from .geometry import PathSnapshot


def radius(trace: TracePath, u: float) -> float | None:
    """
    Return local cubic radius in millimetres, or None for a straight/stationary sample.

    None keeps infinite or undefined values out of finite JSON. These sampled
    display measurements are independent of solver-side intrinsic field bounds.
    """
    if not math.isfinite(u) or not 0 <= u <= 1:
        raise ValueError("Bend sample fraction must lie within [0,1].")
    count = len(trace.curves)
    index = min(count - 1, int(u * count))
    fraction = u * count - index
    curve = trace.curves[index]
    velocity = curve.derivative(fraction)
    speed = magnitude(velocity)
    if speed < 1e-12:
        return None
    curvature = magnitude(cross(velocity, curve.second_derivative(fraction))) / speed**3
    return 1 / curvature if curvature > 1e-12 else None


def inspect(snapshot: PathSnapshot, section: int) -> dict[str, Any]:
    """
    Share local radii and65curvature samples between the palette and diagnostics.

    The3Dline is a declared historical material-guide reference, not the missing
    wide-ribbon centre/edge ratio/scalar/flex contract or a physical certificate.
    Every search proposal is measured from its own frozen cubics, never its result.
    """
    guides = {guide.number: guide for guide in snapshot.guides}
    reference = 3 * snapshot.diameter_mm

    def sample(u: float) -> dict[str, Any]:
        """
        Keep measured radii separate from curvature normalized to the guide reference.
        """
        radii: dict[str, float | None] = {
            label: radius(guides[number], u) if number in guides else None
            for label, number in (("centre", 0), ("edge_a", -1), ("edge_b", -2))
        }
        edges: list[float] = []
        for label in ("edge_a", "edge_b"):
            edge_radius = radii[label]
            if edge_radius is not None:
                edges.append(edge_radius)
        centre = radii["centre"]
        return {
            "u": u,
            "radii_mm": radii,
            "utilization": {key: reference / value if value else 0 for key, value in radii.items()},
            "centre_edge_ratio": centre / min(edges) if centre is not None and edges else None,
        }

    return {
        "reference_radius_mm": reference,
        "has_edges": -1 in guides and -2 in guides,
        "selected": sample(snapshot.sections[section].u),
        "samples": [sample(index / 64) for index in range(65)],
        "scope": "Measured frozen cubic guides. The3Dline is a material-guide reference; wide-ribbon minimum-radius ratio, scalar and clearance flex remain unresolved. No full-thickness collision or physical acceptance is inferred.",
    }
