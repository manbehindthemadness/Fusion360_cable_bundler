"""
Expose one continuous bank coordinate while eliminating a two-fold pair's orientation residual.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from functools import cached_property

from cable_bundler.routing.geometry import difference, magnitude
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose
from experiments.experiment_ribbon_fold_route.orientation import (
    Quaternion,
    material_factors,
    relative_rotation,
    remaining_rotation,
)


@dataclass(frozen=True)
class FrameFamily:
    """
    Continue the same ordered material branch with exact full end orientation.

    Equal-opposite banks are not required. The first bank determines its bend
    angle by eliminating the remaining quaternion's longitudinal component.
    The second angle and bank follow algebraically. This coordinate chart is
    not a positional solver, a new discrete root search or a physical certificate.
    Degenerate charts, longitudinal creases and material sign/half-turn aliases
    decline rather than selecting a different branch or adding events.
    """

    start: Pose
    end: Pose
    reference: tuple[CylindricalFold, CylindricalFold]

    def __post_init__(self) -> None:
        """
        Require two ordinary material factors with one unchanged profile width.
        """
        if len(self.reference) != 2 or any(
            type(fold) is not CylindricalFold for fold in self.reference
        ):
            raise ValueError("An orientation family requires two ordinary material folds")
        if self.reference[0].width_mm != self.reference[1].width_mm:
            raise ValueError("An orientation family must preserve the joined profile width")

    @cached_property
    def rotation(self) -> Quaternion:
        """
        Reuse the shared exact relative-frame conversion without retaining other families.
        """
        return relative_rotation(self.start, self.end)

    def at(self, bank: float) -> tuple[CylindricalFold, CylindricalFold] | None:
        """
        Derive one same-sign factor pair, retaining radii and extra flat material.

        Finite bank inputs outside regular material bounds return unsupported.
        Invalid nonfinite inputs raise ValueError. Existing shared quaternion
        conversion can decline a longitudinal remaining crease; no alternative
        bank, root or half-turn is tried. Endpoint position remains unclosed.
        """
        if type(bank) not in (int, float) or not math.isfinite(bank):
            raise ValueError("Use a finite bank coordinate")
        if abs(bank) >= math.pi / 2 - 1e-6:
            return None
        _, x, y, z = self.rotation
        denominator = math.sin(bank) * y + math.cos(bank) * x
        if z == denominator == 0:
            return None
        half = math.atan2(z, denominator)
        if half > math.pi / 2:
            half -= math.pi
        elif half < -math.pi / 2:
            half += math.pi
        first = (
            math.cos(half),
            math.sin(bank) * math.sin(half),
            -math.cos(bank) * math.sin(half),
            0.0,
        )
        radius, width = self.reference[0].radius_mm, self.reference[0].width_mm
        try:
            factors = material_factors(first, radius, width, 0.0) + material_factors(
                remaining_rotation(first, self.rotation), radius, width, 0.0
            )
        except ValueError:
            return None
        if len(factors) != 2 or any(
            math.copysign(1, old.angle_radians) != math.copysign(1, new.angle_radians)
            or abs(old.angle_radians - new.angle_radians) > math.pi
            for old, new in zip(self.reference, factors)
        ):
            return None
        result = []
        for old, new in zip(self.reference, factors):
            old_lead = old.width_mm / 2 * abs(math.tan(old.bank_radians))
            new_lead = old.width_mm / 2 * abs(math.tan(new.bank_radians))
            result.append(
                replace(
                    old,
                    angle_radians=new.angle_radians,
                    bank_radians=new.bank_radians,
                    before_mm=new_lead + max(0.0, old.before_mm - old_lead),
                    after_mm=new_lead + max(0.0, old.after_mm - old_lead),
                )
            )
        pose = self.start
        for fold in result:
            pose = PlacedPiece(pose, fold, "Continuous orientation family").end_pose()
        if (
            max(
                magnitude(difference(pose.tangent, self.end.tangent)),
                magnitude(difference(pose.width, self.end.width)),
            )
            > 1e-10
        ):
            raise ArithmeticError("Continuous factors lost the ordered end orientation")
        return result[0], result[1]
