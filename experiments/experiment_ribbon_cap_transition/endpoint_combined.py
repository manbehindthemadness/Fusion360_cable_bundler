"""
Freeze combined turn-and-roll challenges independently of generated centerlines.

These examined development inputs extend prior endpoint and lateral families.
Endpoint width directions specify ordered cap orientation, not a winding class.
No native attempt or solver evaluation occurs while registering these inputs.
"""

import math

from cable_bundler.routing.geometry import Vector3, unit

from .endpoint_first import EndpointCase


def combined_cases() -> tuple[EndpointCase, ...]:
    """
    Combine a lateral quarter-roll, oblique return and reversed spatial cap.

    Retain 19 conductors of 1.5 mm diameter and the existing five-width sphere
    policy. Every position, tangent and signed width axis is fixed before solving.
    """
    return (
        EndpointCase(
            "combined_lateral90_quarter_roll",
            Vector3(-40, 0, 0),
            Vector3(0, 50, 15),
            Vector3(1, 0, 0),
            Vector3(0, 1, 0),
            Vector3(0, 1, 0),
            Vector3(0, 0, 1),
        ),
        EndpointCase(
            "combined_oblique120_return",
            Vector3(-40, 0, 0),
            Vector3(10, 40, 12),
            Vector3(1, 0, 0),
            Vector3(-0.5, math.sqrt(3) / 2, 0),
            Vector3(0, 1, 0),
            unit(Vector3(-math.sqrt(3) / 2, -0.5, 1)),
        ),
        EndpointCase(
            "combined_spatial_reversed_width",
            Vector3(-35, -10, 0),
            Vector3(30, 20, 25),
            Vector3(1, 0, 0),
            unit(Vector3(1, 1, 1)),
            Vector3(0, 1, 0),
            unit(Vector3(1, -2, 1)),
        ),
    )
