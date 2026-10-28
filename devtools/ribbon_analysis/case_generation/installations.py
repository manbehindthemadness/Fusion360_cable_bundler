"""
Describe generic connector installations independently of any routing algorithm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude

from ..contracts import Targets

Family = Literal[
    "same-board", "parallel-boards", "perpendicular-boards", "reversed-connector", "board-to-panel"
]
FAMILIES: tuple[Family, ...] = (
    "same-board",
    "parallel-boards",
    "perpendicular-boards",
    "reversed-connector",
    "board-to-panel",
)


def validate_vector(vector: Vector3, *, direction: bool = False) -> None:
    """
    Reject nonnumeric coordinates and,for directions,nonunit axes without repairing them.
    """
    if not isinstance(vector, Vector3) or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in (vector.x, vector.y, vector.z)
    ):
        raise ValueError("Installation vectors need finite numeric coordinates.")
    if direction and abs(magnitude(vector) - 1) > 1e-8:
        raise ValueError("Installation directions must be unit vectors.")


@dataclass(frozen=True)
class Connector:
    """
    Freeze an outward cable departure and ordered width separately from mating.

    Mount points lie on an idealized board/panel plane. Mating directions point
    out of the mount;they need not equal cable departure directions. Width points
    from the first conductor toward the last,never an unordered plane axis.
    Housing dimensions,keepouts and manufacturer bend limits are not modeled.
    """

    exit_point: Vector3
    exit_direction: Vector3
    width_direction: Vector3
    mount_point: Vector3
    mount_normal: Vector3
    mating_direction: Vector3
    mount_kind: Literal["board", "panel"]

    def __post_init__(self) -> None:
        """
        Validate the declared departure frame and its outward mounting relationship.
        """
        for point in (self.exit_point, self.mount_point):
            validate_vector(point)
        for axis in (
            self.exit_direction,
            self.width_direction,
            self.mount_normal,
            self.mating_direction,
        ):
            validate_vector(axis, direction=True)
        if self.mount_kind not in ("board", "panel"):
            raise ValueError("Connector mounts must be boards or panels.")
        if (
            max(
                abs(dot(self.exit_direction, self.width_direction)),
                abs(dot(self.mating_direction, self.width_direction)),
            )
            > 1e-8
        ):
            raise ValueError("Ordered width must be perpendicular to departure and mating.")
        if (
            dot(difference(self.exit_point, self.mount_point), self.mount_normal) <= 0
            or dot(self.exit_direction, self.mount_normal) < -1e-8
            or dot(self.mating_direction, self.mount_normal) <= 0
        ):
            raise ValueError("Connector departure must lie outside its mounting plane.")


@dataclass(frozen=True)
class Installation:
    """
    Preserve assembly context without claiming a known-feasible route or keepout audit.

    The axis-aligned room is a declared inspection envelope,not a solver constraint.
    These generic engineering fixtures are not calibrated connector products.
    """

    family: Family
    start: Connector
    end: Connector
    room_min: Vector3
    room_max: Vector3
    feasibility: Literal["unknown"] = "unknown"

    def __post_init__(self) -> None:
        """
        Reject malformed context and inconsistent named mounting relationships.
        """
        if self.family not in FAMILIES or self.feasibility != "unknown":
            raise ValueError("Installation needs a known family and unknown feasibility.")
        if not isinstance(self.start, Connector) or not isinstance(self.end, Connector):
            raise ValueError("Installation needs two frozen connectors.")
        for point in (self.room_min, self.room_max):
            validate_vector(point)
        if any(
            getattr(self.room_min, axis) >= getattr(self.room_max, axis) for axis in ("x", "y", "z")
        ):
            raise ValueError("Installation room must have positive extent on every axis.")
        start, end = self.start, self.end
        expected_dot = (
            1
            if self.family in ("same-board", "reversed-connector")
            else -1
            if self.family == "parallel-boards"
            else 0
        )
        if abs(dot(start.mount_normal, end.mount_normal) - expected_dot) > 1e-8:
            raise ValueError("Mount normals disagree with the installation family.")
        if start.mount_kind != "board" or end.mount_kind != (
            "panel" if self.family == "board-to-panel" else "board"
        ):
            raise ValueError("Mount kinds disagree with the installation family.")
        if (
            self.family in ("same-board", "reversed-connector")
            and abs(dot(difference(end.mount_point, start.mount_point), start.mount_normal)) > 1e-8
        ):
            raise ValueError("Same-board connectors must share their mounting plane.")

    def validate_targets(self, targets: Targets) -> None:
        """
        Check exact target correspondence and full terminal widths inside the room.

        Both connector departures point outward. A start-to-end path therefore
        arrives opposite the end connector's departure;pin order is never flipped.
        """
        end_arrival = Vector3(
            -self.end.exit_direction.x, -self.end.exit_direction.y, -self.end.exit_direction.z
        )
        if (
            targets.start != self.start.exit_point
            or targets.end != self.end.exit_point
            or targets.start_tangent != self.start.exit_direction
            or targets.end_tangent != end_arrival
            or targets.start_width != self.start.width_direction
            or targets.end_width != self.end.width_direction
        ):
            raise ValueError("Installation connectors disagree with frozen targets.")
        half_width = targets.lines * targets.diameter_mm / 2
        for connector in (self.start, self.end):
            for offset in (-half_width, half_width):
                point = connector.exit_point.translated(connector.width_direction, offset)
                if any(
                    not getattr(self.room_min, axis)
                    <= getattr(point, axis)
                    <= getattr(self.room_max, axis)
                    for axis in ("x", "y", "z")
                ):
                    raise ValueError("Full terminal widths must fit the declared room.")
