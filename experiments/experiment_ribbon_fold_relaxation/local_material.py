"""
Share identical immutable local folds without retaining world placements or models.
"""

from __future__ import annotations

import struct
from functools import lru_cache

from devtools.ribbon_analysis.isometric_fold import CylindricalFold


class LocalFolds:
    """
    Retain at most64 validated local shapes within one material model's lifetime.

    Binary keys distinguish all six float parameters, including signed zero.
    Other scalar types follow original construction and validation directly.
    The cache owns geometry only, with no model, pose or acceptance reference.
    """

    def __init__(self) -> None:
        """
        Create an empty store whose closure has no reference back to this owner.
        """

        @lru_cache(maxsize=64)
        def construct(key: bytes) -> CylindricalFold:
            """
            Validate a new exact local shape; failed construction is never cached.
            """
            return CylindricalFold(*struct.unpack("!6d", key))

        self._construct = construct

    def __call__(
        self,
        radius_mm: float,
        angle_radians: float,
        bank_radians: float,
        width_mm: float,
        before_mm: float,
        after_mm: float,
    ) -> CylindricalFold:
        """
        Reuse only an identical six-float shape, retaining original nonfloat behavior.
        """
        values = (radius_mm, angle_radians, bank_radians, width_mm, before_mm, after_mm)
        if not all(type(value) is float for value in values):
            return CylindricalFold(*values)
        return self._construct(struct.pack("!6d", *values))
