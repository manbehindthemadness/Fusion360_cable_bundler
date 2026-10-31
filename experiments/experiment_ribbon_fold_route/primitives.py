"""
Construct unchanged material primitives with flat terminal profiles.
"""

from __future__ import annotations

import math
from typing import Union

from devtools.ribbon_analysis.isometric_fold import CylindricalFold

from .geometry import Straight

Piece = Union[Straight, CylindricalFold]


def fold(radius: float, width: float, angle: float, bank: float, runway: float) -> CylindricalFold:
    """
    Retain flat terminal material profiles and explicitly requested extra runway.
    """
    lead = width / 2 * abs(math.tan(bank)) + runway
    return CylindricalFold(radius, angle, bank, width, lead, lead)
