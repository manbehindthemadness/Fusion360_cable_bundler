"""
Check feasible-prefix linear optimization independently of any recorded ribbon or endpoint seed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_terminal_hardware import primal_projection as primal
from experiments.experiment_ribbon_terminal_hardware.projection_system import (
    CoordinateBounds,
    ProjectionSystem,
)


@dataclass(frozen=True)
class _Bounds(CoordinateBounds):
    """
    Supply explicit analytical coordinate domains independent of ribbon geometry.
    """

    pairs: tuple[tuple[float, float], ...]

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Return the indexed unchanged absolute coordinate bounds.
        """
        return self.pairs[index]


def _rows(size: int, *physical: list[float]) -> list[list[float]]:
    """
    Keep six unconstrained cap equations before the supplied physical halfspaces.
    """
    return [[0.0] * size for _ in range(6)] + list(physical)


@pytest.mark.parametrize("scale", (1e-6, 1.0, 1e6))
@pytest.mark.parametrize("size", (2, 9, 31))
def test_scaled_physical_halfspace_preserves_caps_and_unused_coordinates(
    scale: float, size: int
) -> None:
    """
    Reach the analytical minimum without a coordinate-count cutoff or scale-specific rule.
    """
    rows = _rows(size, [-scale] + [0.0] * (size - 1))
    residual = (0.0,) * 6 + (scale,)
    result = primal.project(
        _Bounds(((-math.inf, math.inf),) * size),
        (0.0,) * size,
        rows,
        residual,
        (2.0,) + (1.0,) * (size - 1),
        lambda: None,
    )
    assert result.stop is primal.Stop.STATIONARY and result.updates <= 16
    assert result.step == pytest.approx((1.0,) + (0.0,) * (size - 1), abs=1e-12)
    assert (
        result.step is not None
        and residual[6] + math.fsum(a * b for a, b in zip(rows[6], result.step)) <= 1e-14
    )


def test_redundant_caps_and_physical_rows_remain_present_in_final_constraints() -> None:
    """
    Rank-dependent equalities and duplicate halfspaces do not exempt an occupied direction.
    """
    rows = [[1.0, -1.0], [2.0, -2.0]] + [[0.0, 0.0] for _ in range(4)]
    rows += [[-1.0, 0.0], [-2.0, 0.0], [0.0, -1.0]]
    residual = (0.0,) * 6 + (1.0, 2.0, 1.0)
    result = primal.project(
        _Bounds(((-5.0, 5.0),) * 2), (0.0, 0.0), rows, residual, (2.0, 2.0), lambda: None
    )
    assert result.step == pytest.approx((1.0, 1.0), abs=1e-12)
    assert result.stop is primal.Stop.STATIONARY
    assert result.step is not None
    predicted = [
        r + math.fsum(a * b for a, b in zip(row, result.step)) for row, r in zip(rows, residual)
    ]
    assert max(map(abs, predicted[:6])) <= 1e-8 and max(predicted[6:]) <= 1e-14


def test_absolute_coordinate_face_identity_is_only_reported_at_stationarity() -> None:
    """
    Respect nonzero current coordinates and return the actual selected lower face.
    """
    result = primal.project(
        _Bounds(((3.0, 5.0),)), (2.0,), _rows(1, [0.0]), (0.0,) * 6 + (-1.0,), (2.0,), lambda: None
    )
    assert result.step == (1.0,)
    assert (
        result.stop is primal.Stop.STATIONARY
        and result.lower == frozenset({0})
        and not result.upper
    )


@pytest.mark.parametrize("anchor", ((-1.0, 0.0), (6.0, 0.0)))
def test_bad_anchor_cannot_supply_an_incumbent(anchor: tuple[float, float]) -> None:
    """
    Decline physical or domain violations before any working-set update.
    """
    result = primal.project(
        _Bounds(((-5.0, 5.0),) * 2),
        (0.0, 0.0),
        _rows(2, [-1.0, 0.0]),
        (0.0,) * 6 + (1.0,),
        anchor,
        lambda: None,
    )
    assert result.step is None and result.stop is primal.Stop.INVALID_ANCHOR and result.updates == 0


