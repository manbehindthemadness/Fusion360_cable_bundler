"""
Measure bank-zero change points without restricting successful crossings or nonzero bank signs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from experiments.experiment_ribbon_bend_relocation.model import MovableBends

from .projection_system import CoordinateBounds


@dataclass(frozen=True)
class BankEvent:
    """
    Identify the first bank zero on one existing bounded correction ray.
    """

    fraction: float
    indices: frozenset[int]

    @classmethod
    def first(
        cls,
        values: tuple[float, ...],
        delta: tuple[float, ...],
        indices: Iterable[int],
        maximum: float,
    ) -> BankEvent | None:
        """
        Retain only positive crossings reached by the original proposed trial.
        """
        first = maximum
        selected: set[int] = set()
        for index in indices:
            value, change = values[index], delta[index]
            if (value > 0.0 and change < 0.0) or (value < 0.0 and change > 0.0):
                fraction = -value / change
                if 0.0 < fraction <= first:
                    if fraction < first:
                        selected.clear()
                    first = fraction
                    selected.add(index)
        return cls(first, frozenset(selected)) if selected else None

    def coordinates(self, trial: tuple[float, ...], fraction: float) -> tuple[float, ...]:
        """
        Evaluate a known bank-zero event exactly instead of retaining cancellation roundoff.

        Other trial fractions and coordinates are unchanged. This computes the
        mathematical event point on the existing ray; it does not snap a cap,
        delete material or round a nearby arbitrary bank into another branch.
        """
        if fraction != self.fraction:
            return trial
        return tuple(0.0 if i in self.indices else value for i, value in enumerate(trial))


@dataclass(frozen=True)
class ZeroBanks:
    """
    Match derivative and projector sides only for banks currently at exact zero.

    Nonzero banks retain their full original domains. This local numerical
    branch choice is discarded after the update, with no physical authority.
    """

    source: CoordinateBounds
    positive: frozenset[int]
    negative: frozenset[int]

    @classmethod
    def at(
        cls,
        model: MovableBends,
        values: tuple[float, ...],
        score: Callable[[tuple[float, ...]], float],
        admissible: Callable[[tuple[float, ...]], bool],
        checkpoint: Callable[[], None],
    ) -> ZeroBanks | None:
        """
        Compare admissible original finite endpoints at zero before the one linear projection.

        A tie keeps the ordinary positive preference. Endpoint measurements
        share the caller's equation cache and resource allocation; neither is
        accepted geometry, and a declined projection never tries another side.
        """
        positive, negative = set(), set()
        for index, full_index in enumerate(model.indices):
            if full_index % 4 != 2 or values[index] != 0.0:
                continue
            low, high = model.bounds(index)
            options = []
            for endpoint in (min(high, 1e-5), max(low, -1e-5)):
                if endpoint == 0.0:
                    continue
                checkpoint()
                probe = list(values)
                probe[index] = endpoint
                trial = tuple(probe)
                if admissible(trial):
                    options.append((score(trial), endpoint))
            if not options:
                raise ArithmeticError("Zero bank has no admissible finite endpoint")
            value = min(options, key=lambda option: option[0])[1]
            (positive if value > 0.0 else negative).add(index)
        return (
            cls(model, frozenset(positive), frozenset(negative)) if positive or negative else None
        )

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Keep original bounds except for the chosen outgoing side at exact bank zeros.
        """
        low, high = self.source.bounds(index)
        if index in self.positive:
            low = max(low, 0.0)
        elif index in self.negative:
            high = min(high, 0.0)
        return low, high
