"""
Isolate the added width-based surface-curvature floor without weakening prior rules.

This diagnostic retains the inherited center/conductor curvature certificates
and the same finite-width straight-transition regularity. Surface curvature is
still measured;its width-based extension alone is removed from authoring policy.
No solver run or native construction occurs in this module.
"""

from __future__ import annotations

from .conductor_allocation import minimum_travel as inherited_minimum_travel
from .endpoint_first import EndpointCase
from .material_strip import MaterialSpan


def minimum_travel(case: EndpointCase, spans: tuple[MaterialSpan, ...]) -> tuple[float, ...]:
    """
    Retain inherited motion floors and flat ruling-transition length requirements.

    The principal-surface-curvature times ribbon-width limit is deliberately
    absent for this isolated comparison. This does not remove the original
    macaroni bound,conductor radius,material regularity or endpoint checks.
    Straight-only ruling changes remain an explicit unmodified limitation.
    """
    inherited = inherited_minimum_travel(case, tuple(span.motion for span in spans))
    half_width = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    return tuple(
        max(old, half_width * abs(span.end_slope - span.start_slope) * (1 + 1e-12))
        for old, span in zip(inherited, spans)
    )
