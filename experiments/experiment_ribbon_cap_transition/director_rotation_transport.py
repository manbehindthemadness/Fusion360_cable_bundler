"""
Transport material directors using unit rotations instead of nine unconstrained axes.

RK4 integrates position and quaternion. Unit-quaternion normalization maintains
the rotation representation at each integration step;it does not alter endpoints
to match targets. Interpolated frame/metric accuracy remains separately audited.
"""

from __future__ import annotations

import math
from typing import Callable

from .director_fields import DirectorField
from .director_transport import INITIAL, DirectorPath, State, rate


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


def integrate_rotation(
    field: DirectorField, steps: int, checkpoint: Callable[[], None], *, initial: State = INITIAL
) -> DirectorPath:
    """
    Integrate the same intrinsic fields with structural unit director axes.

    Same grids/checkpoints as the original transport;return the same dense-output
    type. Initial pose validation is explicit;no axis repair or target snapping.
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
        k, eta, _ = field.sample(u)
        scale = k * field.length_mm
        ox, oy, oz = (scale * (eta * a + b) for a, b in zip(tangent, width))
        w, x, y, z = values[3:7]
        t = _rotate(values[3:7], tangent)
        return (
            field.length_mm * t[0],
            field.length_mm * t[1],
            field.length_mm * t[2],
            -0.5 * (x * ox + y * oy + z * oz),
            0.5 * (w * ox + y * oz - z * oy),
            0.5 * (w * oy + z * ox - x * oz),
            0.5 * (w * oz + x * oy - y * ox),
        )

    states = [initial]
    rates = [rate(field, initial, 0)]
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
        rates.append(rate(field, state, (i + 1) / steps))
    return DirectorPath(field, tuple(states), tuple(rates))
