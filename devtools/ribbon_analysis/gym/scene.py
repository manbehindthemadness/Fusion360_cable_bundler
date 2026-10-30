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
from .primitives import PHI, Box, Dodecahedron

ZONES = tuple(zone for zone in product((-1, 0, 1), repeat=3) if zone != (0, 0, 0))
FACES = tuple(f"Face {number + 1:02}" for number in range(12))


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
    void_percent: float = 300.0
    zone_percent: float = 300.0

    def __post_init__(self) -> None:
        """
        Validate finite input dimensions before any scene or host mutation.
        """
        _integer(self.seed, 0, 2**32 - 1)
        _integer(self.lines, 1, 128)
        for value in (self.diameter_mm, self.void_percent, self.zone_percent):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError("Dimensions must be finite numbers.")
        if self.diameter_mm <= 0 or self.void_percent < 300 or self.zone_percent <= 0:
            raise ValueError(
                "Diameter and zone depth must be positive; central void side must be at least300% of width."
            )
        if not math.isfinite(self.extent_mm):
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
        Return the central void side in millimeters.
        """
        return self.width_mm * (self.void_percent / 100)

    @property
    def zone_mm(self) -> float:
        """
        Return outer zone depth as a percentage of nominal ribbon width.
        """
        return self.width_mm * (self.zone_percent / 100)

    @property
    def extent_mm(self) -> float:
        """
        Return the complete gym side, including both outer zone layers.
        """
        return self.side_mm + 2 * self.zone_mm


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
        _integer(self.face, 0, 11)
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

    def zone_box(self, zone: int) -> Box:
        """
        Return a cell with configurable outer depth and central-band dimensions.
        """
        _integer(zone, 0, 25)
        side, depth = self.config.side_mm, self.config.zone_mm
        indices = ZONES[zone]
        return Box(
            Vector3(*(coordinate * (side + depth) / 2 for coordinate in indices)),
            (
                depth if indices[0] else side,
                depth if indices[1] else side,
                depth if indices[2] else side,
            ),
        )

    def solid(self, zone: int) -> Dodecahedron:
        """
        Seat a regular solid against every inward cell boundary nearest the void.

        Nonzero zone axes touch their inner barrier with zero AABB gap. Free
        tangential coordinates retain seeded variation. Edge/corner cells snug
        against two/three inward planes without entering the central void.
        """
        bounds = self.zone_box(zone)
        rng = random.Random(f"ribbon-gym-dodecahedron-v2:{self.config.seed}:{zone}")
        scale = min(bounds.size) * rng.uniform(0.65, 0.85) / (2 * PHI)
        reach = scale * PHI
        center = Vector3(
            *(
                coordinate * (self.config.side_mm / 2 + reach)
                if coordinate
                else rng.uniform(-self.config.side_mm / 2 + reach, self.config.side_mm / 2 - reach)
                for coordinate in ZONES[zone]
            )
        )
        return Dodecahedron(center, scale)

    def pose(self, goal: Goal) -> tuple[Vector3, Vector3, Vector3]:
        """
        Derive the attachment center, outward departure and ordered width from its face.
        """
        origin, normal, across, _ = self.solid(goal.zone).face(goal.face)
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
            "schema": "ribbon-gym-preview-v2",
            "config": asdict(self.config),
            "width_mm": self.config.width_mm,
            "side_mm": self.config.side_mm,
            "zone_mm": self.config.zone_mm,
            "extent_mm": self.config.extent_mm,
            "a": asdict(self.a),
            "b": asdict(self.b),
            "zones": [",".join(map(str, zone)) for zone in ZONES],
            "faces": FACES,
            "solids": [
                {"kind": "regular_dodecahedron", **asdict(self.solid(goal.zone))}
                for goal in (self.a, self.b)
            ],
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
        Goal(a, rng.randrange(12), rng.randrange(4)),
        Goal(b, rng.randrange(12), rng.randrange(4)),
    )
