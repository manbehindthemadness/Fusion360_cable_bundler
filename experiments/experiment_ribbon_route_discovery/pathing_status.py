"""
Measure fixed connection targets without introducing clearance or contact decisions.
"""

from __future__ import annotations

from typing import Any

from cable_bundler.routing.geometry import difference, magnitude
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.director_shooting import endpoint_metrics
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase


def endpoint_status(case: EndpointCase, path: CompatiblePath) -> dict[str, Any]:
    """
    Report connection goals only; deliberately provide no invented contact-clear result.
    """
    half = path.field.half_width_mm
    gaps = tuple(
        magnitude(difference(path.lane(1, q)[0], case.end.translated(case.end_width, q)))
        for q in (-half, 0.0, half)
    )
    metrics = endpoint_metrics(case, path)
    return {
        "scope": "Connection targets only; self-contact is not evaluated or enforced.",
        "contact_enforced": False,
        "maximum_gap_mm": max(gaps),
        "position_threshold_mm": case.diameter_mm / 2,
        "position_connected": max(gaps) <= case.diameter_mm / 2,
        "strict_frame_gate": max(metrics["edge_tangent_error"], metrics["terminal_width_error"])
        <= 1e-8,
    }
