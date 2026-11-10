"""
Contract rejected nonlinear correction steps within the original trial allowance.
"""

from __future__ import annotations

import math


def contracted_fraction(
    fraction: float, before: float, observed: float | None, predicted_change: float
) -> float:
    """
    Use measured curvature to shrink one rejected step, with halving as the fallback.

    The predicted change is an upper bound on the directional maximum-merit
    derivative from the existing linear model. A negative value permits a
    quadratic through the base value and rejected observation. Safeguards keep
    the next fraction between one tenth and one half of the previous fraction.
    An inadmissible trial supplies no observation and retains ordinary halving.
    This chooses only a scalar; the caller owns trials, strict nonlinear descent,
    coordinate bounds and final certificates. No extra evaluation is requested.
    """
    half = 0.5 * fraction
    if observed is None or not all(
        math.isfinite(value) for value in (fraction, before, observed, predicted_change)
    ):
        return half
    if predicted_change >= 0.0:
        return half
    curvature = observed - before - fraction * predicted_change
    if curvature <= 0.0:
        return half
    minimizer = -0.5 * predicted_change * fraction * fraction / curvature
    return min(half, max(0.1 * fraction, minimizer))
