"""
Discover three C4-joined trunk regions from frozen ordered endpoint poses.

Circular approaches occupy parameter quarters, with one middle bridge occupying
one half. These are trunk partitions, not exempt end-loft transition regions.
Every piece must pass the original envelope/regularity certificate before traces.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, cross, unit

from .distributed_bend import distributed_controls
from .endpoint_first import EndpointCase, derivative, evaluate
from .trace_diagnostic import shared_lane_jet


@dataclass(frozen=True)
class BendPose:
    """
    Retain an ordered local pose, external or discovered from an endpoint arc.
    """

    origin: Vector3
    tangent: Vector3
    width: Vector3


@dataclass(frozen=True)
class BendPiece:
    """
    Store a local Bernstein curve and its interval in the global path parameter.
    """

    start_parameter: float
    end_parameter: float
    controls: tuple[Vector3, ...]

    def jet(
        self, parameter: float, offset_mm: float, constant_width: Vector3 | None = None
    ) -> tuple[Vector3, Vector3, Vector3]:
        """
        Evaluate offset-lane position/derivatives in the global parameter units.
        """
        duration = self.end_parameter - self.start_parameter
        local = (parameter - self.start_parameter) / duration
        if not math.isfinite(local) or not 0 <= local <= 1:
            raise ValueError("Piece parameter outside its interval.")
        if offset_mm == 0 or constant_width is not None:
            first = derivative(self.controls)
            position = evaluate(self.controls, local)
            velocity, acceleration = evaluate(first, local), evaluate(derivative(first), local)
            if constant_width is not None:
                position = position.translated(constant_width, offset_mm)
        else:
            position, velocity, acceleration = shared_lane_jet(self.controls, local, offset_mm)
        zero = Vector3(0, 0, 0)
        return (
            position,
            zero.translated(velocity, 1 / duration),
            zero.translated(acceleration, 1 / duration**2),
        )


@dataclass(frozen=True)
class PiecewiseBend:
    """
    Retain the complete shared scaffold with optional exact straight width.
    """

    pieces: tuple[BendPiece, ...]
    constant_width: Vector3 | None = None

    def jet(self, parameter: float, offset_mm: float) -> tuple[Vector3, Vector3, Vector3]:
        """
        Evaluate the right-sided jet at joins; C4 construction preserves both sides.
        """
        if not math.isfinite(parameter) or not 0 <= parameter <= 1:
            raise ValueError("Global path parameter outside [0,1].")
        piece = next(
            (piece for piece in self.pieces if parameter < piece.end_parameter), self.pieces[-1]
        )
        return piece.jet(parameter, offset_mm, self.constant_width)


def _controls(
    start: BendPose, end: BendPose, speed: float, radius: float, duration: float
) -> tuple[Vector3, ...]:
    """
    Interpolate two circular pose jets through order4, scaled to a local interval.
    """
    zero = Vector3(0, 0, 0)
    ends = []
    for pose, sign in ((start, 1), (end, -1)):
        normal = cross(pose.width, pose.tangent)
        jets = (
            zero.translated(pose.tangent, speed),
            zero.translated(normal, speed**2 / radius),
            zero.translated(pose.tangent, -(speed**3) / radius**2),
            zero.translated(normal, -(speed**4) / radius**3),
        )
        endpoint_controls = []
        for index in range(5):
            point, falling = pose.origin, 1
            for order in range(1, index + 1):
                falling *= 10 - order
                point = point.translated(
                    jets[order - 1], math.comb(index, order) * (sign * duration) ** order / falling
                )
            endpoint_controls.append(point)
        ends.append(tuple(endpoint_controls))
    return ends[0] + tuple(reversed(ends[1]))


def build_piecewise(case: EndpointCase) -> tuple[PiecewiseBend, dict[str, object]]:
    """
    Derive two inner poses from quarter-parameter circular endpoint advances.

    Preserve endpoint positions/order/first4global derivatives of the arc-jet
    baseline. The shared middle bridge must discover a regular bank field through
    its geometry; nominal cap radius is not a claim about its interior radius.
    """
    previous, metadata = distributed_controls(case)
    if metadata["nominal_turn_radians"] == 0:
        return PiecewiseBend((BendPiece(0, 1, previous),), case.start_width), dict(metadata)
    radius, speed = metadata["cap_radius_mm"], metadata["cap_speed_mm"]
    turn = metadata["nominal_turn_radians"] / 4
    poses = [BendPose(case.start, case.start_tangent, case.start_width)]
    for origin, tangent, width, sign in (
        (case.start, case.start_tangent, case.start_width, 1),
        (case.end, case.end_tangent, case.end_width, -1),
    ):
        normal = cross(width, tangent)
        inner_origin = origin.translated(tangent, sign * radius * math.sin(turn)).translated(
            normal, radius * (1 - math.cos(turn))
        )
        inner_tangent = unit(
            Vector3(0, 0, 0)
            .translated(tangent, math.cos(turn))
            .translated(normal, sign * math.sin(turn))
        )
        poses.append(BendPose(inner_origin, inner_tangent, width))
    poses.append(BendPose(case.end, case.end_tangent, case.end_width))
    intervals = (0.0, 0.25, 0.75, 1.0)
    pieces = tuple(
        BendPiece(a, b, _controls(start, end, speed, radius, b - a))
        for start, end, a, b in zip(poses, poses[1:], intervals, intervals[1:])
    )
    return PiecewiseBend(pieces), {**metadata, "poses": tuple(poses), "intervals": intervals}
