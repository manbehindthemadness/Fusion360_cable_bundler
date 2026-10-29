"""
Fit independent terminal turn amplitudes alongside the original ten coordinates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import difference, magnitude
from experiments.experiment_ribbon_cap_transition.compatible_strip import (
    BendMapping,
    CompatibleField,
    CompatiblePath,
    integrate_compatible,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery import broad_chart

from .field import TangentTightening, TerminalRoutingField


@dataclass(frozen=True)
class TangentFitChart:
    """
    Append start then end amplitudes only for enabled terminal windows.

    Amplitudes use a +/-4pi raw search box, not a physical turn allowance. Original
    bend/ruling/carrier boxes, near-limit mapping and terminal target poses remain.
    Zero amplitudes replay the original field exactly, including its integration.
    """

    tightening: TangentTightening

    def lift(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Embed a finite original seed without silently discarding extra coordinates.
        """
        if len(values) != 10 or not all(math.isfinite(v) for v in values):
            raise ValueError("Tangent fitting needs ten finite original coordinates.")
        return values + (0.0,) * (self.tightening.dimensions - 10)

    def bounds(self, case: EndpointCase) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """
        Retain existing bounds and append one signed amplitude box per enabled end.
        """
        lower, upper = broad_chart.bounds(case)
        extras = self.tightening.dimensions - 10
        return lower + (-4 * math.pi,) * extras, upper + (4 * math.pi,) * extras

    def _validate(self, case: EndpointCase, values: tuple[float, ...]) -> None:
        """
        Refuse malformed or out-of-box inputs before sampling or transport.
        """
        lower, upper = self.bounds(case)
        if len(values) != len(lower) or any(
            not math.isfinite(v) or not lo <= v <= hi for lo, v, hi in zip(lower, values, upper)
        ):
            raise ValueError("Coordinates exceed the selected terminal fit chart.")

    def probe(self, case: EndpointCase, values: tuple[float, ...], index: int) -> tuple[float, ...]:
        """
        Use an inward 1e-5 difference at an upper bound, including terminal amplitudes.
        """
        self._validate(case, values)
        _, upper = self.bounds(case)
        if not 0 <= index < len(values):
            raise ValueError("Probe index lies outside the selected terminal fit chart.")
        proposed = list(values)
        proposed[index] += -1e-5 if values[index] >= upper[index] else 1e-5
        lower, upper = self.bounds(case)
        return tuple(min(hi, max(lo, v)) for lo, v, hi in zip(lower, proposed, upper))

    def trial(
        self,
        case: EndpointCase,
        values: tuple[float, ...],
        delta: tuple[float, ...],
        fraction: float,
    ) -> tuple[float, ...]:
        """
        Share the original 1.5 step-norm ceiling across every fitted coordinate.
        """
        self._validate(case, values)
        if (
            len(delta) != len(values)
            or not all(math.isfinite(v) for v in delta)
            or not math.isfinite(fraction)
            or not 0 < fraction <= 1
        ):
            raise ValueError("Terminal trials need finite matching steps and a fraction in (0,1].")
        scale = 1.5 / max(1.5, math.hypot(*delta))
        requested = tuple(a + fraction * scale * b for a, b in zip(values, delta))
        lower, upper = self.bounds(case)
        return tuple(min(hi, max(lo, v)) for lo, v, hi in zip(lower, requested, upper))

    def amplitudes(self, values: tuple[float, ...]) -> tuple[float, float]:
        """
        Decode independently enabled ends without shifting the original coordinates.
        """
        if len(values) != self.tightening.dimensions:
            raise ValueError("Coordinates disagree with the selected terminal windows.")
        index = 10
        start = values[index] if self.tightening.start_fraction else 0.0
        index += int(self.tightening.start_fraction > 0)
        end = values[index] if self.tightening.end_fraction else 0.0
        return start, end

    def integrate(
        self,
        case: EndpointCase,
        values: tuple[float, ...],
        steps: int,
        checkpoint: Callable[[], None],
    ) -> CompatiblePath:
        """
        Transport the requested local bends without moving targets or repairing closure.
        """
        self._validate(case, values)
        start, end = self.amplitudes(values)
        if start == end == 0:
            return broad_chart.integrate(case, values[:10], steps, checkpoint)
        raw = TerminalRoutingField(
            case.name,
            magnitude(difference(case.end, case.start)) * values[9],
            (values[0], values[1], values[2], values[3]),
            (values[5], -values[5], values[6], values[7]),
            case.lines,
            case.diameter_mm,
            values[4],
            values[8],
            self.tightening,
            start,
            end,
        )
        initial = tuple(
            value
            for vector in (case.start, case.start_tangent, case.start_width)
            for value in (vector.x, vector.y, vector.z)
        )
        return integrate_compatible(
            CompatibleField(raw, BendMapping.NEAR_LIMIT), steps, checkpoint, initial=initial
        )
