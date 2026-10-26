"""
Transport material frames with explicit positive progress and tangent turning.

Variable progress is a parameter choice,not endpoint snapping or geometric repair.
The historical constant-speed rotation adapter uses this same RK4 implementation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from .director_transport import INITIAL, State, motion_rate


@dataclass(frozen=True)
class DirectorMotion:
    """
    Specify center progress per u,signed tangent turn per u,and ruling slope.
    """

    progress_mm: float
    turn: float
    eta: float

    def __post_init__(self) -> None:
        """
        Refuse nonfinite motion or stationary/reversed center progress.
        """
        if (
            not all(math.isfinite(v) for v in (self.progress_mm, self.turn, self.eta))
            or self.progress_mm <= 0
        ):
            raise ValueError("Director motion requires finite positive progress.")


def _rotate(q: tuple[float, ...], v: tuple[float, ...]) -> tuple[float, float, float]:
    """
    Apply the quaternion rotation polynomial to a reference vector.
    """
    w, x, y, z = q
    a, b, c = v
    ux, uy, uz = y * c - z * b, z * a - x * c, x * b - y * a
    return (
        a + 2 * (w * ux + y * uz - z * uy),
        b + 2 * (w * uy + z * ux - x * uz),
        c + 2 * (w * uz + x * uy - y * ux),
    )


def integrate_motion(
    motion: Callable[[float], DirectorMotion],
    steps: int,
    checkpoint: Callable[[], None],
    *,
    initial: State = INITIAL,
) -> tuple[tuple[State, ...], tuple[State, ...]]:
    """
    Integrate explicit material motion with structural unit director axes.

    Fixed64/128/256/512grids and caller checkpoints bound work. Initial pose and
    motion validate before use. Returns states and exact input rates at grid nodes;
    dense-output accuracy remains a separate measurement.
    """
    if isinstance(steps, bool) or not isinstance(steps, int) or steps not in (64, 128, 256, 512):
        raise ValueError("Use a registered rotation integration grid.")
    if len(initial) != 9 or not all(math.isfinite(v) for v in initial):
        raise ValueError("Initial rotation pose needs nine finite coordinates.")
    tangent, width = initial[3:6], initial[6:9]
    if (
        max(
            abs(sum(v * v for v in tangent) - 1),
            abs(sum(v * v for v in width) - 1),
            abs(sum(a * b for a, b in zip(tangent, width))),
        )
        > 1e-8
    ):
        raise ValueError("Initial directors must be perpendicular unit vectors.")
    current = initial[:3] + (1.0, 0.0, 0.0, 0.0)

    def derivative(values: tuple[float, ...], u: float) -> tuple[float, ...]:
        """
        Differentiate position and a right-multiplied material rotation quaternion.
        """
        motion_value = motion(u)
        scale, eta = motion_value.turn, motion_value.eta
        ox, oy, oz = (scale * (eta * a + b) for a, b in zip(tangent, width))
        w, x, y, z = values[3:7]
        t = _rotate(values[3:7], tangent)
        return (
            motion_value.progress_mm * t[0],
            motion_value.progress_mm * t[1],
            motion_value.progress_mm * t[2],
            -0.5 * (x * ox + y * oy + z * oz),
            0.5 * (w * ox + y * oz - z * oy),
            0.5 * (w * oy + z * ox - x * oz),
            0.5 * (w * oz + x * oy - y * ox),
        )

    states = [initial]
    first = motion(0)
    rates = [motion_rate(initial, first.progress_mm, first.turn, first.eta)]
    h = 1 / steps
    for i in range(steps):
        if i % 32 == 0:
            checkpoint()
        a = derivative(current, i / steps)
        b = derivative(tuple(v + h * d / 2 for v, d in zip(current, a)), (i + 0.5) / steps)
        c = derivative(tuple(v + h * d / 2 for v, d in zip(current, b)), (i + 0.5) / steps)
        d = derivative(tuple(v + h * e for v, e in zip(current, c)), (i + 1) / steps)
        proposed = tuple(
            v + h * (w + 2 * x + 2 * y + z) / 6 for v, w, x, y, z in zip(current, a, b, c, d)
        )
        norm = math.sqrt(sum(v * v for v in proposed[3:7]))
        if not math.isfinite(norm) or norm <= 1e-12:
            raise ValueError("Rotation integration lost its quaternion.")
        current = proposed[:3] + tuple(v / norm for v in proposed[3:7])
        state = current[:3] + _rotate(current[3:7], tangent) + _rotate(current[3:7], width)
        states.append(state)
        sample = motion((i + 1) / steps)
        rates.append(motion_rate(state, sample.progress_mm, sample.turn, sample.eta))
    return tuple(states), tuple(rates)
