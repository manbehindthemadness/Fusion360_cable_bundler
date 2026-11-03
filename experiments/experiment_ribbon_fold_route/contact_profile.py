"""
Exclude empty joined-profile space from conservative material-cell envelopes.
"""

from __future__ import annotations

import math
from dataclasses import replace

from .contact_bounds import Cell, Span
from .contact_inverse import profile_height


def clip_profile(cell: Cell, lines: int, diameter: float) -> Cell | None:
    """
    Enclose occupied profile height over the entire cell's width interval.

    Each upper circular lobe has one maximum at its conductor center; the two
    outer side arcs decrease toward their tips. Endpoints and any enclosed lobe
    apex therefore bound the whole interval. An outward numerical guard enlarges
    this enclosure, without introducing physical clearance or penetration slack.
    Return None only when the original height interval contains no material.
    """
    maximum = max(
        profile_height(cell.q.low, lines, diameter),
        profile_height(cell.q.high, lines, diameter),
    )
    nominal = lines * diameter / 2
    index = max(0, math.ceil((cell.q.low + nominal) / diameter - 0.5))
    if index < lines and -nominal + (index + 0.5) * diameter <= cell.q.high:
        maximum = max(maximum, diameter / 2)
    maximum = math.nextafter(maximum + 1e-12 * diameter, math.inf)
    low, high = max(cell.height.low, -maximum), min(cell.height.high, maximum)
    if low > high:
        return None
    if low == cell.height.low and high == cell.height.high:
        return cell
    return replace(cell, height=Span(low, high))
