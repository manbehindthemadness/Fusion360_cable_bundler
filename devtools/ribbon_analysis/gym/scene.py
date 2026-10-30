"""
Generate a central void and face-mounted targets without constructing a cable path.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, replace
from itertools import product
from typing import Any

from cable_bundler.routing.geometry import Vector3, cross

from ..contracts import Targets

ZONES = tuple(zone for zone in product((-1, 0, 1), repeat=3) if zone != (0, 0, 0))
FACES = ("+X", "-X", "+Y", "-Y", "+Z", "-Z")
AXES = (Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1))


def _integer(value: Any, minimum: int, maximum: int) -> int:
    """
    Reject booleans, nonintegers and unsupported preview ranges.
    """
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"Expected an integer in {minimum}..{maximum}.")
    return value


@dataclass(frozen=True)
class Config:
    """
    Declare preview dimensions; width is the existing nominal lines-times-diameter.

    The three-width minimum sizes the central empty cube only. It is not a
    routing constraint, reachability test, collision certificate or solver bound.
    """

    seed: int = 20261030
    lines: int = 3
    diameter_mm: float = 1.5
    void_widths: float = 3.0

    def __post_init__(self) -> None:
        """
        Validate finite input dimensions before any scene or host mutation.
        """
        _integer(self.seed, 0, 2**32 - 1)
        _integer(self.lines, 1, 128)
        for value in (self.diameter_mm, self.void_widths):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError("Dimensions must be finite numbers.")
        if self.diameter_mm <= 0 or self.void_widths < 3:
            raise ValueError(
                "Diameter must be positive; central void side must be at least3widths."
            )
        if not math.isfinite(self.side_mm * 3):
            raise ValueError("Preview dimensions overflow.")

    @property
    def width_mm(self) -> float:
        """
        Return nominal cable width without adding a new profile or padding policy.
        """
        return self.lines * self.diameter_mm

    @property
    def side_mm(self) -> float:
        """
        Return the central cube side and each surrounding zone's side.
        """
        return self.width_mm * self.void_widths


@dataclass(frozen=True)
class Box:
    """
    Represent an axis-aligned virtual goal solid, with no native BRep dependency.
    """

    center: Vector3
    size: tuple[float, float, float]

    def face(self, index: int) -> tuple[Vector3, Vector3, Vector3, tuple[Vector3, ...]]:
        """
        Return face center, outward normal, ordered across axis and four corners.
        """
        _integer(index, 0, 5)
        axis, sign = index // 2, 1 if index % 2 == 0 else -1
        normal = Vector3(0, 0, 0).translated(AXES[axis], sign)
        across = AXES[(axis + 1) % 3]
        up = cross(normal, across)
        origin = self.center.translated(normal, self.size[axis] / 2)
        corners = tuple(
            origin.translated(across, a * self.size[(axis + 1) % 3] / 2).translated(
                up, b * self.size[(axis + 2) % 3] / 2
            )
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))
        )
        return origin, normal, across, corners


@dataclass(frozen=True)
class Goal:
    """
    Preserve selected zone, face and ordered in-face connector orientation.
    """

    zone: int
    face: int
    roll: int = 0

    def __post_init__(self) -> None:
        """
        Validate stable zone/face identifiers and quarter-turn in-face orientation.
        """
        _integer(self.zone, 0, 25)
        _integer(self.face, 0, 5)
        _integer(self.roll, 0, 3)


@dataclass(frozen=True)
class Scene:
    """
    Hold only a reproducible environment and endpoint selections, never an interior route.
    """

    config: Config
    a: Goal
    b: Goal

    def __post_init__(self) -> None:
        """
        Require two distinct valid goal zones for this visual preview.
        """
        if not isinstance(self.config, Config) or not all(
            isinstance(g, Goal) for g in (self.a, self.b)
        ):
            raise ValueError("Scene needs preview configuration and two goals.")
        if self.a.zone == self.b.zone:
            raise ValueError("Select two different goal zones.")

    def box(self, zone: int) -> Box:
        """
        Sample one solid wholly inside its zone with a seed independent of selections.
        """
        _integer(zone, 0, 25)
        rng = random.Random(f"ribbon-gym-preview-v1:{self.config.seed}:{zone}")
        side = self.config.side_mm
        extents = tuple(side * rng.uniform(0.4, 0.75) for _ in range(3))
        size = (extents[0], extents[1], extents[2])
        center = Vector3(
            *(
                coordinate * side + rng.uniform(-(side - extent) / 2, (side - extent) / 2)
                for coordinate, extent in zip(ZONES[zone], size)
            )
        )
        return Box(center, size)

    def pose(self, goal: Goal) -> tuple[Vector3, Vector3, Vector3]:
        """
        Derive the attachment center, outward departure and ordered width from its face.
        """
        origin, normal, across, _ = self.box(goal.zone).face(goal.face)
        up = cross(normal, across)
        widths = (
            across,
            up,
            Vector3(0, 0, 0).translated(across, -1),
            Vector3(0, 0, 0).translated(up, -1),
        )
        return origin, normal, widths[goal.roll]

    @property
    def targets(self) -> Targets:
        """
        Expose endpoints for future use; arrival is opposite the end face's departure.
        """
        a, na, wa = self.pose(self.a)
        b, nb, wb = self.pose(self.b)
        return Targets.capture(
            Targets(
                "Rubik gym preview",
                a,
                b,
                na,
                Vector3(0, 0, 0).translated(nb, -1),
                wa,
                wb,
                self.config.lines,
                self.config.diameter_mm,
            )
        )

    def choose(self, role: str, goal: Goal) -> Scene:
        """
        Replace one endpoint selection without moving other solids or inventing a route.
        """
        if role not in ("a", "b"):
            raise ValueError("Choose goal a or b.")
        return replace(self, **{role: goal})

    def payload(self) -> dict[str, Any]:
        """
        Serialize the same frozen scene and drawing primitives for Fusion and canvas.
        """
        from .strokes import drawing

        return {
            "schema": "ribbon-gym-preview-v1",
            "config": asdict(self.config),
            "width_mm": self.config.width_mm,
            "side_mm": self.config.side_mm,
            "a": asdict(self.a),
            "b": asdict(self.b),
            "zones": [",".join(map(str, zone)) for zone in ZONES],
            "faces": FACES,
            "solids": [asdict(self.box(goal.zone)) for goal in (self.a, self.b)],
            "targets": asdict(self.targets),
            "drawing": drawing(self),
            "scope": "Endpoint layout only. No cable path, solver run or physical feasibility judgement. Routing boundary and planar gym are deferred.",
        }


def generate(config: Config | None = None) -> Scene:
    """
    Select two zones and faces dynamically without consulting any routing procedure.
    """
    config = config or Config()
    rng = random.Random(f"ribbon-gym-selections-v1:{config.seed}")
    a, b = rng.sample(range(26), 2)
    return Scene(
        config,
        Goal(a, rng.randrange(6), rng.randrange(4)),
        Goal(b, rng.randrange(6), rng.randrange(4)),
    )
