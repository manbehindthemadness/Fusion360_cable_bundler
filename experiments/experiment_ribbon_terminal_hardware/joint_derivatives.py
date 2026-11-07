"""
Share bounded finite-difference derivatives for the same constrained joint coordinates.
"""

from __future__ import annotations

from typing import AbstractSet, Callable

from experiments.experiment_ribbon_bend_relocation.model import MovableBends


def jacobian(
    model: MovableBends,
    values: tuple[float, ...],
    evaluate: Callable[[tuple[float, ...]], tuple[float, ...]],
    row_count: int,
    fixed: AbstractSet[int],
    checkpoint: Callable[[], None],
) -> list[list[float]]:
    """
    Preserve1e-5coordinate probes, bound clipping and exact zero columns for fixed native slots.

    Differentiate the raw equations supplied by the caller, including active
    inequalities. The caller retains ownership of all CPU/update allocations.
    """
    columns = []
    for index, value in enumerate(values):
        checkpoint()
        if index in fixed:
            columns.append([0.0] * row_count)
            continue
        low, high = model.bounds(index)
        a, b = list(values), list(values)
        a[index], b[index] = max(low, value - 1e-5), min(high, value + 1e-5)
        first, last = evaluate(tuple(a)), evaluate(tuple(b))
        if len(first) != row_count or len(last) != row_count or a[index] == b[index]:
            raise ArithmeticError(
                "Constrained joint derivative changed its finite equation contract"
            )
        columns.append([(y - x) / (b[index] - a[index]) for x, y in zip(first, last)])
    return [[column[row] for column in columns] for row in range(row_count)]
