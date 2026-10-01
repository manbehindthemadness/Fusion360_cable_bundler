"""
Sweep separately addressable wire bodies from numbered ribbon line faces.
"""

from __future__ import annotations

import json
import math
from importlib import import_module
from time import perf_counter
from typing import Optional
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...application import CableGroupRouteLeg
from ...domain import CableGroupDefinition, HarnessDefinition, PullbackMode
from ...routing import RoutePreview
from ..harness_gateway import ATTRIBUTE_GROUP
from ..ribbon_geometry import RibbonGuidePlane
from .constants import FINALIZED_OUTPUT_MODE, GENERATED_CABLE_GROUP_ATTRIBUTE
from .materials import cable_appearance
from .metadata import route_in_component_space, route_metadata
from .ribbon_overlap import fitted_ribbon_overlap_diameter
from .solid_builder import _build_route_sweep
from .sweep_geometry import extend_route_tail, split_route_for_pullback
from .welds import build_weld_body


def _line_number(definition: HarnessDefinition, connection_id: UUID, attachment_id: UUID) -> int:
    """
    Follow a child branch to the root's persistent ribbon pin.
    """
    connection = next(
        item for item in definition.connections if item.connection_id == connection_id
    )
    by_id = {item.attachment_id: item for item in connection.attachments}
    attachment = by_id[attachment_id]
    while attachment.parent_attachment_id is not None:
        attachment = by_id[attachment.parent_attachment_id]
    if attachment.pin_number is None:
        raise ValueError("A generated ribbon connection needs a numbered root.")
    return int(attachment.pin_number)


