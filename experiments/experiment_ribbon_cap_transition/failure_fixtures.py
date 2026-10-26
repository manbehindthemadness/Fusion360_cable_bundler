"""
Freeze controlled bend/fold demonstrations without invoking the endpoint solver.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3

from .director_fields import DirectorField
from .director_rotation_transport import integrate_rotation
from .director_transport import DirectorPath
from .endpoint_first import EndpointCase


@dataclass(frozen=True)
class Demonstration:
    """
    Declare one parented forward fixture and expected diagnostic outcomes in advance.
    """

    number: str
    parent: str
    field: DirectorField
    expected_red: tuple[str, ...]
    expected_amber: str | None


def specifications() -> tuple[Demonstration, ...]:
    """
    Vary one peak parameter per family; these are six variants, not six route wins.
    """
    zero = (0.0, 0.0, 0.0, 0.0)
    reach = math.hypot(3.6, 0.5)
    items: list[Demonstration] = []
    for number, peak in (("B1", 0.55), ("B2", 0.79), ("B3", 1.4)):
        coefficient = 18 * peak / (2 * reach)
        field = DirectorField(number, 18, (coefficient, -coefficient, 0, 0), zero, 7, 1)
        expected = ("center macaroni", "lane curvature x 3D") if number == "B3" else ()
        items.append(
            Demonstration(
                number,
                "controlled bend",
                field,
                expected,
                "center macaroni" if number == "B2" else None,
            )
        )
    for number, peak in (("F1", 0.7), ("F2", 0.99), ("F3", 1.2)):
        amplitude = peak * 36 / (2 * math.pi * 3.6)
        field = DirectorField(number, 36, zero, (amplitude, -amplitude, 0, 0), 7, 1)
        items.append(
            Demonstration(
                number,
                "controlled fold",
                field,
                ("material J",) if number == "F3" else (),
                "material J" if number == "F2" else None,
            )
        )
    return tuple(items)


def author(spec: Demonstration) -> tuple[DirectorPath, EndpointCase]:
    """
    Author forward geometry and freeze its terminal poses before measuring failures.

    Targets are fixture outputs, not independently prescribed routing challenges.
    """
    path = integrate_rotation(spec.field, 512, lambda: None)
    start, _ = path.pose(0)
    end, _ = path.pose(1)
    case = EndpointCase(
        spec.number,
        Vector3(*start[:3]),
        Vector3(*end[:3]),
        Vector3(*start[3:6]),
        Vector3(*end[3:6]),
        Vector3(*start[6:9]),
        Vector3(*end[6:9]),
        spec.field.lines,
        spec.field.diameter_mm,
    )
    return path, case
