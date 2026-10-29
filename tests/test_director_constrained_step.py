"""
Verify bounded quadratic steps on independently solvable feasible subproblems.
"""

import pytest

from experiments.experiment_ribbon_cap_transition.director_constrained_step import (
    constrained_step,
)


def test_unconstrained_quadratic_matches_damped_least_squares() -> None:
    """
    Recover the exact damped minimizer when no geometric constraint blocks it.
    """
    result = constrained_step(
        [(1.0, 0.0), (0.0, 1.0)],
        (-2.0, -3.0),
        0.001,
        [(), ()],
        (),
        (0.0, 0.0),
        (-10.0, -10.0),
        (10.0, 10.0),
    )
    assert result.values == pytest.approx((2 / 1.001, 3 / 1.001))
    assert result.status == "stationary linearized subproblem"
    assert result.iterations <= 32


@pytest.mark.parametrize("duplicates", [1, 3])
def test_active_boundary_allows_tangential_progress(duplicates: int) -> None:
    """
    Move in ywhile a blocked downhill xdirection must remain zero.
    """
    result = constrained_step(
        [(1.0, 0.0), (0.0, 1.0)],
        (-1.0, -3.0),
        0.001,
        [(-1.0,) * duplicates, (0.0,) * duplicates],
        (0.0,) * duplicates,
        (1.0, 0.0),
        (-10.0, -10.0),
        (10.0, 10.0),
    )
    assert result.values == pytest.approx((0, 3 / 1.001), abs=1e-10)
    assert result.status == "stationary linearized subproblem"


def test_oblique_constraint_and_coordinate_bound_are_both_preserved() -> None:
    """
    Match the analytic projection onto x+y<=1.5with nonnegative coordinates.
    """
    result = constrained_step(
        [(1.0, 0.0), (0.0, 1.0)],
        (-2.0, -3.0),
        0.001,
        [(-1.0,), (-1.0,)],
        (1.5,),
        (0.0, 0.0),
        (0.0, 0.0),
        (10.0, 10.0),
    )
    x, y = result.values
    assert x + y == pytest.approx(1.5)
    assert y - x == pytest.approx(1 / 1.001)
    assert min(x, y) >= 0


def test_infeasible_origin_rejects_before_linear_solves() -> None:
    """
    Do not silently repair a negative geometric slack to initialize the subproblem.
    """
    with pytest.raises(ValueError, match="feasible origin"):
        constrained_step([(1.0,)], (-1.0,), 0.1, [(1.0,)], (-0.01,), (0,), (-1,), (1,))


def test_numerical_stop_retains_feasible_prefix_and_explicit_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Expose a failed linear solve without inventing a downhill or feasible route.
    """

    def singular(matrix: list[list[float]], right: list[float]) -> list[float]:
        """
        Simulate the documented small-system numerical rejection boundary.
        """
        assert matrix and right
        raise ValueError("singular")

    monkeypatch.setattr(
        "experiments.experiment_ribbon_cap_transition.director_constrained_step._solve", singular
    )
    result = constrained_step([(1.0,)], (-1.0,), 0.1, [()], (), (0,), (-1,), (1,))
    assert result.values == (0.0,)
    assert result.status == "numerical KKT stop"


def test_twelve_coordinate_steps_preserve_bounds_and_larger_systems_reject() -> None:
    """
    Support two optional terminal controls while retaining an explicit dimension cap.
    """
    columns = [tuple(float(i == j) for j in range(12)) for i in range(12)]
    result = constrained_step(
        columns,
        (-2.0,) * 12,
        0.001,
        [()] * 12,
        (),
        (0.0,) * 12,
        (-1.0,) * 12,
        (1.0,) * 12,
    )
    assert result.values == pytest.approx((1.0,) * 12)
    assert result.iterations <= 32
    with pytest.raises(ValueError):
        constrained_step(
            columns + [(0.0,) * 12],
            (-2.0,) * 12,
            0.001,
            [()] * 13,
            (),
            (0.0,) * 13,
            (-1.0,) * 13,
            (1.0,) * 13,
        )