def build_ribbon_connection_branches(
    component: adsk.fusion.Component,
    group: CableGroupDefinition,
    group_index: int,
    branches: tuple[tuple[CableGroupRouteLeg, RoutePreview], ...],
    transform: adsk.core.Matrix3D,
    definition: HarnessDefinition,
    design: adsk.fusion.Design,
    output_mode: str,
    ribbon_body: adsk.fusion.BRepBody,
    end_planes: dict[UUID, RibbonGuidePlane],
    notices: Optional[list[str]] = None,
    *,
    timings: Optional[dict[str, float]] = None,
) -> None:
    """
    Add touching branch solids and append their stable identities to ribbon metadata.
    """
    if not branches:
        return
    if timings is not None:
        timings["overlap_fit"] = 0.0
        timings["branch_sweeps"] = 0.0
    attribute = component.attributes.itemByName(ATTRIBUTE_GROUP, GENERATED_CABLE_GROUP_ATTRIBUTE)
    if attribute is None:
        raise RuntimeError("Generated ribbon metadata is missing before branch construction.")
    metadata = json.loads(attribute.value)
    main_materials = definition.cable_group_materials(group)
    line_colors = group.resolved_ribbon_line_colors(main_materials.main_color)
    records = []
    for index, (leg, route) in enumerate(branches, start=1):
        connection_id, attachment_id = leg.start_connection_id, leg.attachment_id
        if connection_id is None or attachment_id is None:
            raise ValueError("A ribbon branch needs its saved connection identity.")
        line_number = _line_number(definition, connection_id, attachment_id)
        connection = next(
            item for item in definition.connections if item.connection_id == connection_id
        )
        attachment = next(
            item for item in connection.attachments if item.attachment_id == attachment_id
        )
        materials = definition.cable_end_attachment_materials(group, connection_id, attachment_id)
        cap_diameter_mm = leg.diameter_mm or group.diameter_mm
        diameter_mm = cap_diameter_mm
        if attachment.parent_attachment_id is None:
            guide_plane = end_planes.get(connection_id)
            if guide_plane is None:
                raise ValueError("A ribbon root connection needs its fitted end plane.")
            try:
                fit_started = perf_counter()
                diameter_mm = fitted_ribbon_overlap_diameter(
                    ribbon_body, route, guide_plane, cap_diameter_mm, transform
                )
                if timings is not None:
                    timings["overlap_fit"] += perf_counter() - fit_started
            except (RuntimeError, ValueError) as error:
                raise RuntimeError(
                    f"Ribbon line {line_number} connection overlap fit failed: {error}"
                ) from error
            if notices is not None and cap_diameter_mm - diameter_mm > 0.01:
                notices.append(
                    f"Warning: {group.name or 'Ribbon'} line {line_number}: "
                    f"ribbon surface fit reduces connection diameter to "
                    f"{diameter_mm:.2f} mm from {cap_diameter_mm:.2f} mm."
                )
        configured_conductor_mm = attachment.visual_overrides.conductor_diameter_mm
        pullback_diameter_mm = (
            configured_conductor_mm if configured_conductor_mm is not None else diameter_mm * 0.75
        )
        pullback = materials.pullback
        requested_pullback_mm = (
            pullback.value
            if pullback.mode is PullbackMode.DISTANCE
            else diameter_mm * pullback.value / 100.0
        )
        if connection.attachment_children(attachment_id):
            requested_pullback_mm = 0.0
        split = split_route_for_pullback(
            route, requested_pullback_mm if output_mode == FINALIZED_OUTPUT_MODE else 0.0
        )
        if split.pullback is not None and pullback_diameter_mm > diameter_mm:
            raise ValueError(
                f"Ribbon line {line_number} connection conductor is wider than its fitted insulation."
            )
        overlap_mm = diameter_mm * 0.5
        insulation_count = 0
        pullback_count = 0
        length_mm = 0.0
        if split.insulation is not None:
            sweep_started = perf_counter()
            body, measured = _build_route_sweep(
                component,
                extend_route_tail(split.insulation, overlap_mm),
                diameter_mm,
                transform,
                f"Ribbon Connection {index} Centerline",
                f"Ribbon Connection {index} Diameter",
                f"Ribbon Connection {index} Sweep",
            )
            if timings is not None:
                timings["branch_sweeps"] += perf_counter() - sweep_started
            body.name = f"Cable Group {group_index + 1} Line {line_number} Connection {index}"
            color = (
                line_colors[line_number - 1]
                if attachment.visual_overrides.main_color is None
                else materials.main_color
            )
            body.appearance = cable_appearance(design, color, materials.appearance)
            insulation_count = 1
            length_mm += measured - overlap_mm
        if split.pullback is not None:
            sweep_started = perf_counter()
            body, measured = _build_route_sweep(
                component,
                extend_route_tail(split.pullback, overlap_mm)
                if split.insulation is None
                else split.pullback,
                pullback_diameter_mm,
                transform,
                f"Ribbon Connection {index} Pullback Centerline",
                f"Ribbon Connection {index} Pullback Diameter",
                f"Ribbon Connection {index} Pullback Sweep",
            )
            if timings is not None:
                timings["branch_sweeps"] += perf_counter() - sweep_started
            body.name = f"Cable Group {group_index + 1} Line {line_number} Pullback {index}"
            body.appearance = cable_appearance(
                design, materials.pullback.color, materials.pullback.appearance
            )
            pullback_count = 1
            length_mm += measured - (overlap_mm if split.insulation is None else 0.0)
        endpoint = (
            import_module("cable_bundler.fusion.cable_solids")._attachment_weld_endpoint(
                design, definition, group, attachment_id
            )
            if output_mode == FINALIZED_OUTPUT_MODE
            else None
        )
        weld_count = 0
        if endpoint is not None:
            weld = build_weld_body(
                component,
                route,
                transform,
                endpoint,
                f"Cable Group {group_index + 1} Line {line_number} Weld {index}",
            )
            weld.body.appearance = cable_appearance(
                design, endpoint.settings.color, endpoint.settings.appearance
            )
            weld_count = 1
        if not math.isfinite(length_mm) or length_mm <= 0.0:
            raise RuntimeError("Fusion did not retain a usable ribbon connection branch.")
        local_route = route_in_component_space(route, transform)
        records.append(
            {
                "route_id": str(route.cable_id),
                "label": route.cable_number,
                "diameter_mm": diameter_mm,
                "attachment_id": str(attachment_id),
                "ribbon_line_number": line_number,
                "length_mm": length_mm,
                "pullback_mm": split.pullback_length_mm,
                "pullback_requested_mm": (
                    requested_pullback_mm if output_mode == FINALIZED_OUTPUT_MODE else 0.0
                ),
                "pullback_diameter_mm": pullback_diameter_mm,
                "insulation_body_count": insulation_count,
                "pullback_body_count": pullback_count,
                "weld_body_count": weld_count,
                "weld_diameter_mm": endpoint.diameter_mm if endpoint is not None else 0.0,
                "weld_conductor_diameter_mm": (
                    endpoint.conductor_diameter_mm if endpoint is not None else 0.0
                ),
                "weld_length_mm": (
                    split_route_for_pullback(route, endpoint.radius_mm).pullback_length_mm
                    if endpoint is not None
                    else 0.0
                ),
                "route_curves_mm": route_metadata(local_route),
            }
        )
    metadata["connection_branches"] = records
    attribute.value = json.dumps(metadata, sort_keys=True)
