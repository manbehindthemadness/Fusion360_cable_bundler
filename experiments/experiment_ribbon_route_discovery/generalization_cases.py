"""
Freeze prospective boundary challenges independently of solver-generated shapes.

Fresh cases vary complete endpoint geometry and dimensions;reserved cases remain
unexecuted until an explicitly frozen later validation phase. Names are reporting
identities and must never select routing coordinates or acceptance rules.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import Vector3, cross
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase


def _case(
    name: str,
    lines: int,
    diameter: float,
    end: tuple[float, float, float],
    yaw: float,
    pitch: float,
    roll: float,
) -> EndpointCase:
    """
    Construct perpendicular terminal axes from fixed yaw,pitch and ordered roll.
    """
    yaw, pitch, roll = (math.radians(v) for v in (yaw, pitch, roll))
    tangent = Vector3(
        math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)
    )
    width = Vector3(-math.sin(yaw), math.cos(yaw), 0)
    normal = cross(tangent, width)
    terminal_width = Vector3(
        width.x * math.cos(roll) + normal.x * math.sin(roll),
        width.y * math.cos(roll) + normal.y * math.sin(roll),
        width.z * math.cos(roll) + normal.z * math.sin(roll),
    )
    return EndpointCase(
        name,
        Vector3(0, 0, 0),
        Vector3(*end),
        Vector3(1, 0, 0),
        tangent,
        Vector3(0, 1, 0),
        terminal_width,
        lines,
        diameter,
    )


def fresh() -> tuple[EndpointCase, ...]:
    """
    Return eight frozen straight,gentle,lateral,return and spatial-roll challenges.
    """
    return (
        _case("G01 straight", 7, 1.0, (80, 0, 0), 0, 0, 0),
        _case("G02 gentle rise", 13, 1.0, (100, 0, 24), 0, 12, 0),
        _case("G03 lateral quarter", 13, 1.0, (60, 40, 8), 90, 0, 90),
        _case("G04 compact skew", 5, 1.25, (30, -22, 14), -55, 8, -45),
        _case("G05 spatial quarter", 24, 0.8, (85, -25, 35), 14, -9, 90),
        _case("G06 opposed return", 9, 1.5, (12, 38, 22), 180, 0, 0),
        _case("G07 wide half roll", 32, 0.75, (120, 22, -30), 0, 19, 180),
        _case("G08 oblique negative roll", 19, 1.2, (70, -30, -18), 24, -13, -135),
    )


def reserved() -> tuple[EndpointCase, ...]:
    """
    Retain four different unexamined boundary conditions for later validation.
    """
    return (
        _case("H01 rising lateral", 11, 0.9, (56, 33, 28), 58, 24, -80),
        _case("H02 descending wide", 28, 1.1, (105, -48, -27), -32, -18, 150),
        _case("H03 narrow return", 4, 1.8, (16, -42, 31), -165, 14, 35),
        _case("H04 long oblique", 17, 0.7, (145, 19, 54), 22, 30, -110),
    )
