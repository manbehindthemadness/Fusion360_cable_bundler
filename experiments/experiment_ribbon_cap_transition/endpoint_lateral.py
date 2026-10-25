"""
Freeze lateral endpoint turns without providing an interior path to the solver.
"""

import math

from cable_bundler.routing.geometry import Vector3

from .endpoint_first import EndpointCase


def lateral_cases() -> tuple[EndpointCase, ...]:
    """
    Register 30/60/90-degree XY heading changes with distinct spatial endpoints.

    End width remains in the XY plane perpendicular to its endpoint tangent.
    Intermediate banking and the centerline come from the unchanged generator.
    """
    starts = Vector3(-40, 0, 0)
    specifications = (
        (30, Vector3(40, 20, 0)),
        (60, Vector3(20, 40, 10)),
        (90, Vector3(0, 50, 15)),
    )
    return tuple(
        EndpointCase(
            f"lateral_{angle}",
            starts,
            end,
            Vector3(1, 0, 0),
            Vector3(math.cos(math.radians(angle)), math.sin(math.radians(angle)), 0),
            Vector3(0, 1, 0),
            Vector3(-math.sin(math.radians(angle)), math.cos(math.radians(angle)), 0),
        )
        for angle, end in specifications
    )
