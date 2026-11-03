"""
Enclose correlated plane-cylinder-plane projections through analytic edge extrema.
"""

from __future__ import annotations

import math

from devtools.ribbon_analysis.isometric_fold import CylindricalFold


def extrema(
    fold: CylindricalFold,
    corners: tuple[tuple[float, float], ...],
    heights: tuple[float, float],
    alpha: float,
    beta: float,
    gamma: float,
) -> tuple[float, float] | None:
    """
    Bound f(xi)+beta*eta on a thick affine material rectangle without losing correlation.

    At fixed height every fixed-xi slice is affine in eta, so an extremum
    occurs on the parallelogram boundary. Height is affine as well. Four edges
    at both height endpoints therefore suffice, including their stationary
    phases and G1 joins. Return None if finite arithmetic cannot retain this bound.
    """
    values: list[float] = []
    for start, end in zip(corners, corners[1:] + corners[:1]):
        for height in heights:
            values.extend(_edge_values(fold, start, end, height, alpha, beta, gamma))
    if not all(math.isfinite(value) for value in values):
        return None
    return min(values), max(values)


def _edge_values(
    fold: CylindricalFold,
    start: tuple[float, float],
    end: tuple[float, float],
    height: float,
    alpha: float,
    beta: float,
    gamma: float,
) -> list[float]:
    """
    Evaluate endpoints, join crossings and all stationary points of one edge.
    """
    xi, eta = start
    dx, de = end[0] - xi, end[1] - eta
    radius, angle = fold.radius_mm, abs(fold.angle_radians)
    arc = radius * angle
    parameters = [0.0, 1.0]
    if dx != 0:
        parameters.extend(t for cut in (0.0, arc) if 0 < (t := (cut - xi) / dx) < 1)
        low, high = max(0.0, min(xi, end[0]) / radius), min(angle, max(xi, end[0]) / radius)
        sign = math.copysign(1.0, fold.angle_radians)
        rho = radius - sign * height
        a, b = alpha * rho, -sign * gamma * rho
        amplitude = math.hypot(a, b)
        derivative = (dx / radius) * amplitude
        if amplitude != 0 and (derivative == 0 or not math.isfinite(derivative)):
            return [math.nan]
        if not math.isfinite(beta * de):
            return [math.nan]
        if low <= high and derivative != 0:
            ratio = -beta * de / derivative
            # An extremum at +/-1 is included despite last-bit division error.
            if abs(ratio) <= 1 + 1e-14:
                phase = math.acos(max(-1.0, min(1.0, ratio)))
                shift = math.atan2(b, a)
                for root in (phase - shift, -phase - shift):
                    first = math.ceil((low - root) / math.tau)
                    last = math.floor((high - root) / math.tau)
                    for winding in range(first, last + 1):
                        p = root + winding * math.tau
                        parameters.append(max(0.0, min(1.0, (radius * p - xi) / dx)))
    return [_value(fold, xi + dx * t, eta + de * t, height, alpha, beta, gamma) for t in parameters]


def _value(
    fold: CylindricalFold,
    xi: float,
    eta: float,
    height: float,
    alpha: float,
    beta: float,
    gamma: float,
) -> float:
    """
    Project the same plane-cylinder-plane offset map as the placed material surface.
    """
    radius, angle = fold.radius_mm, abs(fold.angle_radians)
    sign = math.copysign(1.0, fold.angle_radians)
    arc = radius * angle
    if xi <= 0:
        x, z = xi, height
    elif xi >= arc:
        sine, cosine = math.sin(angle), math.cos(angle)
        x = radius * sine + (xi - arc) * cosine - sign * height * sine
        z = sign * radius * (1 - cosine) + sign * (xi - arc) * sine + height * cosine
    else:
        phase, rho = xi / radius, radius - sign * height
        x = rho * math.sin(phase)
        z = sign * (radius - rho * math.cos(phase))
    return alpha * x + beta * eta + gamma * z
