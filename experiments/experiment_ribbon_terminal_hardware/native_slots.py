"""
Select one native-valid positive or zero slot face for the existing second linear projection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from experiments.experiment_ribbon_fold_route.native_length import minimum_coordinate as _minimum

from .active_projection import CoordinateBounds
from .redistributed_projection import GuidancePolicy, strict_descent


def zero_step(
    values: tuple[float, ...],
    candidates: frozenset[int],
    delta: tuple[float, ...],
    jacobian: list[list[float]],
    residual: tuple[float, ...],
    guidance_policy: GuidancePolicy,
) -> tuple[float, ...] | None:
    """
    Choose original zero faces only when retained affine data still proves strict descent.

    The caller supplies its existing sub-native slot candidates. Only exact-zero
    source slots can stay absent; positive material is never deleted. Replace
    their proposed increments by zero, then apply the projector's unchanged
    predicted constraint/descent gate. Failure retains ordinary positive-floor
    selection. This selects the same one replacement projection and spends no
    additional solve, derivative, geometry trial or working-set allowance.
    """
    if (
        len(values) != len(delta)
        or len(jacobian) != len(residual)
        or any(len(row) != len(values) for row in jacobian)
        or any(type(i) is not int or not 0 <= i < len(values) for i in candidates)
        or any(not math.isfinite(term) for term in values + delta)
        or any(not math.isfinite(term) for row in jacobian for term in row)
        or any(not math.isfinite(term) for term in residual)
    ):
        raise ValueError("Use complete finite coordinates and matching retained linear equations")
    absent = frozenset(i for i in candidates if values[i] == 0)
    if not any(delta[i] > 0 for i in absent):
        return None
    selected = tuple(0.0 if i in absent else change for i, change in enumerate(delta))
    predicted = tuple(
        term + math.fsum(a * b for a, b in zip(row, selected))
        for row, term in zip(jacobian, residual)
    )
    return selected if strict_descent(residual, predicted, guidance_policy) else None


def extensions(
    source: CoordinateBounds,
    values: tuple[float, ...],
    candidates: frozenset[int],
    minimum_mm: float,
    scale: float,
) -> dict[int, float] | None:
    """
    Pin existing positive sub-native slots just above the unchanged native minimum.

    This substitutes for deleting those slots during the existing reclosure
    action. It does not close caps, move targets or certify physical geometry.
    All chosen floors must fit the original coordinate box. The caller retains
    these values through the same remaining Newton/physical proof allocation.
    """
    minimum = _minimum(minimum_mm, scale)
    if any(
        type(index) is not int
        or not 0 <= index < len(values)
        or not math.isfinite(values[index])
        or not 0 < values[index] * scale <= minimum_mm
        for index in candidates
    ):
        raise ValueError("Extend only existing finite positive sub-native slots")
    if minimum is None or any(
        not source.bounds(index)[0] <= minimum <= source.bounds(index)[1] for index in candidates
    ):
        return None
    return dict.fromkeys(sorted(candidates), minimum)


@dataclass(frozen=True)
class NativeSlots(CoordinateBounds):
    """
    Bind positive native floors and exact-zero faces without changing other coordinate bounds.
    """

    source: CoordinateBounds
    positive: frozenset[int]
    frozen: frozenset[int]
    minimum: float

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Keep the original upper limit, activating only selected tiny positive slot directions.
        """
        low, high = self.source.bounds(index)
        if index in self.positive:
            low = max(low, self.minimum)
        if index in self.frozen:
            high = min(high, 0.0)
        return low, high


def bind(
    source: CoordinateBounds,
    candidates: frozenset[int],
    delta: tuple[float, ...],
    minimum_mm: float,
    scale: float,
) -> NativeSlots | None:
    """
    Replace forced-zero cleanup with one valid positive face for necessary positive directions.

    The caller supplies only original zero slots whose first projected motion
    would remain at or below the strict native minimum. Positive directions
    select a representable floor just beyond the native minimum; exact-zero or
    outward directions remain frozen. This chooses one second projection, never
    another mask, working-set allowance or geometry candidate. A floor outside
    original upper bounds declines. Final nonlinear/native checks remain strict.
    """
    if (
        not math.isfinite(minimum_mm)
        or minimum_mm <= 0
        or not math.isfinite(scale)
        or scale <= 0
        or any(type(index) is not int or not 0 <= index < len(delta) for index in candidates)
        or any(not math.isfinite(value) for value in delta)
    ):
        raise ValueError("Use finite positive native dimensions and existing slot directions")
    minimum = _minimum(minimum_mm, scale)
    if minimum is None:
        return None
    positive = frozenset(index for index in candidates if delta[index] > 0)
    if any(source.bounds(index)[1] < minimum for index in positive):
        return None
    return NativeSlots(source, positive, candidates - positive, minimum)


def bind_proposal(
    source: CoordinateBounds,
    values: tuple[float, ...],
    candidates: frozenset[int],
    delta: tuple[float, ...],
    minimum_mm: float,
    scale: float,
) -> NativeSlots | None:
    """
    Select the existing positive or zero face from proposed slot coordinates, not increment signs.

    An already positive slot can contract toward a sub-native positive length.
    Its negative increment must not freeze that remaining material at zero.
    Bind the same representable floor and original upper bounds through the
    existing face selector, without another projection or geometry evaluation.
    """
    if len(values) != len(delta) or any(not math.isfinite(value) for value in values):
        raise ValueError("Use complete finite current and proposed slot coordinates")
    targets = tuple(value + change for value, change in zip(values, delta))
    return bind(source, candidates, targets, minimum_mm, scale)
