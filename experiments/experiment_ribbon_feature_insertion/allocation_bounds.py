"""
Exclude only straight masks whose nonnegative bounded travel cannot reach an endpoint coordinate.
"""

from __future__ import annotations

import math
from typing import Sequence


class StraightReach:
    """
    Bind one affine allocation's rows and existing sum budget without storing geometry or feasibility.

    Each accepted allocation has nonnegative clamped coordinates, sum at most
    budget plus 1e-8, and hard-coordinate residual at most 1e-8. A row's attainable
    interval therefore lies between zero and its extreme active coefficients
    times that sum. Bounds include those original allowances, outward rounding,
    and conservative product/summation roundoff. Overlap is inconclusive and
    always leaves the original guide fit and final physical contracts required.
    Unbounded or numerically overflowing ranges never exclude a mask.
    """

    def __init__(
        self,
        rows: Sequence[Sequence[float]],
        right: Sequence[float],
        maximum_sum: float | None,
    ) -> None:
        """
        Freeze finite matching affine data; preserve omitted-budget behavior exactly.
        """
        self.rows = tuple(tuple(row) for row in rows)
        self.right = tuple(right)
        if len(self.rows) != len(self.right) or any(
            len(row) != len(self.rows[0]) for row in self.rows
        ):
            raise ValueError("Use matching straight-allocation rows and targets")
        if any(not math.isfinite(value) for row in self.rows for value in row) or any(
            not math.isfinite(value) for value in self.right
        ):
            raise ValueError("Use finite straight-allocation coefficients and targets")
        if maximum_sum is not None and (
            type(maximum_sum) not in (int, float)
            or not math.isfinite(maximum_sum)
            or maximum_sum < 0
        ):
            raise ValueError("Use a finite nonnegative straight-coordinate budget")
        self.maximum_sum = maximum_sum

    def excludes(self, active: Sequence[int]) -> bool:
        """
        Reject a mask only on strict disjoint coordinate ranges; never certify an allocation.

        Callers keep their per-mask checkpoint and original ordinal/accounting.
        Eight budget ulps cover normalization and the original sum comparison.
        Four ulps per term exceed ordinary rounded products and the final fsum
        error for the at-most-seven-slot domain. Overflow declines acceleration.
        """
        if self.maximum_sum is None:
            return False
        limit = math.nextafter(self.maximum_sum + 1e-8 + 8 * math.ulp(self.maximum_sum), math.inf)
        if not math.isfinite(limit):
            return False
        for row, target in zip(self.rows, self.right):
            coefficients = tuple(row[index] for index in active)
            low = min((0.0, *coefficients)) * limit
            high = max((0.0, *coefficients)) * limit
            scale = max(abs(low), abs(high))
            if not math.isfinite(scale):
                continue
            margin = math.nextafter(1e-8 + 4 * max(1, len(active)) * math.ulp(scale), math.inf)
            lower = math.nextafter(low - margin, -math.inf)
            upper = math.nextafter(high + margin, math.inf)
            if target < lower or target > upper:
                return True
        return False
