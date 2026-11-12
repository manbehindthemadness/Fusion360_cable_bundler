"""
Share bounded finite-difference derivatives for the same constrained joint coordinates.
"""

from __future__ import annotations

from enum import Enum
from typing import AbstractSet, Callable

from experiments.experiment_ribbon_bend_relocation.model import MovableBends


class Difference(Enum):
    """
    Select centered probes or one admissible endpoint relative to the exact current equations.
    """

    CENTRAL = "central"
    ONE_SIDED = "one_sided_reference"


def jacobian(
    model: MovableBends,
    values: tuple[float, ...],
    evaluate: Callable[[tuple[float, ...]], tuple[float, ...]],
    row_count: int,
    fixed: AbstractSet[int],
    checkpoint: Callable[[], None],
    *,
    admissible: Callable[[tuple[float, ...]], bool] | None = None,
    difference: Difference = Difference.CENTRAL,
) -> list[list[float]]:
    """
    Preserve1e-5coordinate probes, bound clipping and exact zero columns for fixed native slots.

    Differentiate the raw equations supplied by the caller, including active
    inequalities. The caller retains ownership of all CPU/update allocations.
    With a supplied material domain, replace an inadmissible endpoint probe by
    the current valid base coordinate. This gives a one-sided derivative without
    extra equation evaluations or altered geometry. Hard caller errors propagate.

    Explicit one-sided mode reuses current equations and prefers the positive
    original endpoint, using the negative endpoint only when bounds or material
    admissibility prevent it. This numerical guidance has first-order truncation
    error; actual nonlinear descent and every final physical check remain the
    caller's responsibility. It never reuses a prior pose's Jacobian.
    """
    if not isinstance(difference, Difference):
        raise ValueError("Choose an explicit finite-difference scheme")
    if admissible is not None:
        checkpoint()
        if not admissible(values):
            raise ArithmeticError("Joint derivative base is outside its material domain")
    base = evaluate(values) if difference is Difference.ONE_SIDED else None
    if difference is Difference.ONE_SIDED and (base is None or len(base) != row_count):
        raise ArithmeticError("Joint derivative base changed its finite equation contract")
    columns = []
    for index, value in enumerate(values):
        checkpoint()
        if index in fixed:
            columns.append([0.0] * row_count)
            continue
        low, high = model.bounds(index)
        a, b = list(values), list(values)
        a[index], b[index] = max(low, value - 1e-5), min(high, value + 1e-5)
        if base is not None:
            probe = b
            if probe[index] == value or (admissible is not None and not admissible(tuple(probe))):
                probe = a
                if probe[index] == value or (
                    admissible is not None and not admissible(tuple(probe))
                ):
                    raise ArithmeticError("Joint derivative has no admissible finite endpoint")
            sample = evaluate(tuple(probe))
            if len(sample) != row_count:
                raise ArithmeticError("Joint derivative changed its finite equation contract")
            columns.append([(y - x) / (probe[index] - value) for x, y in zip(base, sample)])
            continue
        if admissible is not None:
            for probe in (a, b):
                if not admissible(tuple(probe)):
                    probe[index] = value
        first, last = evaluate(tuple(a)), evaluate(tuple(b))
        if len(first) != row_count or len(last) != row_count or a[index] == b[index]:
            raise ArithmeticError(
                "Constrained joint derivative changed its finite equation contract"
            )
        columns.append([(y - x) / (b[index] - a[index]) for x, y in zip(first, last)])
    return [[column[row] for column in columns] for row in range(row_count)]
