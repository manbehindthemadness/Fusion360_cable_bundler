"""
Flex a section through three fixed anchors with independently perpendicular frames.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import (
    Vector3,
    cross,
    difference,
    dot,
    lerp,
    linear_combination,
    unit,
)
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame


@dataclass(frozen=True)
class AnchorFrame:
    """
    Fix one mid-thickness position and its local transverse orientation.
    """

    position: Vector3
    width: Vector3
    thickness: Vector3


def anchor_frame(position: Vector3, width: Vector3, tangent: Vector3) -> AnchorFrame:
    """
    Project the original width perpendicular to a guide tangent; reject degeneracy.

    No fallback axis or target movement is allowed. Thickness follows the original
    right-handed section convention. Tangent magnitude does not affect orientation.
    """
    normal = unit(tangent)
    transverse = unit(difference(width, linear_combination(normal, dot(width, normal), width, 0)))
    return AnchorFrame(position, transverse, unit(cross(normal, transverse)))


@dataclass(frozen=True)
class FlexSection:
    """
    Interpolate fixed minus/center/plus anchors without route or roll optimization.

    Piecewise cubic Hermite midlines preserve anchor positions and width derivatives.
    Smoothstep thickness interpolation has zero derivative at anchors. Consequently
    the mathematical local section plane there is perpendicular to the respective
    path tangent. Between anchors this is a deformation, not a spacing certificate.
    """

    reach: float
    minus: AnchorFrame
    center: AnchorFrame
    plus: AnchorFrame

    def point(self, x: float, y: float) -> Vector3:
        """
        Map nominal width/thickness coordinates to a nonplanar section in millimeters.
        """
        if not math.isfinite(x) or not math.isfinite(y) or abs(x) > self.reach + 1e-8:
            raise ValueError("Section coordinates must be finite and inside the fixed width.")
        left, right = (self.minus, self.center) if x < 0 else (self.center, self.plus)
        t = max(0.0, min(1.0, (x + self.reach) / self.reach if x < 0 else x / self.reach))
        h00, h10 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t
        h01, h11 = -2 * t**3 + 3 * t**2, t**3 - t**2
        position = linear_combination(left.position, h00, right.position, h01)
        derivative = linear_combination(left.width, h10 * self.reach, right.width, h11 * self.reach)
        position = linear_combination(position, 1, derivative, 1)
        thickness = unit(lerp(left.thickness, right.thickness, t * t * (3 - 2 * t)))
        return position.translated(thickness, y)


def flex_section(
    frame: RibbonFrame,
    minus_tangent: Vector3,
    plus_tangent: Vector3,
    *,
    reach: float = 14.4,
    terminal: bool = False,
) -> FlexSection:
    """
    Keep all three positions fixed; retain exact planar terminal caps as an exception.

    Interior edge orientations use guide tangents. Terminal orientations use the
    authoritative cap tangent instead, so fitted-guide endpoint derivatives cannot
    silently alter the cap/ending contract. No physical guide objects are required.
    """
    if not math.isfinite(reach) or reach <= 0:
        raise ValueError("Section reach must be finite and positive.")
    minus = frame.origin.translated(frame.width, -reach)
    plus = frame.origin.translated(frame.width, reach)
    return FlexSection(
        reach,
        anchor_frame(minus, frame.width, frame.tangent if terminal else minus_tangent),
        anchor_frame(frame.origin, frame.width, frame.tangent),
        anchor_frame(plus, frame.width, frame.tangent if terminal else plus_tangent),
    )
