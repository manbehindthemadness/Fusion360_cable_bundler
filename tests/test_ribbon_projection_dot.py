"""
Retain compensated projection arithmetic at cancellation and exceptional inputs.
"""

import math

import pytest

from experiments.experiment_ribbon_terminal_hardware.projection_system import dot


@pytest.mark.parametrize(
    "first,second,expected",
    (
        ((1e16, 1.0, -1e16), (1.0, 1.0, 1.0), 1.0),
        ((math.ulp(0.0), -math.ulp(0.0)), (1.0, -1.0), 2 * math.ulp(0.0)),
        ((-0.0, -0.0), (1.0, 1.0), 0.0),
        ((2.0, 9.0), (3.0,), 6.0),
        ((), (3.0,), 0.0),
    ),
)
def test_projection_dot_retains_compensation_and_sequence_boundaries(
    first: tuple[float, ...], second: tuple[float, ...], expected: float
) -> None:
    """
    Preserve low cancellation terms, subnormals, sum-zero sign and shortest-sequence termination.
    """
    assert float(dot(first, second)).hex() == float(expected).hex()


@pytest.mark.parametrize(
    "first,second,error",
    (
        ((math.inf, -math.inf), (1.0, 1.0), ValueError),
        ((1e308, 1e308), (1.0, 1.0), OverflowError),
    ),
)
def test_invalid_projection_sums_preserve_their_arithmetic_error(
    first: tuple[float, ...], second: tuple[float, ...], error: type[Exception]
) -> None:
    """
    Invalid infinite cancellation and finite accumulator overflow cannot become usable directions.
    """
    with pytest.raises(error):
        dot(first, second)
