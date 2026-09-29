"""
Support route endpoint anchoring and ordered control crossing placement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union
from uuid import UUID

from ...application import CableGroupRouteLeg
from ...domain import ControlStructure
from ...routing import (
    CableRouteInput,
    GateCapacityError,
    GateCapacityPolicy,
    GateFrame,
    RefineFrame,
    RoutePreview,
    TransitionLengths,
    Vector3,
    place_route_crossings,
)
from ...routing.geometry import cross, difference, magnitude, unit


@dataclass(frozen=True)
class _BranchAnchor:
    """
    Locate a solved parent sweep end and a point inside that sweep.
    """

    origin: Vector3
    interior: Vector3


def _terminal_branch_anchor(route: RoutePreview, *, at_start: bool) -> _BranchAnchor:
    """
    Recover one parent cap and its inward tangent from an exact or raw route.
    """
    if route.curves:
        curve = route.curves[0] if at_start else route.curves[-1]
        origin = curve.start if at_start else curve.end
        derivative = curve.derivative(0.0 if at_start else 1.0)
        inward = derivative if at_start else Vector3(-derivative.x, -derivative.y, -derivative.z)
        if magnitude(inward) <= 1e-9:
            inward = (
                difference(curve.end, curve.start)
                if at_start
                else difference(curve.start, curve.end)
            )
    else:
        origin = route.points[0] if at_start else route.points[-1]
        neighbor = route.points[1] if at_start else route.points[-2]
        inward = difference(neighbor, origin)
    return _BranchAnchor(origin, origin.translated(unit(inward), 1.0))


def _root_branch_anchors(
    legs: tuple[CableGroupRouteLeg, ...],
    routes: tuple[RoutePreview, ...],
) -> dict[tuple[UUID, UUID], _BranchAnchor]:
    """
    Follow conditioned main-route endpoints rather than unshifted guide centers.
    """
    anchors: dict[tuple[UUID, UUID], _BranchAnchor] = {}
    for leg, route in zip(legs, routes):
        if leg.start_connection_id is not None:
            anchors[leg.cable_group_id, leg.start_connection_id] = _terminal_branch_anchor(
                route, at_start=True
            )
        if leg.end_connection_id is not None:
            anchors[leg.cable_group_id, leg.end_connection_id] = _terminal_branch_anchor(
                route, at_start=False
            )
    return anchors


def leg_control_ids(
    leg: CableGroupRouteLeg,
    end_control_ids: dict[UUID, tuple[UUID, ...]],
) -> tuple[UUID, ...]:
    """
    Return end-owned and pathway controls in one leg's traversal order.
    """
    return (
        *(
            end_control_ids.get(leg.start_connection_id, ())
            if leg.start_connection_id is not None
            else ()
        ),
        *(step.control_id for step in leg.control_steps),
        *(
            reversed(end_control_ids.get(leg.end_connection_id, ()))
            if leg.end_connection_id is not None
            else ()
        ),
    )


def _place_control_crossings(
    cables: tuple[CableRouteInput, ...],
    frame: Union[GateFrame, RefineFrame],
    clearance_mm: float,
    preferred_points: tuple[Optional[Vector3], ...],
    notices: list[str],
) -> tuple[Vector3, ...]:
    """
    Preserve deterministic spacing and warn when it exceeds a gate aperture.
    """
    try:
        return place_route_crossings(cables, frame, clearance_mm, preferred_points)
    except GateCapacityError as error:
        notices.append(
            f"{error} Cable spacing is preserved, so routes may extend outside the aperture."
        )
        return place_route_crossings(
            cables,
            frame,
            clearance_mm,
            preferred_points,
            capacity_policy=GateCapacityPolicy.ALLOW_OVERFLOW,
        )


def _append_route_control(
    leg_label: str,
    cable_group_id: UUID,
    control_id: UUID,
    reversed_direction: bool,
    controls: dict[UUID, ControlStructure],
    frames: dict[UUID, Union[GateFrame, RefineFrame]],
    crossings: dict[tuple[UUID, UUID], Vector3],
    points: list[Vector3],
    normals: list[Vector3],
    transitions: list[TransitionLengths],
    point_control_ids: list[Optional[UUID]],
    soft_guide_indices: set[int],
) -> None:
    """
    Append one shared or end-owned routing control in traversal order.
    """
    control = controls.get(control_id)
    if control is None:
        raise RuntimeError(f"{leg_label} references a missing routing control.")
    frame = frames[control_id]
    control_point_index = len(points)
    points.append(crossings[control_id, cable_group_id])
    normals.append(cross(frame.u_direction, frame.v_direction))
    point_control_ids.append(control_id)
    soft_guide_indices.add(control_point_index)
    settings = control.interpolation
    transitions.append(
        TransitionLengths(
            settings.departure_mm if reversed_direction else settings.approach_mm,
            settings.approach_mm if reversed_direction else settings.departure_mm,
        )
    )
