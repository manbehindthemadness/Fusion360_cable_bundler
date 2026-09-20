"""Selection placement and preview helpers for add-refine commands."""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from .....routing import Vector3
from ....refine_graphics import (
    RefinePlacement,
    draw_candidate_refine,
    draw_pathway_spine,
    place_refine,
)
from ...constants import REFINE_RADIUS_INPUT_ID, REFINE_SPINE_INPUT_ID
from ...support import (
    _require_active_design,
)
from .inputs import read_refine_radius_mm, refine_spine_selection_point_mm
from .types import RefineCommandState


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


def update_refine_placement(
    state: RefineCommandState,
    command_inputs: adsk.core.CommandInputs,
    *,
    position_manipulator: bool = True,
) -> None:
    """
    Capture selection and radius inputs without modifying document graphics.
    """
    radius_input = adsk.core.DistanceValueCommandInput.cast(
        command_inputs.itemById(REFINE_RADIUS_INPUT_ID)
    )
    if radius_input is None:
        raise RuntimeError("Refine radius input is unavailable.")
    selection_input = adsk.core.SelectionCommandInput.cast(
        command_inputs.itemById(REFINE_SPINE_INPUT_ID)
    )
    if selection_input is not None and selection_input.selectionCount == 1:
        selected_point_mm = _selected_refine_point_mm(selection_input)
        if selected_point_mm is None:
            selected_point_mm = state.preselected_point_mm
        if selected_point_mm is None:
            radius_input.isEnabled = False
            radius_input.isVisible = False
            return
        state.placement = place_refine(
            state.spine,
            selected_point_mm,
            read_refine_radius_mm(radius_input),
        )
    elif state.placement is not None:
        radius_mm = read_refine_radius_mm(radius_input)
        state.placement = replace(
            state.placement,
            geometry=replace(
                state.placement.geometry,
                display_radius_mm=radius_mm,
            ),
        )
    else:
        radius_input.isEnabled = False
        radius_input.isVisible = False
        return
    placement = state.placement
    if placement is None:
        raise RuntimeError("Refine placement state was not captured.")
    show_refine_radius_input(radius_input, placement, position_manipulator=position_manipulator)


def show_refine_radius_input(
    radius_input: adsk.core.DistanceValueCommandInput,
    placement: RefinePlacement,
    *,
    position_manipulator: bool = True,
) -> None:
    """
    Reveal the radius control and optionally position its canvas manipulator.
    """
    radius_input.isEnabled = True
    radius_input.isVisible = True
    if not position_manipulator:
        return
    origin = placement.geometry.origin_mm
    direction = placement.geometry.u_direction
    if not radius_input.setManipulator(
        adsk.core.Point3D.create(*(coordinate / 10.0 for coordinate in origin)),
        adsk.core.Vector3D.create(*direction),
    ):
        raise RuntimeError("Fusion could not position the refine-radius manipulator.")


def draw_add_refine_preview(state: RefineCommandState) -> None:
    """
    Rebuild Add Refine graphics inside Fusion's preview transaction.
    """
    application = adsk.core.Application.get()
    design = _require_active_design(application)
    group, _lines = draw_pathway_spine(design, state.spine)
    state.group = group
    state.candidate = None
    if state.placement is not None:
        state.candidate = draw_candidate_refine(group, state.placement.geometry)
    application.activeViewport.refresh()
