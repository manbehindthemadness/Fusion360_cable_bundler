"""
Declare independent boundary inputs across six ribbon-routing challenge families.

Positions use nominal ribbon width as their reference scale. These are endpoint
challenges,not solver-produced witness curves or prescribed interior trajectories.
Family names describe boundary intent;they never select solver behavior.
"""

from __future__ import annotations

from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from .generalization_cases import _case


def cases() -> tuple[EndpointCase, ...]:
    """
    Return48 fixed configurations from planar U-turns to spatial ordered rolls.

    Each family has eight different endpoint/dimension configurations. No rigid
    copies or old G/H inputs are included. H01..H04 remain separately reserved.
    """
    dimensions = (
        (5, 1.2),
        (7, 0.9),
        (9, 1.5),
        (13, 1.0),
        (16, 0.8),
        (19, 1.2),
        (24, 0.8),
        (32, 0.75),
    )
    result: list[EndpointCase] = []
    for family in range(6):
        for index, (lines, diameter) in enumerate(dimensions):
            width = lines * diameter
            sign = -1 if index % 2 else 1
            if family == 0:
                # In-plane bending about the preserved material-width axis.
                radius = (0.8, 1.0, 1.2, 1.5, 1.8, 2.2, 2.8, 3.5)[index]
                end = (0.0, 0.0, 2 * radius)
                yaw, pitch, roll = 180.0, 0.0, 180.0
                label = "planar U"
            elif family == 1:
                end = (0.3 + 0.13 * index, sign * (0.5 + 0.14 * index), 2.0 + 0.35 * index)
                yaw, pitch, roll = 165.0 + 3 * index, sign * (4 + 2 * index), 145.0 + 7 * index
                label = "spatial U"
            elif family == 2:
                end = (2.0 + 0.3 * index, sign * (1.5 + 0.18 * index), 0.2 + 0.12 * index)
                yaw, pitch, roll = sign * (45.0 + 6 * index), sign * 2.0 * index, sign * 90.0
                label = "lateral turn"
            elif family == 3:
                end = (4.0 + 0.45 * index, sign * 0.12 * index, sign * (0.7 + 0.25 * index))
                yaw, pitch, roll = sign * 2.0 * index, sign * (index - 3), sign * 5.0 * index
                label = "offset return"
            elif family == 4:
                end = (
                    4.0 + 0.22 * index,
                    sign * (0.25 + 0.09 * index),
                    sign * (0.8 + 0.13 * index),
                )
                yaw, pitch, roll = sign * (2.0 + index), sign * (8.0 + 2 * index), sign * 180.0
                label = "spatial half roll"
            else:
                end = (
                    3.0 + 0.25 * index,
                    sign * (1.0 + 0.08 * index),
                    -sign * (0.5 + 0.16 * index),
                )
                yaw, pitch, roll = (
                    sign * (18.0 + 3 * index),
                    -sign * (5.0 + 2 * index),
                    -sign * (110.0 + 5 * index),
                )
                label = "oblique roll"
            number = len(result) + 1
            endpoint = tuple(value * width for value in end)
            result.append(
                _case(f"B{number:02} {label}", lines, diameter, endpoint, yaw, pitch, roll)
            )
    return tuple(result)
