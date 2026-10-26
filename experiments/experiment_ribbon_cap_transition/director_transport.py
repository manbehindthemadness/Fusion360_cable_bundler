"""
Transport a material frame through signed bending without Frenet division.

Integrate r'=T,T'=k*(W cross T),W'=-k*eta*(W cross T). This prescribed-field
kinematic experiment assumes a developable strip;it does not solve equilibrium
or allocate a path between independently prescribed endpoints.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import Vector3, dot

from .director_fields import DirectorField

State = tuple[float, ...]
INITIAL: State = (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0)


def rate(field: DirectorField, state: State, u: float) -> State:
    """
    Return normalized-coordinate rates of position,tangent and material width.
    """
    k, eta, _ = field.sample(u)
    tx, ty, tz = state[3:6]
    wx, wy, wz = state[6:9]
    nx, ny, nz = wy * tz - wz * ty, wz * tx - wx * tz, wx * ty - wy * tx
    length = field.length_mm
    bend = k * length
    return (
        length * tx,
        length * ty,
        length * tz,
        bend * nx,
        bend * ny,
        bend * nz,
        -bend * eta * nx,
        -bend * eta * ny,
        -bend * eta * nz,
    )


@dataclass(frozen=True)
class DirectorPath:
    """
    Retain integrated states and cubic Hermite dense output with measured drift.

    Frames are not renormalized or repaired. Tests/audits must measure integration
    drift and convergence. Dense-output lane derivatives differentiate the actual
    interpolation rather than substituting ideal unit-speed formulas.
    """

    field: DirectorField
    states: tuple[State, ...]
    rates: tuple[State, ...]

    def pose(self, u: float) -> tuple[State, State]:
        """
        Evaluate the interpolated pose and its parameter derivative on[0,1].
        """
        if not math.isfinite(u) or not 0 <= u <= 1:
            raise ValueError("Director fraction must lie within[0,1].")
        steps = len(self.states) - 1
        index = min(int(u * steps), steps - 1)
        t = u * steps - index
        h = 1 / steps
        basis = (
            2 * t**3 - 3 * t * t + 1,
            (t**3 - 2 * t * t + t) * h,
            -2 * t**3 + 3 * t * t,
            (t**3 - t * t) * h,
        )
        derivative = (
            (6 * t * t - 6 * t) / h,
            3 * t * t - 4 * t + 1,
            (-6 * t * t + 6 * t) / h,
            3 * t * t - 2 * t,
        )
        rows = (
            self.states[index],
            self.rates[index],
            self.states[index + 1],
            self.rates[index + 1],
        )
        return (
            tuple(sum(b * row[j] for b, row in zip(basis, rows)) for j in range(9)),
            tuple(sum(b * row[j] for b, row in zip(derivative, rows)) for j in range(9)),
        )

    def lane(self, u: float, offset_mm: float) -> tuple[Vector3, Vector3]:
        """
        Return a complete material lane's position and actual parameter velocity.

        Offset0is the center,+halfwidth is A and-halfwidth B. Rulings are oblique
        when eta differs from zero;these are not perpendicular rigid sections.
        """
        if not math.isfinite(offset_mm) or abs(offset_mm) > self.field.half_width_mm:
            raise ValueError("Director offset lies outside the physical ribbon width.")
        state, derivative = self.pose(u)
        _, eta, eta_s = self.field.sample(u)
        eta_u = eta_s * self.field.length_mm
        p = tuple(state[j] + offset_mm * (state[j + 6] + eta * state[j + 3]) for j in range(3))
        v = tuple(
            derivative[j]
            + offset_mm * (derivative[j + 6] + eta * derivative[j + 3] + eta_u * state[j + 3])
            for j in range(3)
        )
        return Vector3(*p), Vector3(*v)


def integrate(
    field: DirectorField,
    steps: int,
    checkpoint: Callable[[], None],
    *,
    initial: State = INITIAL,
) -> DirectorPath:
    """
    Perform fixed-cost RK4 transport without searches,singular-frame tests or repair.

    Registered grids64/128/256/512support oracle and convergence comparisons.
    The same method/grid applies to every fixture. Resource checks occur at least
    every32steps;no adaptive refinement or post-result budget increase.
    """
    if isinstance(steps, bool) or not isinstance(steps, int) or steps not in (64, 128, 256, 512):
        raise ValueError("Use a registered director integration grid.")
    if len(initial) != 9 or not all(math.isfinite(value) for value in initial):
        raise ValueError("Initial director pose needs nine finite coordinates.")
    tangent, width = Vector3(*initial[3:6]), Vector3(*initial[6:9])
    if (
        max(abs(dot(tangent, tangent) - 1), abs(dot(width, width) - 1), abs(dot(tangent, width)))
        > 1e-8
    ):
        raise ValueError("Initial directors must be perpendicular unit vectors.")
    states = [initial]
    rates = []
    h = 1 / steps
    for i in range(steps):
        if i % 32 == 0:
            checkpoint()
        state = states[-1]
        u = i / steps
        a = rate(field, state, u)
        b = rate(field, tuple(v + h * d / 2 for v, d in zip(state, a)), u + h / 2)
        c = rate(field, tuple(v + h * d / 2 for v, d in zip(state, b)), u + h / 2)
        d = rate(field, tuple(v + h * q for v, q in zip(state, c)), (i + 1) / steps)
        states.append(
            tuple(v + h * (w + 2 * x + 2 * y + z) / 6 for v, w, x, y, z in zip(state, a, b, c, d))
        )
        rates.append(a)
    rates.append(rate(field, states[-1], 1))
    return DirectorPath(field, tuple(states), tuple(rates))
