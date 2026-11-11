"""
Verify bounded linear angular closure independently of historical ribbon layouts.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_feature_insertion import repair
from experiments.experiment_ribbon_feature_insertion.angular_allocation import (
    Vector,
    bounded_correction,
)

IDENTITY: list[Vector] = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]


@pytest.mark.parametrize(
    "residual,rays,lengths,budget,expected",
    (
        ((2.0, 0.0, 0.0), ((1.0, 0.0, 0.0),), (0.1,), None, (-1.9, 0.0, 0.0)),
        ((-2.0, 0.0, 0.0), ((1.0, 0.0, 0.0),), (0.25,), 1.0, (1.25, 0.0, 0.0)),
        (
            (1.0, -2.0, 0.3),
            ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            (0.1, 0.4),
            1.0,
            (-0.9, 1.4, -0.3),
        ),
        (
            (0.2, -0.2, 0.4),
            ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            (1.0, 1.0),
            3.0,
            (0.0, 0.0, -0.4),
        ),
        (
            (1.1, 0.2, -0.3),
            ((1.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
            (0.1, 1.0),
            2.0,
            (0.0, -0.2, 0.3),
        ),
        ((0.2, -0.3, 0.4), (), (), None, (-0.2, 0.3, -0.4)),
    ),
)
@pytest.mark.parametrize("angular_rate", (0.25, 1.0, 20.0))
def test_minimum_angular_motion_respects_finite_transfer_and_travel_bounds(
    residual: Vector,
    rays: tuple[Vector, ...],
    lengths: tuple[float, ...],
    budget: float | None,
    expected: Vector,
    angular_rate: float,
) -> None:
    """
    Compare against exact Euclidean projections onto authored intervals and simplices.

    Identity angular columns make the constrained optimum the residual to the
    nearest feasible straight displacement. The expected answers follow from
    interval endpoints or simplex faces, rather than the implementation's masks.
    """
    columns = [(angular_rate * x, angular_rate * y, angular_rate * z) for x, y, z in IDENTITY]
    result = bounded_correction(columns, residual, rays, lengths, budget, lambda: None)
    assert result == pytest.approx([value / angular_rate for value in expected], abs=1e-10)


def _rotate(vector: Vector) -> Vector:
    """
    Rotate an authored linear endpoint map without selecting a new physical case.
    """
    a, b = math.cos(0.7), math.sin(0.7)
    return vector[0] * a - vector[1] * b, vector[0] * b + vector[1] * a, vector[2]


def test_covariant_columns_keep_the_same_angular_solution() -> None:
    """
    Scene axes cannot change the correction when the full linear map rotates with them.
    """
    result = bounded_correction(
        [_rotate(column) for column in IDENTITY],
        _rotate((1.0, -2.0, 0.3)),
        (_rotate((1.0, 0.0, 0.0)), _rotate((0.0, 1.0, 0.0))),
        (0.1, 0.4),
        1.0,
        lambda: None,
    )
    assert result == pytest.approx((-0.9, 1.4, -0.3), abs=1e-10)


def test_rank_failure_remains_unresolved_and_checkpoint_errors_propagate() -> None:
    """
    Infeasible linear equations and cancelled work cannot become a purported correction.
    """
    assert (
        bounded_correction(
            [(0.0, 1.0, 0.0)], (2.0, 0.0, 0.0), ((1.0, 0.0, 0.0),), (0.1,), None, lambda: None
        )
        is None
    )
    checkpoint = Mock(side_effect=TimeoutError("original limit"))
    with pytest.raises(TimeoutError, match="original limit"):
        bounded_correction(IDENTITY, (1.0, 0.0, 0.0), (), (), None, checkpoint)
    checkpoint.assert_called_once()


def test_three_positive_slots_have_at_most_sixteen_algebraic_faces() -> None:
    """
    The caller pays for one finite projection without another geometric candidate or Newton action.
    """
    checkpoint = Mock()
    result = bounded_correction(
        IDENTITY, (1.0, -2.0, 3.0), tuple(IDENTITY), (0.1, 0.4, 0.2), 1.0, checkpoint
    )
    assert result == pytest.approx((-0.9, 1.4, -2.8), abs=1e-10)
    assert checkpoint.call_count == 16


def test_unexpected_support_shape_rejects_before_projection() -> None:
    """
    The nearest-cone support bound cannot silently become a larger enumeration.
    """
    with pytest.raises(ValueError, match="three"):
        bounded_correction(IDENTITY, (1.0, 0.0, 0.0), tuple(IDENTITY) * 2, (1.0,) * 6, None, Mock())


@pytest.mark.parametrize("budget,residual,expected", ((None, 0.2, -0.1), (0.2, -0.3, 0.2)))
def test_resumed_correction_integrates_bounds_with_the_original_six_derivative_probes(
    monkeypatch: pytest.MonkeyPatch, budget: float | None, residual: float, expected: float
) -> None:
    """
    Exercise actual derivative/correction dispatch on an authored affine endpoint boundary.

    Free span elimination would return no angular correction, hiding the finite
    negative-length or total-travel violation. No saved material route is used.
    """
    probes: list[tuple[float, ...]] = []

    def changed(frames: Any, delta: list[float], scale: float) -> tuple[float, ...]:
        """
        Supply a unit-rate affine angular endpoint map at the geometry boundary.
        """
        del frames
        return tuple(scale * value for value in delta)

    def reframed(boundary: Any, chain: Any, frames: tuple[float, ...], **kwargs: Any) -> Any:
        """
        Retain each original derivative probe without nonlinear geometry evaluation.
        """
        del boundary, chain, kwargs
        probes.append(frames)
        return SimpleNamespace(topology=frames)

    def model(boundary: Any, topology: tuple[float, ...]) -> Any:
        """
        Expose the same angular endpoint columns and one finite positive straight ray.
        """
        del boundary
        return SimpleNamespace(
            endpoint=lambda values: SimpleNamespace(origin=Vector3(*topology)),
            equations=lambda: (((1.0, 0.0, 0.0),), (0.0, 0.0, 0.0)),
        )

    monkeypatch.setattr(repair, "changed", changed)
    monkeypatch.setattr(repair, "reframed", reframed)
    monkeypatch.setitem(vars(repair), "Model", model)
    sample_boundary: Any = SimpleNamespace(targets=SimpleNamespace(diameter_mm=1.0))
    sample_chain: Any = SimpleNamespace(targets=(object(),), topology=(0.0, 0.0, 0.0))
    result = repair.correction(
        sample_boundary,
        sample_chain,
        repair.Closure((0.1,), (residual, 0.0, 0.0), abs(residual)),
        lambda: None,
        straight_motion=repair.StraightMotion.REALLOCATABLE,
        maximum_straight_mm=budget,
    )
    assert result == pytest.approx((expected, 0.0, 0.0), abs=1e-10)
    assert len(probes) == 6
