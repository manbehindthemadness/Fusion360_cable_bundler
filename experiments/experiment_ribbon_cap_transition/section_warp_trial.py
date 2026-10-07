"""
Transfer measured local edge-frame tilts to a fixed twisted calibration scaffold.

This imposes section orientations for diagnosis; the transferred directions are
not claimed to be derivatives of the calibration scaffold's physical edge curves.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import Vector3, unit
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame

from .section_flex import FlexSection, flex_section


def scaled_direction(local: tuple[float, ...], scale: float) -> Vector3:
    """
    Scale the edge-normal tilt angle from local +Z, preserving its azimuth.
    """
    if len(local) != 3 or not all(math.isfinite(value) for value in (*local, scale)):
        raise ValueError("Expected finite three-dimensional direction and scale.")
    if not 0 <= scale <= 1:
        raise ValueError("Warp scale must lie between zero and one.")
    normal = unit(Vector3(*local))
    radial = math.hypot(normal.x, normal.y)
    if radial <= 1e-10:
        if normal.z < 0:
            raise ValueError("Antiparallel edge normal has no unique tilt azimuth.")
        return Vector3(0, 0, 1)
    angle = math.atan2(radial, normal.z) * scale
    return Vector3(
        normal.x / radial * math.sin(angle), normal.y / radial * math.sin(angle), math.cos(angle)
    )


def imposed_flex(
    frame: RibbonFrame,
    local_minus: tuple[float, ...],
    local_plus: tuple[float, ...],
    scale: float,
    *,
    terminal: bool = False,
) -> FlexSection:
    """
    Keep the scaffold's center, bank and three anchor positions fixed at every scale.

    Only the relative edge-frame tilts vary. Exact planar terminal caps are retained.
    """
    tangents = []
    for local in (local_minus, local_plus):
        direction = scaled_direction(local, scale)
        tangents.append(
            Vector3(
                frame.width.x * direction.x
                + frame.thickness.x * direction.y
                + frame.tangent.x * direction.z,
                frame.width.y * direction.x
                + frame.thickness.y * direction.y
                + frame.tangent.y * direction.z,
                frame.width.z * direction.x
                + frame.thickness.z * direction.y
                + frame.tangent.z * direction.z,
            )
        )
    return flex_section(frame, tangents[0], tangents[1], terminal=terminal)
