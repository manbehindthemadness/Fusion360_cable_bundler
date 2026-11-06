"""
Define explicit finite hardware envelopes behind fixed ribbon mating faces.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from devtools.ribbon_analysis.contracts import TargetPose, Targets
from experiments.experiment_ribbon_fold_route.contact_bounds import Span
from experiments.experiment_ribbon_fold_route.geometry import Pose


class Terminal(Enum):
    """
    Identify the intended ribbon-to-hardware mating face.
    """

    START = "start"
    END = "end"


@dataclass(frozen=True)
class Dimensions:
    """
    Declare a rectangular combined hardware proxy and side/back clearance in millimeters.

    Clearance expands the sides and back. The mating plane stays fixed so the
    intended terminal contact is possible. This is an envelope assumption, not
    a measured connector, mounting-object model or Euclidean clearance offset.
    """

    width_mm: float
    height_mm: float
    depth_mm: float
    clearance_mm: float = 0.0

    def __post_init__(self) -> None:
        """
        Reject nonfinite or nonpositive dimensions and negative clearance.
        """
        for value in (self.width_mm, self.height_mm, self.depth_mm, self.clearance_mm):
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Hardware dimensions must be finite numbers")
        if min(self.width_mm, self.height_mm, self.depth_mm) <= 0 or self.clearance_mm < 0:
            raise ValueError("Hardware dimensions must be positive with nonnegative clearance")

    @classmethod
    def scaled(cls, source: TargetPose) -> Dimensions:
        """
        Freeze trial defaults from the unchanged joined-profile width and conductor diameter.

        Width is profile width plus one diameter per side, height three diameters,
        depth one profile width and clearance one quarter diameter. These declared
        prototype values are not fitted to a route or presented as real hardware.
        """
        target = Targets.capture(source)
        diameter = target.diameter_mm
        profile_width = (target.lines + 0.2) * diameter
        return cls(profile_width + 2 * diameter, 3 * diameter, profile_width, diameter / 4)


@dataclass(frozen=True)
class Box:
    """
    Place a finite hardware envelope with local positive X pointing out of its mating face.
    """

    terminal: Terminal
    pose: Pose
    dimensions: Dimensions

    def __post_init__(self) -> None:
        """
        Require a finite rigid frame before interpreting local coordinate limits as a solid box.
        """
        if not isinstance(self.terminal, Terminal) or not isinstance(self.dimensions, Dimensions):
            raise ValueError("Hardware needs a terminal identity and explicit dimensions")
        vectors = (self.pose.origin, self.pose.tangent, self.pose.width)
        if any(not math.isfinite(value) for v in vectors for value in (v.x, v.y, v.z)):
            raise ValueError("Hardware frames must be finite")
        if (
            max(
                abs(magnitude(self.pose.tangent) - 1),
                abs(magnitude(self.pose.width) - 1),
                abs(dot(self.pose.tangent, self.pose.width)),
            )
            > 1e-10
        ):
            raise ValueError("Hardware frames must be orthonormal")
        forward = unit(self.pose.tangent)
        width = unit(self.pose.width.translated(forward, -dot(self.pose.width, forward)))
        object.__setattr__(self, "pose", Pose(self.pose.origin, forward, width))

    @property
    def axes(self) -> tuple[Vector3, Vector3, Vector3]:
        """
        Return the orthonormal outward, width and height directions.
        """
        return self.pose.tangent, self.pose.width, cross(self.pose.tangent, self.pose.width)

    @property
    def bounds(self) -> tuple[Span, Span, Span]:
        """
        Bound only the occupied side of the mating face, with explicit finite depth.
        """
        d = self.dimensions
        return (
            Span(-d.depth_mm - d.clearance_mm, 0.0),
            Span(-d.width_mm / 2 - d.clearance_mm, d.width_mm / 2 + d.clearance_mm),
            Span(-d.height_mm / 2 - d.clearance_mm, d.height_mm / 2 + d.clearance_mm),
        )

    def corners(self) -> tuple[Vector3, ...]:
        """
        Return all eight exact proxy corners for bounded diagnostic wireframe display.
        """
        x, y, z = self.bounds
        return tuple(
            self.pose.point(Vector3(a, b, c))
            for a in (x.low, x.high)
            for b in (y.low, y.high)
            for c in (z.low, z.high)
        )


@dataclass(frozen=True)
class Hardware:
    """
    Bind both proxies to exact fixed targets without adding the rest of the gym as obstacles.
    """

    targets: Targets
    boxes: tuple[Box, Box]

    def __post_init__(self) -> None:
        """
        Bind each proxy's actual plane and outward direction to its declared fixed terminal.
        """
        target = Targets.capture(self.targets)
        if len(self.boxes) != 2:
            raise ValueError("Both fixed terminal proxies are required")
        for box, terminal, origin, tangent in (
            (self.boxes[0], Terminal.START, target.start, target.start_tangent),
            (
                self.boxes[1],
                Terminal.END,
                target.end,
                Vector3(0, 0, 0).translated(target.end_tangent, -1),
            ),
        ):
            if (
                box.terminal is not terminal
                or box.pose.origin != origin
                or magnitude(difference(box.pose.tangent, unit(tangent))) > 1e-10
            ):
                raise ValueError("Hardware mating faces must retain the fixed target poses")

    @classmethod
    def create(
        cls, source: TargetPose, start: Dimensions, end: Dimensions | None = None
    ) -> Hardware:
        """
        Place start hardware behind departure and end hardware beyond arrival along the route.
        """
        targets = Targets.capture(source)
        poses = (
            (Terminal.START, targets.start, targets.start_tangent, targets.start_width, start),
            (
                Terminal.END,
                targets.end,
                Vector3(0, 0, 0).translated(targets.end_tangent, -1),
                targets.end_width,
                end or start,
            ),
        )
        boxes = []
        for terminal, origin, forward, width, dimensions in poses:
            normal = unit(forward)
            across = unit(width.translated(normal, -dot(width, normal)))
            boxes.append(Box(terminal, Pose(origin, normal, across), dimensions))
        return cls(targets, (boxes[0], boxes[1]))