def test_anchor_must_satisfy_caps_and_inconsistent_caps_do_not_invent_motion() -> None:
    """
    Keep actual original cap equations even when their nullspace rank is deficient.
    """
    rows = [[1.0], [1.0]] + [[0.0] for _ in range(5)]
    bounds = _Bounds(((-5.0, 5.0),))
    invalid = primal.project(bounds, (0.0,), rows, (0.0,) * 6 + (-1.0,), (1.0,), lambda: None)
    inconsistent = primal.project(
        bounds, (0.0,), rows, (0.0, 1.0) + (0.0,) * 4 + (-1.0,), (0.0,), lambda: None
    )
    assert invalid.step is None and invalid.stop is primal.Stop.INVALID_ANCHOR
    assert inconsistent.step is None and inconsistent.stop is primal.Stop.INCONSISTENT_SYSTEM


def test_update_limit_retains_a_checked_prefix_without_claiming_faces() -> None:
    """
    Crowded bound activation stops at sixteen updates, preserving feasibility without claiming completion.
    """
    size = 24
    result = primal.project(
        _Bounds(((1.0, math.inf),) * size),
        (0.0,) * size,
        _rows(size, [0.0] * size),
        (0.0,) * 6 + (-1.0,),
        (1.0,) * size,
        lambda: None,
    )
    assert result.step == (1.0,) * size
    assert result.stop is primal.Stop.UPDATE_LIMIT and result.updates == 16
    assert not result.lower and not result.upper


def test_failed_new_iterate_retains_only_its_checked_predecessor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    An infeasible proposal cannot displace the earlier feasible incumbent or manufacture active faces.
    """

    def invalid_advance(*_args: object) -> tuple[list[float], int | None]:
        """
        Model numerical feasibility loss without granting another optimizer attempt.
        """
        return [-4.0], 0

    monkeypatch.setattr(primal, "_advance", invalid_advance)
    result = primal.project(
        _Bounds(((-5.0, 5.0),)), (0.0,), _rows(1, [-1.0]), (0.0,) * 6 + (1.0,), (2.0,), lambda: None
    )
    assert result.step == (2.0,) and result.stop is primal.Stop.FEASIBILITY_DECLINE
    assert result.updates == 1 and not result.lower and not result.upper


def test_caller_cancellation_propagates_after_feasible_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Never return a retained prefix when the caller cancels a constraint traversal.
    """

    def cancelled(*_args: object) -> tuple[list[float], int | None]:
        """
        Raise the caller's resource error during a moving working-set operation.
        """
        raise TimeoutError("caller clock")

    monkeypatch.setattr(primal, "_advance", cancelled)
    with pytest.raises(TimeoutError, match="caller clock"):
        primal.project(
            _Bounds(((-5.0, 5.0),)),
            (0.0,),
            _rows(1, [-1.0]),
            (0.0,) * 6 + (1.0,),
            (2.0,),
            lambda: None,
        )


@pytest.mark.parametrize("slope", (-1.0, 0.0, 1e-14))
def test_nonblocking_rows_need_no_tangent_independence_work(
    monkeypatch: pytest.MonkeyPatch, slope: float
) -> None:
    """
    Keep each constraint checkpoint while omitting algebra that cannot limit this ray.
    """
    system = ProjectionSystem([0.0, 0.0], [([0.0, 1.0], 1.0, 1e-14)], [None])
    checkpoint = Mock()
    unused = Mock(side_effect=AssertionError("Nonblocking row needs no tangent remainder"))
    monkeypatch.setattr(primal, "_remainder", unused)
    motion, blocker = primal._advance(
        system, [0.0, 0.0], [0.0, slope], [], primal._Tangent([[1.0, 0.0]], [[1.0]]), checkpoint
    )
    assert motion == [0.0, slope] and blocker is None
    checkpoint.assert_called_once_with()
    unused.assert_not_called()


