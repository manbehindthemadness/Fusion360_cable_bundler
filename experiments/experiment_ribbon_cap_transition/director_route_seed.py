"""
Initialize spatial routing with a coupled bend reversal rather than Euler events.

The seed uses only endpoint geometry. It is a numerical hypothesis inspired by
qualitative ribbon references,not a measured equilibrium or stored fixture path.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import cross, difference, dot, magnitude, unit

from .coupled_motion import rotate
from .endpoint_first import EndpointCase


def corkscrew_seed(case: EndpointCase) -> tuple[float, ...]:
    """
    Estimate signed bending and twist from parallel-transported terminal frames.

    K=A*sin(2pi*u),eta=B*sin(2pi*u) has integrated twist AB/2 in the material
    strain model. This initializes a reversal coupled to roll;noncommuting full
    frame/position closure still belongs to the solver. No winding is inferred
    beyond the prescribed endpoint orientation.
    """
    chord = difference(case.end, case.start)
    t, w = case.start_tangent, case.start_width
    normal = cross(w, t)
    product = cross(t, case.end_tangent)
    sine = magnitude(product)
    cosine = dot(t, case.end_tangent)
    if sine > 1e-10:
        transported = rotate(w, unit(product), math.atan2(sine, cosine))
    elif cosine < 0:
        transported = w
    else:
        transported = w
    roll = math.atan2(
        dot(cross(transported, case.end_width), case.end_tangent), dot(transported, case.end_width)
    )
    bend = math.atan2(dot(case.end_tangent, normal), dot(case.end_tangent, t))
    direction = math.atan2(dot(chord, normal), dot(chord, t))
    amplitude = max(0.5, math.sqrt(4 * math.pi * abs(roll)))
    sign = -1.0 if direction < 0 else 1.0
    amplitude *= sign
    ruling = 2 * roll / amplitude
    return bend, 0.0, amplitude, 0.0, 0.0, 0.0, ruling, 0.0, 0.0, 1.6
