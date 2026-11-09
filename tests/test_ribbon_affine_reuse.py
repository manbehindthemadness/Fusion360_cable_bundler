"""
Preserve exact ordered affine projection across bounded prefix reuse and active coordinate subsets.
"""

from __future__ import annotations

import pytest

from experiments.experiment_ribbon_bend_reduction.closure import AffineWorkspace, affine_projection


@pytest.mark.parametrize(
    ("rows", "right", "reference", "expected"),
    (
        ([[1.0, 0.0], [0.0, 1.0]], [2.0, 3.0], [10.0, -5.0], [2.0, 3.0]),
        ([[1.0, 0.0], [1.0, 0.0]], [2.0, 2.0], [0.0, 5.0], [2.0, 5.0]),
        ([[1.0, 0.0], [1.0, 0.0]], [2.0, 3.0], [0.0, 5.0], None),
        ([], [], [1.0, -2.0], [1.0, -2.0]),
    ),
)
def test_affine_reuse_preserves_projection_and_dependent_row_oracles(
    rows: list[list[float]],
    right: list[float],
    reference: list[float],
    expected: list[float] | None,
) -> None:
    """
    Preserve independent solutions, unchanged nullspace coordinates and exact inconsistent-row rejection.
    """
    workspace = AffineWorkspace()
    assert workspace.project(rows, right, reference) == expected
    assert affine_projection(rows, right, reference) == expected


def test_every_scalar_subset_matches_the_uncached_ordered_projection_exactly() -> None:
    """
    Reuse the six common cap rows across the same sixteen subsets without changing any result bits.
    """
    caps = [[float(i == j) for j in range(7)] for i in range(6)]
    limits = [[float(i == j) + 0.25 for j in range(7)] for i in range(4)]
    right = [0.1 * (i + 1) for i in range(10)]
    reference = [-0.25] * 7
    workspace = AffineWorkspace()
    for mask in range(16):
        active = [i for i in range(4) if mask & (1 << i)]
        rows = caps + [limits[i] for i in active]
        targets = right[:6] + [right[6 + i] for i in active]
        assert workspace.project(rows, targets, reference) == affine_projection(
            rows, targets, reference
        )


def test_matrix_snapshots_and_reference_changes_cannot_mutate_cached_bases() -> None:
    """
    Recompute changed right sides while keeping cached input and returned vectors privately immutable.
    """
    workspace = AffineWorkspace()
    rows, right = [[1.0, 0.0]], [2.0]
    answer = workspace.project(rows, right, [0.0, 3.0])
    assert answer is not None
    assert answer == [2.0, 3.0]
    answer[0] = 999
    rows[0][0], right[0] = 2.0, 8.0
    assert workspace.project(rows, right, [0.0, 3.0]) == [4.0, 3.0]
    assert workspace.project([[1.0, 0.0]], [2.0], [5.0, 6.0]) == [2.0, 6.0]
    for i in range(70):
        target = float(i)
        assert workspace.project([[1.0, 0.0]], [target], [0.0, 1.0]) == [target, 1.0]
    assert workspace.project([[1.0, 0.0]], [2.0], [0.0, 3.0]) == [2.0, 3.0]


@pytest.mark.parametrize(
    ("rows", "right", "reference"),
    (([[1.0]], [], [0.0]), ([[1.0, 2.0]], [1.0], [0.0])),
)
def test_affine_workspace_rejects_mismatched_matrix_contracts(
    rows: list[list[float]],
    right: list[float],
    reference: list[float],
) -> None:
    """
    Reject malformed matrix snapshots before a partial prefix can be treated as a valid solution.
    """
    with pytest.raises(ValueError, match="matching rows"):
        AffineWorkspace().project(rows, right, reference)
