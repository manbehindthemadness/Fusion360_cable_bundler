"""
Derive lateral S-fold dimensions through bounded scalar geometry equations.
"""

from __future__ import annotations

import math

from .geometry import Straight
from .primitives import Piece, fold


def halfturn_pair(
    distance: float, height: float, radius: float, width: float, runway: float
) -> tuple[Piece, ...]:
    """
    Preserve the previous outward half-turn steering as a comparison baseline.
    """
    absolute = abs(distance)
    maximum = _offset(math.sin(math.pi / 4), math.pi, radius, width, runway)
    bank = (
        math.asin(_sine(absolute, math.pi, radius, width, runway, math.sin(math.pi / 4)))
        if absolute < maximum
        else math.pi / 4
    )
    direction = -math.copysign(math.pi, height)
    bank = -math.copysign(bank, distance)
    middle = (Straight(absolute - maximum),) if absolute > maximum else ()
    return (
        fold(radius, width, direction, bank, runway),
        *middle,
        fold(radius, width, -direction, bank, runway),
    )


def _offset(s: float, angle: float, radius: float, width: float, runway: float) -> float:
    """
    Evaluate the lateral displacement of a zero-middle-run opposite-angle pair.
    """
    c = math.sqrt(max(0.0, 1 - s * s))
    return (width * s * s + 2 * runway * s * c) * (1 - math.cos(angle)) + 2 * radius * s * (
        angle - math.sin(angle)
    )


def _sine(
    distance: float, angle: float, radius: float, width: float, runway: float, upper: float
) -> float:
    """
    Invert the monotone offset on the established regular bank interval.
    """
    a, b = width * (1 - math.cos(angle)), radius * (angle - math.sin(angle))
    if runway == 0:
        return distance / (b + math.sqrt(b * b + a * distance))
    low, high = 0.0, upper
    for _ in range(52):
        middle = (low + high) / 2
        if _offset(middle, angle, radius, width, runway) < distance:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def _derivative(s: float, angle: float, radius: float, width: float, runway: float) -> float:
    """
    Return the sign numerator of local material-length change along exact closure.
    """
    c = math.sqrt(1 - s * s)
    a = 1 - math.cos(angle)
    by_s = (2 * width * s + 2 * runway * (1 - 2 * s * s) / c) * a + 2 * radius * (
        angle - math.sin(angle)
    )
    by_angle = (width * s * s + 2 * runway * s * c) * math.sin(angle) + 2 * radius * s * a
    return radius * (1 - s * s) * by_s - (width + radius * angle * s) * by_angle


def dimensions(
    distance: float, radius: float, width: float, runway: float
) -> tuple[float, float, float]:
    """
    Determine bank, bend angle and nonnegative middle length without route guesses.

    The pi-boundary stationary bank solves a strictly increasing cubic. If its
    middle run would be negative, use the zero-run family and bracket a stationary
    angle instead. Every scalar solve is capped at52bisections. This is a local
    material-length choice within one fold family, not global route optimality.
    """
    low, high = 0.0, math.sqrt(0.5)
    for _ in range(52):
        s = (low + high) / 2
        value = 2 * math.pi * radius * s**3 + 2 * (width + distance) * s * s - distance
        if value < 0:
            low = s
        else:
            high = s
    upper = (low + high) / 2
    bank = math.asin(upper)
    at_pi = _offset(upper, math.pi, radius, width, runway)
    if distance >= at_pi:
        middle = (distance - at_pi) / (2 * upper * math.cos(bank))
        return bank, math.pi, middle
    low, high = 0.0, math.pi
    for _ in range(52):
        angle = (low + high) / 2
        if _offset(upper, angle, radius, width, runway) < distance:
            low = angle
        else:
            high = angle
    low, high = (low + high) / 2, math.pi
    s_pi = _sine(distance, math.pi, radius, width, runway, upper)
    if _derivative(s_pi, math.pi, radius, width, runway) <= 0:
        return math.asin(s_pi), math.pi, 0.0
    for _ in range(52):
        angle = (low + high) / 2
        s = _sine(distance, angle, radius, width, runway, upper)
        if _derivative(s, angle, radius, width, runway) < 0:
            low = angle
        else:
            high = angle
    angle = (low + high) / 2
    s = _sine(distance, angle, radius, width, runway, upper)
    return math.asin(s), angle, 0.0


def lateral_pair(
    distance: float, height: float, radius: float, width: float, runway: float
) -> tuple[Piece, ...]:
    """
    Place the continuously sized S-fold layer opposite the subsequent height move.
    """
    bank, angle, middle = dimensions(abs(distance), radius, width, runway)
    direction = -math.copysign(angle, height)
    bank = -math.copysign(bank, distance)
    between = (Straight(middle),) if middle > 1e-12 else ()
    return (
        fold(radius, width, direction, bank, runway),
        *between,
        fold(radius, width, -direction, bank, runway),
    )
