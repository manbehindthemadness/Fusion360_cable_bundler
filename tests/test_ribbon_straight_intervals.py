"""
Preserve the exact prior outward interval certificate with fewer temporary allocations.
"""

from __future__ import annotations

import math
import random
from typing import Callable
from unittest.mock import Mock, patch

import pytest

from experiments.experiment_ribbon_fold_route import contact_bounds
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span


def _interval(low: float, high: float) -> Span:
    """
    Construct the original interval through an explicitly typed test boundary.
    """
    return Span(low, high)


def _original(
    origin: float,
    length: float,
    coefficients: tuple[float, float, float],
    cell: Cell,
    construct: Callable[[float, float], Span] = _interval,
) -> Span:
    """
    Retain the previous public Span algebra as an independent exact arithmetic oracle.
    """
    result = construct(origin, origin)
    for span, coefficient in zip((cell.u.scale(length), cell.q, cell.height), coefficients):
        result = result.add(span.scale(coefficient))
    guard = 1e-11 * (1 + max(abs(result.low), abs(result.high)))
    return construct(result.low - guard, result.high + guard)


@pytest.mark.parametrize("scale", (5e-324, 1e-300, 1e-9, 1.0, 1e9, 1e300))
@pytest.mark.parametrize("coefficients", ((0.0, -0.0, 1.0), (1.0, -2.0, 0.3), (-1e-9, 1e9, -1.0)))
def test_scalar_intervals_match_every_original_rounding_step(
    scale: float,
    coefficients: tuple[float, float, float],
) -> None:
    """
    Compare exact floating encodings across translations, zero terms, subnormals and finite overflow.
    """
    generator = random.Random(2162)
    for _ in range(30):
        a, b = sorted((generator.random(), generator.random()))
        q = sorted((generator.uniform(-2, 2) * scale, generator.uniform(-2, 2) * scale))
        cell = Cell(0, Span(a, b), Span(*q), Span(-0.5 * scale, 0.5 * scale))
        origin = generator.uniform(-10, 10) * scale
        length = generator.uniform(0.01, 2) * scale
        expected = _original(origin, length, coefficients, cell)
        actual = contact_bounds._straight_projection(origin, length, coefficients, cell)
        assert (float(actual.low).hex(), float(actual.high).hex()) == (
            float(expected.low).hex(),
            float(expected.high).hex(),
        )


def test_projection_allocates_one_final_interval_instead_of_nine() -> None:
    """
    Count actual Span construction while comparing identical complete outward enclosures.
    """
    cell = Cell(0, Span(0.1, 0.9), Span(-2, 1), Span(-0.5, 0.3))
    construct = Mock(wraps=Span)
    with patch.dict(vars(contact_bounds), Span=construct):
        expected = _original(7.0, 10.0, (0.3, -0.8, 0.0), cell, construct)
        assert construct.call_count == 9
        construct.reset_mock()
        actual = contact_bounds._straight_projection(7.0, 10.0, (0.3, -0.8, 0.0), cell)
        assert actual == expected and construct.call_count == 1


def test_zero_coefficients_still_widen_instead_of_erasing_outward_arithmetic() -> None:
    """
    The optimization must retain even zero-product rounding and all three ordered additions.
    """
    cell = Cell(0, Span(0, 1), Span(-2, 2), Span(-0.5, 0.5))
    expected = _original(0.0, 1.0, (0.0, 0.0, 0.0), cell)
    rounding = Mock(wraps=math.nextafter)
    with patch.object(math, "nextafter", rounding):
        actual = contact_bounds._straight_projection(0.0, 1.0, (0.0, 0.0, 0.0), cell)
    assert actual == expected and rounding.call_count == 14
