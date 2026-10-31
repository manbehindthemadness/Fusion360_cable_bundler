"""
Separate material-fold pinch from sufficient rigid-sweep construction bounds.
"""

from __future__ import annotations

import math
from enum import Enum

from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.pinch import PinchLimit


class ConstructionPolicy(Enum):
    """
    Declare whether a route must also avoid local rigid-profile sweep collapse.
    """

    MATERIAL_FOLD = "material_fold"
    RIGID_PERPENDICULAR = "rigid_perpendicular"


def enclosing_profile_radius(targets: Targets) -> float:
    """
    Enclose the unchanged joined lobe contour for any transported profile roll.

    The existing contour lies inside half-width (lines + .2)D/2 and half-height
    D/2. The box's circumradius is a sufficient bound, not the exact contour's
    minimum enclosing radius or a physical ribbon bend requirement.
    """
    return math.hypot((targets.lines + 0.2) * targets.diameter_mm / 2, targets.diameter_mm / 2)


def spatial_fold_radius(targets: Targets, limit: PinchLimit, policy: ConstructionPolicy) -> float:
    """
    Bound local rigid sweep singularity without claiming native material fidelity.

    A cylindrical fold center has curvature cos(bank)^2/R <= 1/R. Bounding every
    rigid profile offset by rho gives J >= 1-rho/R for any transported orientation.
    The requested utilization supplies the positive margin. This deliberately
    conservative construction policy does not certify self-clearance, terminal
    roll, equal native lane lengths or native no-wide-axis bending.
    """
    if not isinstance(policy, ConstructionPolicy):
        raise ValueError("Use an explicit ConstructionPolicy.")
    reach = (
        enclosing_profile_radius(targets)
        if policy is ConstructionPolicy.RIGID_PERPENDICULAR
        else targets.diameter_mm / 2
    )
    return reach / limit.fraction * (1 + 1e-9)
