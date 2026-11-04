"""
Match equivalent material-fold factorizations by rotation, independent of quadratic-root order.
"""

from __future__ import annotations

import math
from enum import Enum

from devtools.ribbon_analysis.isometric_fold import CylindricalFold


class BranchPolicy(Enum):
    """
    Distinguish legacy root indexing from physical factor continuation.
    """

    INDEX = "root_index"
    CONTINUOUS = "continuous_rotation"


def _rotation(fold: CylindricalFold) -> tuple[float, float, float]:
    """
    Represent the transverse material rotation as its unit quaternion's nonzero components.
    """
    half, bank = fold.angle_radians / 2, fold.bank_radians
    return math.cos(half), math.sin(bank) * math.sin(half), -math.cos(bank) * math.sin(half)


def closest(
    previous: tuple[CylindricalFold, ...],
    choices: tuple[tuple[CylindricalFold, ...], ...],
) -> tuple[CylindricalFold, ...] | None:
    """
    Continue the same ordered factor rotations, rejecting ambiguous or changed-size branches.

    Summed 1-dot-squared quaternion distance is dimensionless and invariant to
    quaternion sign. Root order, scene position and conductor dimensions cannot
    choose the branch. A tied match stays unresolved instead of picking an index.
    """
    ranked = []
    for index, choice in enumerate(choices):
        if len(choice) != len(previous):
            continue
        cost = math.fsum(
            1
            - min(1.0, abs(math.fsum(a * b for a, b in zip(_rotation(before), _rotation(after)))))
            ** 2
            for before, after in zip(previous, choice)
        )
        ranked.append((cost, index, choice))
    ranked.sort(key=lambda item: (item[0], item[1]))
    if not ranked or (len(ranked) > 1 and abs(ranked[0][0] - ranked[1][0]) <= 1e-12):
        return None
    return ranked[0][2]
