"""
Resolve flat ribbon trace dimensions against a measured contact pitch.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FfcDimensions:
    """
    Retain the contact pitch and the joined flat ribbon cross-section dimensions.
    """

    pitch_mm: float
    trace_width_mm: float
    spacing_mm: float


def resolve_ffc_dimensions(
    pitch_mm: float,
    contact_widths_mm: tuple[Optional[float], ...],
    trace_width_mm: Optional[float],
    spacing_mm: Optional[float],
) -> FfcDimensions:
    """
    Fill Auto values from first-end contacts and require one exact center pitch.

    Point contacts use eighty percent of the pitch. A measured contact wider
    than the pitch leaves at least a two-percent insulating web.
    """
    if not math.isfinite(pitch_mm) or pitch_mm <= 0.0 or not contact_widths_mm:
        raise ValueError("FFC contact pitch must be finite and positive.")
    if trace_width_mm is None and spacing_mm is None:
        candidates = tuple(
            min(width, pitch_mm * 0.98)
            if width is not None and math.isfinite(width) and width > 0.0
            else pitch_mm * 0.8
            for width in contact_widths_mm
        )
        trace_width_mm = min(candidates)
    if trace_width_mm is None:
        trace_width_mm = pitch_mm - spacing_mm
    if spacing_mm is None:
        spacing_mm = pitch_mm - trace_width_mm
    if (
        not math.isfinite(trace_width_mm)
        or not math.isfinite(spacing_mm)
        or trace_width_mm <= 0.0
        or spacing_mm <= 0.0
        or abs(trace_width_mm + spacing_mm - pitch_mm) > 0.0001
    ):
        raise ValueError(
            "FFC Trace Width and Spacing must be positive and sum to the contact pitch."
        )
    return FfcDimensions(pitch_mm, trace_width_mm, spacing_mm)
