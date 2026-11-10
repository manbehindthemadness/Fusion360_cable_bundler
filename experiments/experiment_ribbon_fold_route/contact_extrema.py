"""
Enclose correlated plane-cylinder-plane projections through analytic edge extrema.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Callable, Optional

from devtools.ribbon_analysis.isometric_fold import CylindricalFold

Corners = tuple[tuple[float, float], ...]
Heights = tuple[float, float]
Extrema = Callable[[Corners, Heights], Optional[tuple[float, float]]]


def extrema(
    fold: CylindricalFold,
    corners: Corners,
    heights: Heights,
    alpha: float,
    beta: float,
    gamma: float,
) -> tuple[float, float] | None:
    """
    Enclose one affine material rectangle through the shared exact edge-extrema evaluator.
    """
    return prepare_extrema(fold, alpha, beta, gamma)(corners, heights)


def prepare_extrema(fold: CylindricalFold, alpha: float, beta: float, gamma: float) -> Extrema:
    """
    Bind immutable fold/axis constants without caching any material-cell result.

    At fixed height every fixed-xi slice is affine in eta, so extrema occur on
    the parallelogram boundary. Four edges at both heights retain every original
    endpoint, G1 join and stationary phase. Arithmetic order and finite guards
    remain unchanged; the returned evaluator retains only this projection's
    coefficients, including at most sixteen height-dependent coefficient pairs,
    with no material-cell result cache, global route cache or acceptance authority.
    """
    radius, angle = fold.radius_mm, abs(fold.angle_radians)
    sign = math.copysign(1.0, fold.angle_radians)
    arc = radius * angle
    sine, cosine = math.sin(angle), math.cos(angle)

    @lru_cache(maxsize=16)
    def height_coefficients(height: float) -> tuple[float, float]:
        """
        Reuse only the stationary amplitude and phase shift for an unchanged material height.
        """
        rho = radius - sign * height
        a, b = alpha * rho, -sign * gamma * rho
        return math.hypot(a, b), math.atan2(b, a)

    def value(xi: float, eta: float, height: float) -> float:
        """
        Evaluate the original material offset map with fixed trigonometric coefficients.
        """
        if xi <= 0:
            x, z = xi, height
        elif xi >= arc:
            x = radius * sine + (xi - arc) * cosine - sign * height * sine
            z = sign * radius * (1 - cosine) + sign * (xi - arc) * sine + height * cosine
        else:
            phase, rho = xi / radius, radius - sign * height
            x = rho * math.sin(phase)
            z = sign * (radius - rho * math.cos(phase))
        return alpha * x + beta * eta + gamma * z

    def edge_values(
        start: tuple[float, float], end: tuple[float, float], heights: Heights
    ) -> list[float]:
        """
        Retain endpoints, join crossings and all stationary points in their original order.
        """
        xi, eta = start
        dx, de = end[0] - xi, end[1] - eta
        parameters = [0.0, 1.0]
        low, high = 0.0, -1.0
        if dx != 0:
            parameters.extend([t for cut in (0.0, arc) if 0 < (t := (cut - xi) / dx) < 1])
            low, high = max(0.0, min(xi, end[0]) / radius), min(angle, max(xi, end[0]) / radius)
        values: list[float] = []
        for height in heights:
            points = list(parameters)
            if dx != 0:
                amplitude, shift = height_coefficients(height)
                derivative = (dx / radius) * amplitude
                if amplitude != 0 and (derivative == 0 or not math.isfinite(derivative)):
                    return [math.nan]
                if not math.isfinite(beta * de):
                    return [math.nan]
                if low <= high and derivative != 0:
                    ratio = -beta * de / derivative
                    # Include an extremum at +/-1 despite last-bit division error.
                    if abs(ratio) <= 1 + 1e-14:
                        phase = math.acos(max(-1.0, min(1.0, ratio)))
                        for root in (phase - shift, -phase - shift):
                            first = math.ceil((low - root) / math.tau)
                            last = math.floor((high - root) / math.tau)
                            for winding in range(first, last + 1):
                                p = root + winding * math.tau
                                points.append(max(0.0, min(1.0, (radius * p - xi) / dx)))
            values.extend([value(xi + dx * t, eta + de * t, height) for t in points])
        return values

    def bounds(corners: Corners, heights: Heights) -> tuple[float, float] | None:
        """
        Enclose all original boundary extrema, declining nonfinite arithmetic.
        """
        values: list[float] = []
        for start, end in zip(corners, corners[1:] + corners[:1]):
            values.extend(edge_values(start, end, heights))
        if not all(math.isfinite(result) for result in values):
            return None
        return min(values), max(values)

    return bounds
