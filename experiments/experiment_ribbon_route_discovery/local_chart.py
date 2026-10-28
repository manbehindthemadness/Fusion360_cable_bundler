"""
Overlay four smooth material intervals on a frozen compatible route.

The intervals are numerical basis supports, not physical ribbon segments. Local
ruling changes can trigger whole-field normalization to preserve material bounds.
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
from experiments.experiment_ribbon_cap_transition.director_routing_field import RoutingField
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from . import broad_chart

DERIVATIVE_BOUND = 768 / (25 * math.sqrt(5))


def bump(u: float) -> tuple[int, float, float]:
    """
    Return the active quarter and a C2 compact bump with its exact derivative.
    """
    if not math.isfinite(u) or not 0 <= u <= 1:
        raise ValueError("Material fraction must lie in [0,1].")
    index = min(int(4 * u), 3)
    t = 4 * u - index
    return index, 64 * t**3 * (1 - t) ** 3, 768 * t**2 * (1 - t) ** 2 * (1 - 2 * t)


@dataclass(frozen=True)
class LocalRaw(RoutingField):
    """
    Add compact bending and ruling coordinates to a normalized frozen raw field.
    """

    local_bending: tuple[float, ...] = (0.0,) * 4
    local_ruling: tuple[float, ...] = (0.0,) * 4

    def __post_init__(self) -> None:
        """
        Reject malformed local coefficients before field evaluation.
        """
        super().__post_init__()
        if any(len(values) != 4 for values in (self.local_bending, self.local_ruling)) or not all(
            math.isfinite(value) for value in (*self.local_bending, *self.local_ruling)
        ):
            raise ValueError("Four finite coefficients are required per local field.")

    def sample(self, u: float) -> tuple[float, float, float]:
        """
        Preserve zero terminal ruling and differentiable joins without mesh repair.
        """
        curvature, eta, gradient = super().sample(u)
        index, value, derivative = bump(u)
        return (
            curvature + self.local_bending[index] * value / self.length_mm,
            eta + self.local_ruling[index] * value,
            gradient + self.local_ruling[index] * derivative / self.length_mm,
        )


@dataclass(frozen=True)
class LocalField(CompatibleField):
    """
    Retain original progress and turn limits with an analytic local derivative bound.
    """

    raw: LocalRaw

    def __post_init__(self) -> None:
        """
        Rescale only when the complete analytic bound exhausts available progress.

        Disjoint supports require the maximum local derivative bound, not its sum.
        The inward margin keeps J strictly above .1 even at rounded saturation.
        """
        _, b, c, d = self.raw.ruling
        bound = 2 * math.pi * (abs(b) + abs(c) + 2 * abs(d) + 2 * abs(self.raw.extra_ruling))
        bound += DERIVATIVE_BOUND * max(abs(value) for value in self.raw.local_ruling)
        allowed = 0.9 * self.carrier_length_mm / (1.9 * self.half_width_mm)
        scale = min(1.0, allowed * (1 - 1e-12) / bound) if bound else 1.0
        object.__setattr__(self, "ruling_scale", scale)


def bounds(case: EndpointCase) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """
    Bound eight local coefficients and one carrier ratio independently of case ID.
    """
    return (
        (-4 * math.pi,) * 4 + (-3.0,) * 4 + (1.0,),
        (4 * math.pi,) * 4 + (3.0,) * 4 + (broad_chart.carrier_maximum(case),),
    )


def integrate(
    case: EndpointCase,
    base: tuple[float, ...],
    values: tuple[float, ...],
    steps: int,
    checkpoint: Callable[[], None],
) -> CompatiblePath:
    """
    Transport local corrections without changing targets, material order or bend rules.

    Zero corrections replay the original chart exactly. Nonzero corrections keep
    its Fourier shape frozen while allowing local bend/ruling and carrier changes.
    """
    lower, upper = bounds(case)
    if (
        len(base) != 10
        or len(values) != 9
        or any(not math.isfinite(v) or not lo <= v <= hi for v, lo, hi in zip(values, lower, upper))
    ):
        raise ValueError("Local coordinates exceed their nine-dimensional domain.")
    if not any(values[:8]):
        return broad_chart.integrate(case, base[:9] + (values[8],), steps, checkpoint)
    lo, hi = broad_chart.bounds(case)
    if any(not math.isfinite(v) or not a <= v <= b for v, a, b in zip(base, lo, hi)):
        raise ValueError("Frozen base exceeds the original chart bounds.")
    original = RoutingField(
        case.name,
        magnitude(difference(case.end, case.start)) * values[8],
        base[:4],
        (base[5], -base[5], base[6], base[7]),
        case.lines,
        case.diameter_mm,
        base[4],
        base[8],
    )
    scale = CompatibleField(original, BendMapping.NEAR_LIMIT).ruling_scale
    raw = LocalRaw(
        original.name,
        original.length_mm,
        original.bending,
        tuple(v * scale for v in original.ruling),
        original.lines,
        original.diameter_mm,
        original.extra_bending,
        original.extra_ruling * scale,
        values[:4],
        values[4:8],
    )
    return integrate_compatible(
        LocalField(raw, BendMapping.NEAR_LIMIT),
        steps,
        checkpoint,
        initial=tuple(
            v for p in (case.start, case.start_tangent, case.start_width) for v in (p.x, p.y, p.z)
        ),
    )
