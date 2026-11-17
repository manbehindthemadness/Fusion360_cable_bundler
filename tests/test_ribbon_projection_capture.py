"""
Check passive forwarding and independent algebraic certificates before diagnostic execution.
"""

from __future__ import annotations

from typing import Any

import pytest

from artifacts.verification.resume3370.capture import installed
from artifacts.verification.resume3370.prototype import build, coefficients
from experiments.experiment_ribbon_terminal_hardware import (
    active_projection,
    redistributed_projection,
)


class Bounds:
    """
    Supply an unbounded synthetic domain with no physical geometry claim.
    """

    def __init__(self) -> None:
        """
        Supply the twenty coordinates used by the analytical certificate.
        """
        self.domains = [(-float("inf"), float("inf"))] * 20

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Exclude coordinate faces from the independent analytical certificates.
        """
        return self.domains[index]


def checkpoint() -> None:
    """
    Supply a no-op only for these tiny synthetic unit systems.
    """


def test_fourteen_active_rows_exact_optimum() -> None:
    """
    Check the complete independent optimum rather than mirroring implementation steps.
    """
    values = (0.0,) * 20
    rows = [[float(i == j) * (1 if i < 6 else -1) for j in range(20)] for i in range(20)]
    residual = (0.0,) * 6 + (1.0,) * 14
    with pytest.raises(ValueError):
        active_projection.active_step(Bounds(), values, rows, residual, checkpoint)
    step = build()(Bounds(), values, rows, residual, checkpoint)
    assert step == (0.0,) * 6 + (1.0,) * 14
    assert sum(value * value for value in step) / 2 == 7.0


def test_row_basis_preserves_near_independent_direction() -> None:
    """
    A resolvable row direction must survive conditioning lost by squaring the matrix.
    """
    assert coefficients([[1.0, 0.0], [1.0, 1e-7]], [0.0, 1.0]) == pytest.approx([-1e7, 1e7])
    assert coefficients([[1.0, 0.0], [2.0, 0.0]], [0.0, 1.0]) is None


def test_capture_restores_and_preserves_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    An interrupted backend keeps its captured prefix and never leaks the observer.
    """
    marker = RuntimeError("bounded stop")

    def stopped(*args: Any, **kwargs: Any) -> None:
        """
        Represent a cancellation propagated by the real numerical backend.
        """
        assert args[1:4] == ((0.0,), [[1.0]], (0.0,))
        assert kwargs == {}
        raise marker

    monkeypatch.setitem(vars(redistributed_projection), "active_step", stopped)
    records: list[dict[str, Any]] = []
    timing = [0.0]
    with pytest.raises(RuntimeError) as caught, installed(records, timing):
        redistributed_projection.active_step(Bounds(), (0.0,), [[1.0]], (0.0,), checkpoint)
    assert caught.value is marker
    assert redistributed_projection.active_step is stopped
    assert records[0]["status"] == "raised"
    assert records[0]["jacobian"] == [[1.0]]
