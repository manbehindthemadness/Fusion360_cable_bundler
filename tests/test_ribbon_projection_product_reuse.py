"""
Reuse only immutable constraint products within an original bounded algebraic projection.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_terminal_hardware import active_projection as active
from experiments.experiment_ribbon_terminal_hardware.projection_initialization import (
    Initialization,
    InitializationEvidence,
)
from tests.test_ribbon_native_slots import _Bounds
from tests.test_ribbon_projection_initialization import _Orthant


@pytest.mark.parametrize("count", (4, 10, 20))
@pytest.mark.parametrize("grouped", (False, True))
def test_immutable_products_preserve_every_projection_disposition(
    count: int, grouped: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Compare exact vectors and all receipts with uncached arithmetic on authored orthant equations.

    An empty initialization beyond sixteen coordinate faces remains exhausted;
    product reuse grants no seventeenth update. No saved ribbon geometry runs.
    """
    rows = [[-1.0] * count + [1.0]] + [[0.0] * (count + 1) for _ in range(6)]
    terms = (-1.0,) + (0.0,) * 5 + (-1.0,)
    mode = Initialization.COORDINATE_FACES if grouped else Initialization.EMPTY
    original_dot = vars(active)["_dot"]

    def run() -> tuple[Any, ...]:
        """
        Retain counters, vector, active identity and unsuccessful progress from one independent call.
        """
        dot = Mock(wraps=original_dot)
        monkeypatch.setitem(vars(active), "_dot", dot)
        check = Mock()
        unfinished = active.UnfinishedProjection()
        faces = active.ActiveFaces()
        seed = InitializationEvidence()
        result = active.active_step(
            _Orthant(False, count),
            (0.0,) * (count + 1),
            rows,
            terms,
            check,
            initialization=mode,
            initialization_evidence=seed,
            unfinished=unfinished,
            faces=faces,
        )
        return result, unfinished, faces, seed, check.call_count, dot.call_count

    cached = run()
    monkeypatch.setitem(vars(active), "lru_cache", lambda **kwargs: lambda function: function)
    uncached = run()
    assert cached[:-1] == uncached[:-1]
    if not grouped:
        assert cached[-1] < uncached[-1]
    if grouped or count < 16:
        assert cached[0] is not None
        assert max(abs(value) for value in cached[0][:-1]) < 1e-12
        assert cached[0][-1] == pytest.approx(1.0, abs=1e-12)
    else:
        assert cached[0] is None and cached[1].stop_reason == "working_set_limit"


def test_new_projection_never_reuses_prior_normals_or_bounds() -> None:
    """
    Changed independently authored equations receive fresh products, even with identical row indices.
    """
    results = []
    for coefficient, high in ((1.0, 10.0), (2.0, 10.0), (1.0, 0.1), (1.0, 10.0)):
        rows = [[0.0, 0.0] for _ in range(6)] + [[-coefficient, -1.0]]
        result = active.active_step(
            _Bounds(((0.0, high), (0.0, 10.0))), (0.0, 0.0), rows, (0.0,) * 6 + (1.0,), lambda: None
        )
        assert result is not None
        expected_x = min(high, coefficient / (1.0 + coefficient**2))
        assert result == pytest.approx((expected_x, 1.0 - coefficient * expected_x), abs=1e-12)
        results.append(result)
    assert results[0] == results[-1]