def test_positive_independent_blockers_keep_first_tie_and_exact_fraction() -> None:
    """
    Slope filtering cannot reorder equal limiting faces or relax their original halfspaces.
    """
    system = ProjectionSystem(
        [0.0, 0.0],
        [([0.0, -1.0], 1.0, 1e-14), ([0.0, 1.0], 0.25, 1e-14), ([0.0, 1.0], 0.25, 1e-14)],
        [None] * 3,
    )
    checkpoint = Mock()
    motion, blocker = primal._advance(
        system, [0.0, 0.0], [0.0, 1.0], [], primal._Tangent([[1.0, 0.0]], [[1.0]]), checkpoint
    )
    assert motion == [0.0, 0.25] and blocker == 1 and checkpoint.call_count == 3


@pytest.mark.parametrize("right", (1.0, 2.0))
def test_positive_nonlimiting_rows_need_no_tangent_independence_work(
    monkeypatch: pytest.MonkeyPatch, right: float
) -> None:
    """
    A boundary at or beyond the full ray cannot become its first blocking face.
    """
    system = ProjectionSystem([0.0, 0.0], [([0.0, 1.0], right, 1e-14)], [None])
    unused = Mock(side_effect=AssertionError("Nonlimiting ray needs no tangent remainder"))
    monkeypatch.setattr(primal, "_remainder", unused)
    checkpoint = Mock()
    motion, blocker = primal._advance(
        system, [0.0, 0.0], [0.0, 1.0], [], primal._Tangent([[1.0, 0.0]], [[1.0]]), checkpoint
    )
    assert motion == [0.0, 1.0] and blocker is None
    checkpoint.assert_called_once_with()
    unused.assert_not_called()


@pytest.mark.parametrize("dependent", (False, True))
@pytest.mark.parametrize("quantity", ("slope", "slack"))
def test_speculative_overflow_preserves_original_dependence_and_error_behavior(
    dependent: bool,
    quantity: str,
) -> None:
    """
    Finite extreme directions must not introduce errors on rows the old algorithm skipped.
    """
    normal = [math.sqrt(0.5), math.sqrt(0.5)]
    tangent = primal._Tangent([normal if dependent else [1.0, 0.0]], [[1.0]])
    system = ProjectionSystem([0.0, 0.0], [(normal, 1.0, 1e-14)], [None])
    direction = [1.5e308, 1.5e308] if quantity == "slope" else [1.0, 1.0]
    origin = [1.5e308, 1.5e308] if quantity == "slack" else [0.0, 0.0]
    if dependent:
        motion, blocker = primal._advance(system, origin, direction, [], tangent, lambda: None)
        assert motion == [a + b for a, b in zip(origin, direction)] and blocker is None
    else:
        with pytest.raises(OverflowError):
            primal._advance(system, origin, direction, [], tangent, lambda: None)


def test_cancellation_still_runs_for_each_nonblocking_row() -> None:
    """
    Skipped independence work grants no permission to skip cancellation or resource checks.
    """
    system = ProjectionSystem([0.0], [([-1.0], 1.0, 1e-14), ([-1.0], 2.0, 1e-14)], [None, None])
    checkpoint = Mock(side_effect=[None, TimeoutError("caller clock")])
    with pytest.raises(TimeoutError, match="caller clock"):
        primal._advance(system, [0.0], [1.0], [], primal._Tangent([], []), checkpoint)
    assert checkpoint.call_count == 2


@pytest.mark.parametrize("anchor", ((math.nan,), (math.inf,), ()))
def test_incomplete_or_nonfinite_anchor_is_an_input_error(anchor: tuple[float, ...]) -> None:
    """
    Malformed anchors cannot bypass the linear-system preparation contract.
    """
    with pytest.raises(ValueError, match="anchor"):
        primal.project(
            _Bounds(((-5.0, 5.0),)),
            (0.0,),
            _rows(1, [-1.0]),
            (0.0,) * 6 + (1.0,),
            anchor,
            lambda: None,
        )
