"""
Freeze three collateral-mechanics challenges, not three fixes for one failure.
"""

from __future__ import annotations

import math
from dataclasses import replace

from cable_bundler.routing.geometry import CubicBezier, Vector3
from experiments.experiment_ribbon_diagnosis.spatial import rotate
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase

from .fixtures import _arc, _case, development_cases

PURPOSES = {
    "regression_twisted_quarter": "Twist/spacing and cap flow through a curved route.",
    "regression_orthogonal_bends": "Width/thickness transport through two perpendicular bend planes.",
    "regression_asymmetric_arch": "Preserve exact cap alignment, ordered translated lanes and variable curvature.",
}


def collateral_cases() -> tuple[RibbonStressCase, ...]:
    """
    Author distinct fixed routes with the same material and five-width sphere scale.

    Outcomes do not alter endpoints, orientation, targets, curvature or identity.
    These are development regression challenges, not unseen certification cases.
    """
    quarter = _arc(0, 30, 30, -math.pi / 2, math.pi / 2)
    twisted = replace(
        _case("regression_twisted_quarter", quarter, Vector3(15, 0, 15)),
        end_width=rotate(Vector3(0, 1, 0), quarter[-1].derivative(1), 60),
    )

    def second_plane(point: Vector3) -> Vector3:
        """
        Join the first quarter's final tangent to a perpendicular second bend.
        """
        return Vector3(30, point.z, 30 + point.x)

    second = tuple(
        CubicBezier(*(second_plane(p) for p in (c.start, c.control_a, c.control_b, c.end)))
        for c in quarter
    )
    compound = replace(
        _case("regression_orthogonal_bends", (*quarter, *second), Vector3(15, 15, 30)),
        end_width=Vector3(1, 0, 0),
    )
    arch = _case(
        "regression_asymmetric_arch",
        (
            CubicBezier(
                Vector3(-45, 0, 0), Vector3(-35, 0, 30), Vector3(25, 0, 35), Vector3(40, 0, 10)
            ),
        ),
        Vector3(-2.5, 0, 15),
    )
    return twisted, compound, arch


def comparison_cases() -> tuple[RibbonStressCase, ...]:
    """
    Retain the original failure, all existing controls and all three collateral cases.

    Register eleven complete configurations for a future baseline/fix comparison;
    registration does not authorize their execution or any native attempts.
    """
    return (*development_cases(), *collateral_cases())
