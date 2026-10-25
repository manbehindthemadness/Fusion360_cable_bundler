"""
Set one global curve's travel scale from nominal bending plus explicit banking.

This is an allocation heuristic, not physical minimum length or an equilibrium
solution. Actual arclength and all geometry rules remain separate measurements.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit

from .distributed_bend import distributed_controls
from .endpoint_first import EndpointCase
from .piecewise_bend import BendPose, _controls


def _angle(left: Vector3, right: Vector3) -> float:
    """
    Measure the principal angle between validated ordered unit directions.
    """
    return math.acos(max(-1.0, min(1.0, dot(left, right))))


def travel_controls(case: EndpointCase) -> tuple[tuple[Vector3, ...], dict[str, object]]:
    """
    Add envelope-radius times bank demand to the baseline nominal travel scale.

    The natural bend-plane width follows start-tangent cross end-tangent; parallel
    tangents use start-tangent cross chord, or the start width when both vanish.
    Bank demand is entry width->plane plus plane->exit width, without modulo180
    erasure. Preserve baseline cap radius and circular jets, increasing their speed
    from the combined travel estimate. A zero-bank control returns its exact prior
    polynomial. Endpoints/order stay fixed; no search, extra winding or repairs.
    """
    previous, metadata = distributed_controls(case)
    base = metadata["cap_speed_mm"]
    axis = cross(case.start_tangent, case.end_tangent)
    if magnitude(axis) <= 1e-8:
        axis = cross(case.start_tangent, unit(difference(case.end, case.start)))
    natural_width = unit(axis) if magnitude(axis) > 1e-8 else case.start_width
    if metadata["nominal_turn_radians"] == 0:
        entry, exit_angle = 0.0, 0.0
    else:
        entry = _angle(case.start_width, natural_width)
        exit_angle = _angle(natural_width, case.end_width)
    allowance = metadata["minimum_envelope_radius_mm"] * (entry + exit_angle)
    nominal = base + allowance
    result_metadata: dict[str, object] = {
        **metadata,
        "base_travel_scale_mm": base,
        "bank_entry_radians": entry,
        "bank_exit_radians": exit_angle,
        "additional_bank_allowance_mm": allowance,
        "nominal_travel_scale_mm": nominal,
        "cap_speed_mm": nominal,
        "natural_bend_width": natural_width,
    }
    if allowance == 0:
        return previous, result_metadata
    start = BendPose(case.start, case.start_tangent, case.start_width)
    end = BendPose(case.end, case.end_tangent, case.end_width)
    return _controls(start, end, nominal, metadata["cap_radius_mm"], 1), result_metadata
