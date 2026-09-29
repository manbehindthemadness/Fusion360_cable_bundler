"""
Classify selected Fusion end guides without requiring ribbon geometry generation.
"""

from __future__ import annotations

from typing import Optional

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ....domain import CableEndShape


def end_guide_shape(entity: object) -> Optional[CableEndShape]:
    """
    Accept closed profiles or one physically open sketch curve.

    A closed sketch curve must be picked as its Fusion profile so closed-end
    behavior continues to use the profile and its enclosed area.
    """
    if adsk.fusion.Profile.cast(entity) is not None:
        return CableEndShape.CLOSED
    curve = adsk.fusion.SketchCurve.cast(entity)
    if curve is None:
        return None
    try:
        geometry = curve.geometry
        success, start, end = geometry.evaluator.getEndPoints()
        if success and start is not None and end is not None and start.distanceTo(end) > 1e-6:
            return CableEndShape.OPEN
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    return None


def read_end_guides(
    command_inputs: adsk.core.CommandInputs,
    input_id: str,
    unavailable: tuple[object, ...] = (),
    expected_shape: Optional[CableEndShape] = None,
) -> tuple[tuple[str, ...], CableEndShape]:
    """
    Read ordered, distinct guides whose open or closed shapes all match.
    """
    selection_input = adsk.core.SelectionCommandInput.cast(command_inputs.itemById(input_id))
    if selection_input is None or selection_input.selectionCount < 1:
        raise ValueError("Select at least one end guide profile or open sketch curve.")
    tokens: list[str] = []
    shape = expected_shape
    for index in range(selection_input.selectionCount):
        selection = selection_input.selection(index)
        entity = selection.entity if selection is not None else None
        selected_shape = end_guide_shape(entity)
        token = getattr(entity, "entityToken", None)
        if selected_shape is None or not isinstance(token, str) or not token.strip():
            raise ValueError(f"End guide selection {index + 1} is not a valid shape.")
        if shape is not None and selected_shape is not shape:
            raise ValueError("All end guides must be open curves or all must be closed profiles.")
        native = getattr(entity, "nativeObject", None) or entity
        if any(native == registered for registered in unavailable):
            raise ValueError(f"End guide selection {index + 1} is already registered.")
        if token in tokens:
            raise ValueError("Each end guide must reference distinct geometry.")
        shape = selected_shape
        tokens.append(token)
    assert shape is not None
    return tuple(tokens), shape
