"""
Reuse exact affine bases across native cone faces without reusing candidate decisions.
"""

from __future__ import annotations

import random
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_reduction import closure
from experiments.experiment_ribbon_bend_reduction.closure import AffineWorkspace
from experiments.experiment_ribbon_feature_insertion import native_cone
from experiments.experiment_ribbon_feature_insertion.linear_fit import least_squares


def _uncached(
    hard: list[list[float]],
    right: list[float],
    objective: list[list[float]],
    wanted: list[float],
    size: int,
    *,
    maximum_sum: float | None = None,
    workspace: AffineWorkspace | None = None,
) -> list[float] | None:
    """
    Supply the original independent affine projections to the unchanged native-face loop.
    """
    del workspace
    return least_squares(hard, right, objective, wanted, size, maximum_sum=maximum_sum)


@pytest.mark.parametrize("size", (0, 1, 2, 3))
def test_native_faces_match_uncached_bits_and_checkpoint_counts(
    size: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Compare 80 algebraic systems per size, including rank and budget-face failures.

    Randomness authors linear matrices only, never saved layouts or route seeds.
    One bounded workspace sees changing rows, right sides, minima and budgets.
    """
    randomizer = random.Random(2256 + size)
    workspace = AffineWorkspace()
    for index in range(80):
        rows = [[randomizer.uniform(-2, 2) for _ in range(size)] for _ in range(3)]
        if size > 1 and index % 3 == 0:
            for row in rows:
                row[-1] = row[0] * (1.0 if index % 2 else 1.0 + 1e-12)
        wanted = [randomizer.uniform(-3, 3) for _ in range(3)]
        minimum = (1e-8, 0.2, 4.0)[index % 3]
        budget = (None, minimum * size * 0.9, minimum * size * 1.2, 5.0)[index % 4]
        old_checkpoint, new_checkpoint = Mock(), Mock()
        with monkeypatch.context() as old:
            old.setitem(vars(native_cone), "least_squares", _uncached)
            expected = native_cone.project(rows, wanted, size, minimum, budget, old_checkpoint)
        actual = native_cone.project(
            rows, wanted, size, minimum, budget, new_checkpoint, workspace=workspace
        )
        assert new_checkpoint.call_count == old_checkpoint.call_count
        if expected is None:
            assert actual is None
            continue
        assert actual is not None
        assert [float(v).hex() for v in actual] == [float(v).hex() for v in expected]


def test_pinned_faces_omit_repeated_basis_builds_but_keep_every_face(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Observe actual two-pass basis work on a known native-lower-face optimum.
    """
    append = Mock(wraps=closure._append_basis)
    monkeypatch.setattr(closure, "_append_basis", append)
    checkpoints = []
    outputs = []
    work = []
    for reuse in (False, True):
        append.reset_mock()
        checkpoint = Mock()
        with monkeypatch.context() as variant:
            if not reuse:
                variant.setitem(vars(native_cone), "least_squares", _uncached)
            outputs.append(
                native_cone.project([[1, 0], [0, 1]], [-0.1, 1], 2, 0.2, None, checkpoint)
            )
        checkpoints.append(checkpoint.call_count)
        work.append(append.call_count)
    assert outputs == [[0.2, 1.0], [0.2, 1.0]]
    assert checkpoints[0] == checkpoints[1] == 4
    assert work[1] < work[0]
