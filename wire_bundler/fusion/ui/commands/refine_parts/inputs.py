"""Geometry, radius, and transform input conversion for refine commands."""

from __future__ import annotations

from typing import Optional

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from .....domain import RefineGeometry
from .....routing import Vector3
from .....routing.geometry import cross, unit
from ....refine_graphics import (
    REFINE_SPINE_ENTITY_ID,
    PathwaySpine,
    RefinePlacement,
    place_refine,
)
from ...constants import REFINE_RADIUS_INPUT_ID, REFINE_SPINE_INPUT_ID, REFINE_TRANSFORM_INPUT_ID

MINIMUM_REFINE_RADIUS_MM = 0.5


def refine_spine_selection_point_mm(selection: object) -> Optional[Vector3]:
    """
    Convert a valid Custom Graphics spine selection point to millimeters.
    """
    entity = getattr(selection, "entity", None)
    point: Optional[adsk.core.Point3D] = getattr(selection, "point", None)
    if getattr(entity, "id", None) != REFINE_SPINE_ENTITY_ID or point is None:
        return None
    return Vector3(point.x * 10.0, point.y * 10.0, point.z * 10.0)


def _selected_refine_point_mm(
    selection_input: Optional[adsk.core.SelectionCommandInput],
) -> Optional[Vector3]:
    """
    Read a selected spine point, tolerating Fusion-invalidated preview entities.
    """
    if selection_input is None or selection_input.selectionCount != 1:
        return None
    try:
        selection = selection_input.selection(0)
    except (AttributeError, RuntimeError, TypeError):
        return None
    return refine_spine_selection_point_mm(selection)


def read_refine_placement(
    command_inputs: adsk.core.CommandInputs,
    spine: PathwaySpine,
) -> RefinePlacement:
    """
    Read a selected spine point and marker radius in millimeters.
    """
    selection_input = adsk.core.SelectionCommandInput.cast(
        command_inputs.itemById(REFINE_SPINE_INPUT_ID)
    )
    radius_input = adsk.core.DistanceValueCommandInput.cast(
        command_inputs.itemById(REFINE_RADIUS_INPUT_ID)
    )
    if selection_input is None or selection_input.selectionCount != 1:
        raise ValueError("Select one point on the pathway spine.")
    radius_mm = read_refine_radius_mm(radius_input)
    selected_point = _selected_refine_point_mm(selection_input)
    if selected_point is None:
        raise ValueError("Select a point on the displayed pathway spine.")
    return place_refine(spine, selected_point, radius_mm)


def add_refine_radius_input(
    command_inputs: adsk.core.CommandInputs,
    initial_radius_mm: float = MINIMUM_REFINE_RADIUS_MM,
) -> adsk.core.DistanceValueCommandInput:
    """
    Add a radius manipulator that starts at or above the supported minimum.
    """
    clamped_radius_mm = max(float(initial_radius_mm), MINIMUM_REFINE_RADIUS_MM)
    radius_input = command_inputs.addDistanceValueCommandInput(
        REFINE_RADIUS_INPUT_ID,
        "Marker Radius",
        adsk.core.ValueInput.createByString(f"{clamped_radius_mm:g} mm"),
    )
    if radius_input is None:
        raise RuntimeError("Fusion could not create the refine-radius input.")
    radius_input.minimumValue = MINIMUM_REFINE_RADIUS_MM / 10.0
    radius_input.isMinimumValueInclusive = True
    return radius_input


def read_refine_radius_mm(
    radius_input: Optional[adsk.core.DistanceValueCommandInput],
) -> float:
    """
    Read a valid Fusion distance and clamp transient subminimum values.
    """
    if radius_input is None or not radius_input.isValidExpression:
        raise ValueError("Refine marker radius must be valid.")
    return max(radius_input.value * 10.0, MINIMUM_REFINE_RADIUS_MM)


def _refine_geometry_transform(geometry: RefineGeometry) -> adsk.core.Matrix3D:
    """
    Convert saved millimeter geometry into a centimeter-based Fusion triad.
    """
    u_direction = Vector3(*geometry.u_direction)
    v_direction = Vector3(*geometry.v_direction)
    tangent = unit(cross(u_direction, v_direction))
    transform = adsk.core.Matrix3D.create()
    if transform is None or not transform.setWithCoordinateSystem(
        adsk.core.Point3D.create(*(value / 10.0 for value in geometry.origin_mm)),
        adsk.core.Vector3D.create(*geometry.u_direction),
        adsk.core.Vector3D.create(*geometry.v_direction),
        adsk.core.Vector3D.create(tangent.x, tangent.y, tangent.z),
    ):
        raise RuntimeError("Fusion could not orient the refine transform controls.")
    return transform


def add_refine_transform_input(
    command_inputs: adsk.core.CommandInputs,
    geometry: RefineGeometry,
) -> adsk.core.TriadCommandInput:
    """
    Add a triad and explicitly initialize its writable world transform.

    Fusion can ignore the initial matrix passed to ``addTriadCommandInput``;
    assigning the same matrix to ``transform`` prevents the dialog and the first
    manipulation from falling back to the global origin.
    """
    initial_transform = _refine_geometry_transform(geometry)
    triad = command_inputs.addTriadCommandInput(
        REFINE_TRANSFORM_INPUT_ID,
        initial_transform,
    )
    if triad is None:
        raise RuntimeError("Fusion could not create the refine transform controls.")
    triad.transform = initial_transform
    return triad


def read_edited_refine_geometry(command_inputs: adsk.core.CommandInputs) -> RefineGeometry:
    """
    Read a rigid triad and marker radius as persistent millimeter geometry.
    """
    triad = adsk.core.TriadCommandInput.cast(command_inputs.itemById(REFINE_TRANSFORM_INPUT_ID))
    radius = adsk.core.DistanceValueCommandInput.cast(
        command_inputs.itemById(REFINE_RADIUS_INPUT_ID)
    )
    if triad is None or not triad.isValidExpressions:
        raise ValueError("Refine position and rotation must be valid.")
    radius_mm = read_refine_radius_mm(radius)
    origin, u_direction, v_direction, _tangent = triad.transform.getAsCoordinateSystem()
    return RefineGeometry(
        origin_mm=(origin.x * 10.0, origin.y * 10.0, origin.z * 10.0),
        u_direction=(u_direction.x, u_direction.y, u_direction.z),
        v_direction=(v_direction.x, v_direction.y, v_direction.z),
        display_radius_mm=radius_mm,
    )
