"""
Supply coordinate operations to the shared bounded endpoint fitter.
"""

from __future__ import annotations

from typing import Callable, Protocol

from experiments.experiment_ribbon_cap_transition.compatible_coordinates import (
    probe_coordinates,
    trial_coordinates,
)
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from . import broad_chart


class FitChart(Protocol):
    """
    Keep transport, bounds and finite differences in the same coordinate chart.
    """

    def bounds(self, case: EndpointCase) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """
        Return one lower and upper bound for every fitted coordinate.
        """
        ...

    def probe(self, case: EndpointCase, values: tuple[float, ...], index: int) -> tuple[float, ...]:
        """
        Return a bounded nonzero finite-difference probe for one coordinate.
        """
        ...

    def trial(
        self,
        case: EndpointCase,
        values: tuple[float, ...],
        delta: tuple[float, ...],
        fraction: float,
    ) -> tuple[float, ...]:
        """
        Apply a bounded trial with the chart's registered step norm.
        """
        ...

    def integrate(
        self,
        case: EndpointCase,
        values: tuple[float, ...],
        steps: int,
        checkpoint: Callable[[], None],
    ) -> CompatiblePath:
        """
        Transport the same field used by probes and accepted trials.
        """
        ...


class BroadFitChart:
    """
    Preserve the original ten-coordinate operations and arithmetic exactly.
    """

    @staticmethod
    def bounds(case: EndpointCase) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """
        Retain the historical broad search box.
        """
        return broad_chart.bounds(case)

    @staticmethod
    def probe(case: EndpointCase, values: tuple[float, ...], index: int) -> tuple[float, ...]:
        """
        Delegate to the historical signed finite difference.
        """
        _, proposed = probe_coordinates(values, index, broad_chart.carrier_maximum(case))
        return proposed

    @staticmethod
    def trial(
        case: EndpointCase, values: tuple[float, ...], delta: tuple[float, ...], fraction: float
    ) -> tuple[float, ...]:
        """
        Retain the historical bounded full or half step.
        """
        _, proposed = trial_coordinates(values, delta, fraction, broad_chart.carrier_maximum(case))
        return proposed

    @staticmethod
    def integrate(
        case: EndpointCase,
        values: tuple[float, ...],
        steps: int,
        checkpoint: Callable[[], None],
    ) -> CompatiblePath:
        """
        Retain the historical near-limit transport.
        """
        return broad_chart.integrate(case, values, steps, checkpoint)
