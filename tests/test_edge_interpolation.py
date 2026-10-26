"""
Check cubic interpolation against an independent exact polynomial trajectory.
"""

from __future__ import annotations

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_ribbon_cap_transition.edge_interpolation import cubic_controls
from experiments.experiment_ribbon_cap_transition.endpoint_first import evaluate


def _jet(u: float) -> tuple[Vector3, Vector3]:
    """
    Supply an exact spatial cubic and its analytical velocity.
    """
    return Vector3(u, u * u, u**3), Vector3(1, 2 * u, 3 * u * u)


@pytest.mark.parametrize("intervals", [64, 128, 512])
def test_piecewise_cubic_preserves_exact_polynomial(intervals: int) -> None:
    """
    Compare interior Bernstein evaluation with the unsampled polynomial.
    """
    points, knots = cubic_controls(_jet, intervals)
    assert len(points) == 3 * intervals + 1
    assert len(knots) == len(points) + 4
    assert knots[:4] == (0.0,) * 4 and knots[-4:] == (1.0,) * 4
    for segment in (0, intervals // 3, intervals - 1):
        controls = points[3 * segment : 3 * segment + 4]
        for fraction in (0.0, 0.21, 0.79, 1.0):
            actual = evaluate(controls, fraction)
            expected = _jet((segment + fraction) / intervals)[0]
            assert magnitude(difference(actual, expected)) < 1e-12
    assert points[0] == _jet(0)[0] and points[-1] == _jet(1)[0]


@pytest.mark.parametrize("intervals", [True, 0, 15, 1025, 64.5])
def test_invalid_resolution_rejects_before_sampling(intervals: object) -> None:
    """
    Keep work bounded and reject bools rather than interpreting them as counts.
    """
    with pytest.raises(ValueError):
        cubic_controls(_jet, intervals)  # type: ignore[arg-type]
