"""
Represent the strict native straight-length floor in scaled material coordinates.
"""

from __future__ import annotations

import math

from .geometry import FoldRoute, Straight


def minimum_straight_length(point_tolerance_mm: float) -> float:
    """
    Separate endpoint uncertainty and point distinguishability from native segment construction.

    Fusion's point tolerance compares points; it is not a constructible edge
    length. Reserve one tolerance at each endpoint and another between them.
    Callers retain this three-tolerance construction floor independently of the
    original point tolerance, then apply their existing strict positive/zero
    slot policy. This is a conservative authoring guard, not a kernel guarantee
    or permission to relax native topology, fidelity or physical acceptance.
    """
    if (
        type(point_tolerance_mm) not in (int, float)
        or not math.isfinite(point_tolerance_mm)
        or point_tolerance_mm <= 0
    ):
        raise ValueError("Native point tolerance must be finite and positive")
    minimum = 3 * point_tolerance_mm
    if not math.isfinite(minimum):
        raise ValueError("Native construction floor must be finite")
    return minimum


def minimum_coordinate(minimum_mm: float, scale: float) -> float | None:
    """
    Return the smallest existing native floor with a strictly valid world-space product.
    """
    if not math.isfinite(minimum_mm) or minimum_mm <= 0 or not math.isfinite(scale) or scale <= 0:
        raise ValueError("Use finite positive native dimensions and existing slot directions")
    minimum = math.nextafter(minimum_mm / scale, math.inf)
    if minimum * scale <= minimum_mm:
        minimum = math.nextafter(minimum, math.inf)
    return minimum if math.isfinite(minimum) and minimum * scale > minimum_mm else None


def subminimum_straights(route: FoldRoute, minimum_mm: float) -> tuple[int, ...]:
    """
    Identify independent positive straights that do not meet the strict construction floor.

    Absent zero slots and bank-dependent flat fold leads are not independent
    straight primitives. This performs no cleanup or changed geometry proof.
    """
    if not math.isfinite(minimum_mm) or minimum_mm <= 0:
        raise ValueError("Use a finite positive native construction floor")
    return tuple(
        i
        for i, piece in enumerate(route.pieces)
        if isinstance(piece.geometry, Straight) and piece.geometry.material_length_mm <= minimum_mm
    )
