"""
Partition complete material boxes using midpoint or actual fold-phase hints.
"""

from __future__ import annotations

import math
from enum import Enum

from devtools.ribbon_analysis.isometric_fold import CylindricalFold

from .contact_bounds import Cell
from .geometry import Straight


class Subdivision(Enum):
    """
    Select numerical cuts without changing full-cell proof or coverage requirements.
    """

    MIDPOINT = "midpoint"
    MATERIAL_PHASES = "material_phases"


def subdivide(
    cell: Cell, geometry: Straight | CylindricalFold, policy: Subdivision
) -> tuple[Cell, Cell]:
    """
    Keep the original largest dimension and optionally align longitudinal cuts to G1 joins.

    Entry and exit fractions at both width endpoints are hints only. Their
    numerical location grants no material exclusion, phase certificate or
    clearance. Cell.split retains the complete parent and original depth charge.
    """
    length = geometry.material_length_mm
    if policy is Subdivision.MIDPOINT:
        return cell.split(length)
    if policy is not Subdivision.MATERIAL_PHASES:
        raise ValueError("Select an explicit material subdivision policy")
    cuts: tuple[float, ...] = ()
    if isinstance(geometry, CylindricalFold):
        cosine, sine = math.cos(geometry.bank_radians), math.sin(geometry.bank_radians)
        arc = geometry.radius_mm * abs(geometry.angle_radians) / (cosine * length)
        entries = tuple(
            (geometry.before_mm - q * sine / cosine) / length for q in (cell.q.low, cell.q.high)
        )
        cuts = tuple(value for entry in entries for value in (entry, entry + arc))
    return cell.split(length, longitudinal_cuts=cuts)
