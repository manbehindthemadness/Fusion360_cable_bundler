"""
Check encoded phase pullbacks against exact affine curves and malformed source bases.
"""

from __future__ import annotations

import math
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.material_distance import DistanceSpan, enclose
from experiments.experiment_ribbon_complete.material_phase import uniform_phase_chart
from tests.test_ribbon_complete_execution import checkpoint


def knots(angle: float, count: int) -> tuple[float, ...]:
    """
    Encode the documented cubic uniform authoring partition without generating geometry.
    """
    cuts = tuple(angle * i / count for i in range(count + 1))
    return (cuts[0],) * 4 + tuple(v for v in cuts[1:-1] for _ in range(3)) + (cuts[-1],) * 4


@pytest.mark.parametrize("angle,count", ((0.102, 5), (0.375, 16), (math.pi, 126)))
def test_encoded_partition_has_exact_requested_endpoints_and_positive_cell_maps(
    angle: float, count: int
) -> None:
    """
    Each cell maps bijectively without discarding either encoded knots or nominal material cuts.
    """
    source = knots(angle, count)
    chart = uniform_phase_chart(angle, source)
    assert chart.encoded == tuple(dict.fromkeys(Fraction(v) for v in source))
    assert chart.nominal == tuple(Fraction(angle) * i / count for i in range(count + 1))
    assert chart.nominal[0] == 0 and chart.nominal[-1] == Fraction(angle)
    assert all(
        (b - a) / (d - c) > 0
        for a, b, c, d in zip(chart.encoded, chart.encoded[1:], chart.nominal, chart.nominal[1:])
    )


def test_encoding_jacobian_error_is_included_by_the_existing_length_bound() -> None:
    """
    Exact affine path lengths expose every encoded-cell stretch without geometry normalization.
    """
    chart = uniform_phase_chart(0.102, knots(0.102, 5))
    assert chart.encoded[-1] != chart.nominal[-1]
    assert chart.maximum_phase_error_radians > 0
    bounds, exact_errors = [], []
    for a, b, c, d in zip(chart.encoded, chart.encoded[1:], chart.nominal, chart.nominal[1:]):
        span = DistanceSpan(c, d, ((a, Fraction(0), Fraction(0)), (b, Fraction(0), Fraction(0))))
        bounds.append(enclose(span, checkpoint).upper_mm)
        exact_errors.append(abs((b - a) - (d - c)))
    assert sum(bounds) >= sum(exact_errors) > 0


def test_one_ulp_source_basis_change_is_rejected_without_tolerance_snapping() -> None:
    """
    A small arbitrary basis edit is not the documented uniform authoring encoding.
    """
    source = knots(0.102, 5)
    changed = tuple(math.nextafter(v, math.inf) if v == source[4] else v for v in source)
    with pytest.raises(ValueError, match="source knots changed"):
        uniform_phase_chart(0.102, changed)


@pytest.mark.parametrize("source", ((), (0.0,) * 8, (0.0,) * 3 + (1.0,) * 4, (float("nan"),)))
def test_missing_degenerate_or_malformed_source_basis_never_gets_a_chart(
    source: tuple[float, ...],
) -> None:
    """
    Source validity remains an exact contract rather than a dimensional acceptance threshold.
    """
    with pytest.raises(ValueError):
        uniform_phase_chart(1.0, source)
