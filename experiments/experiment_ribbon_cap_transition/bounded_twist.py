"""
Select endpoint-equivalent signed twist without retaining extra winding.
"""

import math


def shortest_twist(degrees: float) -> float:
    """
    Return a finite roll in [-180,180], retaining the sign of half-turn ties.

    Modulo360 preserves ordered endpoint orientation, not physical winding.
    No modulo180 equivalence or conductor-order reversal is permitted.
    """
    if not math.isfinite(degrees):
        raise ValueError("Twist must be finite.")
    result = math.fmod(degrees, 360.0)
    if result > 180:
        result -= 360
    elif result < -180:
        result += 360
    return 0.0 if result == 0 else result
