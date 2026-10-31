"""
Compare both edges of one developable material map at corresponding fractions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from cable_bundler.routing.geometry import Vector3, cross, difference, magnitude
from devtools.ribbon_analysis.edge_frames import ruling_kinematics
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_cap_transition.edge_first import BoundaryCurve, BoundaryFrame

from .geometry import EdgeChart


def _rows(u: float, degree: int) -> tuple[tuple[float, ...], ...]:
    """
    Evaluate Bernstein weights through fourth derivatives at one parameter fraction.
    """
    return tuple(
        tuple(
            math.comb(degree - order, i) * u**i * (1 - u) ** (degree - order - i)
            for i in range(degree - order + 1)
        )
        for order in range(5)
    )


@lru_cache(maxsize=4)
def _weights(stations: int, degree: int) -> tuple[tuple[tuple[float, ...], ...], ...]:
    """
    Cache bounded Bernstein evaluation weights through fourth derivatives.
    """
    if stations not in (65, 129, 257, 513, 4097):
        raise ValueError("Use a registered paired-edge measurement grid.")
    return tuple(_rows(index / (stations - 1), degree) for index in range(stations))


@lru_cache(maxsize=4)
def _selected_weights(
    fractions: tuple[float, ...], degree: int
) -> tuple[tuple[tuple[float, ...], ...], ...]:
    """
    Cache a bounded critical-location grid reused across local geometric sensitivities.
    """
    if not 1 <= len(fractions) <= 4097 or any(
        not math.isfinite(u) or not 0 <= u <= 1 for u in fractions
    ):
        raise ValueError("Use one to4097finite fractions inside the curve domain.")
    return tuple(_rows(u, degree) for u in fractions)


def _straight_width(chart: EdgeChart, curve: BoundaryCurve) -> Vector3 | None:
    """
    Recover an explicitly supplied constant material width on an exactly straight curve.
    """
    direction = difference(curve.points[-1], curve.points[0])
    straight = (
        all(
            magnitude(cross(difference(p, curve.points[0]), direction)) <= 1e-12
            for p in curve.points
        )
        and magnitude(difference(chart.case.start_width, chart.case.end_width)) <= 1e-10
    )
    return chart.case.start_width if straight else None


def frames_at(
    chart: EdgeChart, curve: BoundaryCurve, fractions: tuple[float, ...]
) -> tuple[BoundaryFrame, ...]:
    """
    Sample material kinematics at explicit fractions; singular frames raise ValueError.

    These nonuniform samples carry no implied quadrature weights or continuous
    certificate. Their location correspondence is exactly the supplied tuple.
    """
    width = _straight_width(chart, curve)
    return tuple(
        _frame(curve, rows, width) for rows in _selected_weights(fractions, len(curve.points) - 1)
    )


def _frame(
    curve: BoundaryCurve, rows: tuple[tuple[float, ...], ...], straight_width: Vector3 | None
) -> BoundaryFrame:
    """
    Recover the same analytic Frenet/ruling map using cached evaluation weights.
    """
    jets = tuple(
        Vector3(
            *(
                sum(getattr(p, axis) * w for p, w in zip(controls, weights))
                for axis in ("x", "y", "z")
            )
        )
        for controls, weights in zip(curve.derivatives, rows)
    )
    position, velocity, acceleration, jerk, snap = jets
    speed = magnitude(velocity)
    if straight_width is not None and speed > 1e-10:
        tangent = Vector3(*(value / speed for value in (velocity.x, velocity.y, velocity.z)))
        return BoundaryFrame(position, tangent, straight_width, 0, 0, speed, 0)
    observed = ruling_kinematics(velocity, acceleration, jerk, snap)
    return BoundaryFrame(
        position,
        observed.tangent,
        observed.width,
        observed.eta,
        observed.eta_u,
        observed.speed,
        observed.curvature,
    )


@dataclass(frozen=True)
class PairMeasure:
    """
    Retain violations and the corresponding shared-frame samples without physical PASS.
    """

    residual: tuple[float, ...]
    frames: tuple[BoundaryFrame | None, ...]
    minimum_j: float
    peak_a: float
    peak_b: float | None
    failed: int
    governing: tuple[str, ...]

    @property
    def score(self) -> float:
        """
        Return only the squared two-edge pinch deficits; no other rule steers changes.
        """
        return sum(value * value for value in self.residual)


def measure(
    chart: EdgeChart, curve: BoundaryCurve, stations: int, limit: PinchLimit
) -> PairMeasure:
    """
    Require both edge progress rates to exceed their common thickness-pinch demand.

    A has J=1; B has J=1-fullwidth*eta_s. Their affine material progress bounds
    every intermediate width position. A nonpositive B progress is a folding
    failure, never a negative/zero pinch ratio interpreted as safe. No auxiliary
    material reserve, containment, contact, length or loop objective is included.
    """
    half = chart.case.lines * chart.case.diameter_mm / 2 + chart.case.diameter_mm * 0.1
    residual, frames, governing = [], [], []
    minimum_j, peak_a, peak_b, failed = 1.0, 0.0, 0.0, 0
    straight_width = _straight_width(chart, curve)
    for rows in _weights(stations, len(curve.points) - 1):
        try:
            observed = _frame(curve, rows, straight_width)
            j = 1 - 2 * half * observed.slope_rate / observed.speed
            demand = chart.case.diameter_mm / 2 * observed.curvature * (1 + observed.slope**2)
            a = max(0.0, demand / limit.fraction - 1)
            b = max(0.0, demand / limit.fraction - j)
            residual.extend((math.log1p(a), math.log1p(b)))
            failed += int(j <= 0 or a > 1e-10 or b > 1e-10)
            minimum_j = min(minimum_j, j)
            peak_a = max(peak_a, demand)
            peak_b = max(peak_b, demand / j) if peak_b is not None and j > 0 else None
            governing.append("B" if j < 1 else "A")
            frames.append(observed)
        except ValueError:
            residual.extend((20.0, 20.0))
            frames.append(None)
            governing.append("undefined")
            failed += 1
    return PairMeasure(
        tuple(residual), tuple(frames), minimum_j, peak_a, peak_b, failed, tuple(governing)
    )
