"""
Sample coupled board/panel relationships without consulting a solver or fitted path.
"""

from __future__ import annotations

import hashlib
import math
import random

from cable_bundler.routing.geometry import Vector3, unit

from ..contracts import Targets
from .installations import FAMILIES, Connector, Installation
from .models import Case, RandomBounds


def installation_case(seed: int, index: int, bounds: RandomBounds) -> Case:
    """
    Freeze one generic installation with a size-independent random substream.

    Families cycle evenly;dimensions,board spacing,offset,connector heading and
    assembly yaw vary independently of solver outcomes. Ranges are engineering
    test assumptions,not manufacturer limits. No witness route is supplied.
    """
    digest = hashlib.sha256(f"ribbon-installations-v1:{seed}:{index}".encode()).digest()
    rng = random.Random(int.from_bytes(digest, "big"))
    family = FAMILIES[(index - 1) % len(FAMILIES)]
    counts = tuple(
        n
        for n in (6, 8, 10, 14, 16, 20, 26, 34, 40, 50, 60, 64)
        if bounds.minimum_lines <= n <= bounds.maximum_lines
    )
    lines = (
        rng.choice(counts) if counts else rng.randint(bounds.minimum_lines, bounds.maximum_lines)
    )
    diameter = math.exp(
        rng.uniform(math.log(bounds.minimum_diameter_mm), math.log(bounds.maximum_diameter_mm))
    )
    width = lines * diameter
    chord = width * math.exp(
        rng.uniform(math.log(bounds.minimum_chord_widths), math.log(bounds.maximum_chord_widths))
    )
    height = rng.uniform(0.2, 0.5) * width
    end_height = rng.uniform(0.2, 0.5) * width
    up, right, across = Vector3(0, 0, 1), Vector3(1, 0, 0), Vector3(0, 1, 0)
    start_point = Vector3(0, 0, height)
    start_exit, end_exit = up, up
    end_normal = up
    start_width, end_width = across, across
    heading = math.radians(rng.choice((0, 0, 0, -45, 45, -90, 90, 180)))
    if family in ("same-board", "reversed-connector"):
        direction = unit(Vector3(1, rng.uniform(-0.75, 0.75), 0))
        end_height = height
        if family == "reversed-connector":
            end_width = Vector3(0, -1, 0)
        elif rng.choice((False, True)):
            start_exit, end_exit = right, Vector3(-1, 0, 0)
        else:
            end_width = Vector3(math.sin(heading), math.cos(heading), 0)
    elif family == "parallel-boards":
        direction = unit(Vector3(rng.uniform(-0.75, 0.75), rng.uniform(-0.5, 0.5), 1))
        end_normal = end_exit = Vector3(0, 0, -1)
        end_width = Vector3(math.sin(heading), math.cos(heading), 0)
    else:
        direction = unit(Vector3(rng.uniform(0.5, 1.5), rng.uniform(-0.5, 0.5), 1))
        end_normal = end_exit = Vector3(-1, 0, 0)
        end_width = Vector3(0, math.cos(heading), math.sin(heading))
        if family == "board-to-panel" and rng.choice((False, True)):
            start_exit = right
    end_point = start_point.translated(direction, chord)
    yaw = rng.uniform(-math.pi, math.pi)

    def rotate(vector: Vector3) -> Vector3:
        """
        Turn the whole assembly together,preserving every mount relationship.
        """
        return Vector3(
            math.cos(yaw) * vector.x - math.sin(yaw) * vector.y,
            math.sin(yaw) * vector.x + math.cos(yaw) * vector.y,
            vector.z,
        )

    start = Connector(
        rotate(start_point),
        rotate(start_exit),
        rotate(start_width),
        Vector3(0, 0, 0),
        up,
        up,
        "board",
    )
    end = Connector(
        rotate(end_point),
        rotate(end_exit),
        rotate(end_width),
        rotate(end_point.translated(end_normal, -end_height)),
        rotate(end_normal),
        rotate(end_normal),
        "panel" if family == "board-to-panel" else "board",
    )
    margin = width * rng.uniform(1.5, 3)
    coordinates = (
        (start.exit_point.x, end.exit_point.x),
        (start.exit_point.y, end.exit_point.y),
        (start.exit_point.z, end.exit_point.z),
    )
    room_min = Vector3(*(min(first, last) - margin for first, last in coordinates))
    room_max = Vector3(*(max(first, last) + margin for first, last in coordinates))
    installation = Installation(family, start, end, room_min, room_max)
    identifier = f"I{index:03}"
    targets = Targets.capture(
        Targets(
            identifier + " " + family,
            start.exit_point,
            end.exit_point,
            start.exit_direction,
            Vector3(-end.exit_direction.x, -end.exit_direction.y, -end.exit_direction.z),
            start.width_direction,
            end.width_direction,
            lines,
            diameter,
        )
    )
    return Case(
        identifier,
        "random",
        targets,
        (),
        "installation-v1/" + family,
        "Unknown feasibility;generic assembly assumptions,not a calibrated connector product. "
        "Mount planes/room are context only;housing clearance and required straight lead are unmodeled. "
        "Width=lines*diameter is the existing geometry model,not an independent IDC pitch specification. "
        "No solver-conditioned rejection or witness initialization.",
        installation,
    )
