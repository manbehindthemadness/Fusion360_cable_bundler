"""
Update appearances and stripe presentation on existing generated cable groups.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from importlib import import_module
from types import ModuleType
from typing import Any, cast
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..domain import CableGroupDefinition, HarnessDefinition
from .cable_solid_parts.constants import FINALIZED_OUTPUT_MODE, GENERATED_CABLE_GROUP_ATTRIBUTE
from .cable_solid_parts.materials import material_metadata
from .cable_solid_parts.metadata import (
    connection_branches_from_metadata,
    group_routes_from_metadata,
)
from .cable_solid_parts.stripes import replace_group_stripe_bodies
from .cable_solid_parts.sweep_geometry import (
    split_route_endpoint_pullbacks,
    split_route_for_pullback,
)
from .harness_gateway import ATTRIBUTE_GROUP


def _cable_solid_services() -> ModuleType:
    """
    Resolve the active facade module so Fusion reloads and test isolation stay coherent.
    """
    return import_module("cable_bundler.fusion.cable_solids")


def _service(name: str) -> Callable[..., Any]:
    """
    Resolve one reload-safe private facade callback by name.
    """
    return cast(Callable[..., Any], getattr(_cable_solid_services(), name))


def _main_pullbacks_from_metadata(
    metadata: dict[str, object],
) -> tuple[tuple[UUID, float, UUID, str, float, float], ...]:
    """
    Decode finalized main-route pullback body ownership in body order.
    """
    encoded = metadata.get("main_pullbacks", [])
    if not isinstance(encoded, list):
        raise RuntimeError("Generated cable-group pullback metadata is malformed.")
    decoded: list[tuple[UUID, float, UUID, str, float, float]] = []
    for item in encoded:
        if not isinstance(item, dict):
            raise RuntimeError("Generated cable-group pullback metadata is malformed.")
        raw_attachment_id = item.get("attachment_id")
        requested_mm = item.get("requested_mm")
        raw_route_id = item.get("route_id")
        boundary = item.get("boundary")
        length_mm = item.get("length_mm")
        diameter_mm = item.get("diameter_mm", 0.0)
        if (
            not isinstance(raw_attachment_id, str)
            or not isinstance(raw_route_id, str)
            or boundary not in ("start", "end")
            or isinstance(requested_mm, bool)
            or not isinstance(requested_mm, (int, float))
            or not math.isfinite(requested_mm)
            or requested_mm < 0.0
            or isinstance(length_mm, bool)
            or not isinstance(length_mm, (int, float))
            or not math.isfinite(length_mm)
            or length_mm < 0.0
            or isinstance(diameter_mm, bool)
            or not isinstance(diameter_mm, (int, float))
            or not math.isfinite(diameter_mm)
            or ("diameter_mm" in item and diameter_mm <= 0.0)
        ):
            raise RuntimeError("Generated cable-group pullback metadata is malformed.")
        try:
            attachment_id = UUID(raw_attachment_id)
            route_id = UUID(raw_route_id)
        except ValueError as error:
            raise RuntimeError("Generated cable-group pullback metadata is malformed.") from error
        decoded.append(
            (
                attachment_id,
                float(requested_mm),
                route_id,
                boundary,
                float(length_mm),
                float(diameter_mm),
            )
        )
    return tuple(decoded)


def _expected_main_pullbacks(
    definition: HarnessDefinition,
    group: CableGroupDefinition,
) -> dict[UUID, tuple[float, float]]:
    """
    Resolve current single-node leaf pullbacks at the group's main-route ends.
    """
    expected: dict[UUID, tuple[float, float]] = {}
    for connection_id in group.connection_ids:
        distance_mm, _materials, attachment_id, conductor_diameter_mm = _service(
            "_connection_endpoint_pullback"
        )(
            definition,
            group,
            connection_id,
        )
        if distance_mm > 0.0 and attachment_id is not None:
            expected[attachment_id] = (distance_mm, conductor_diameter_mm)
    return expected


def _main_welds_from_metadata(
    metadata: dict[str, object],
) -> tuple[tuple[UUID, UUID, str, float, float, float], ...]:
    """
    Decode finalized main-route weld ownership in body order.
    """
    encoded = metadata.get("main_welds", [])
    if not isinstance(encoded, list):
        raise RuntimeError("Generated cable-group weld metadata is malformed.")
    decoded: list[tuple[UUID, UUID, str, float, float, float]] = []
    for item in encoded:
        if not isinstance(item, dict):
            raise RuntimeError("Generated cable-group weld metadata is malformed.")
        raw_attachment_id = item.get("attachment_id")
        raw_route_id = item.get("route_id")
        boundary = item.get("boundary")
        diameter_mm = item.get("diameter_mm")
        conductor_diameter_mm = item.get("conductor_diameter_mm")
        length_mm = item.get("length_mm")
        if (
            not isinstance(raw_attachment_id, str)
            or not isinstance(raw_route_id, str)
            or boundary not in ("start", "end")
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0.0
                for value in (diameter_mm, conductor_diameter_mm, length_mm)
            )
        ):
            raise RuntimeError("Generated cable-group weld metadata is malformed.")
        try:
            attachment_id = UUID(raw_attachment_id)
            route_id = UUID(raw_route_id)
        except ValueError as error:
            raise RuntimeError("Generated cable-group weld metadata is malformed.") from error
        decoded.append(
            (
                attachment_id,
                route_id,
                boundary,
                float(cast(float, diameter_mm)),
                float(cast(float, conductor_diameter_mm)),
                float(cast(float, length_mm)),
            )
        )
    return tuple(decoded)


def _expected_main_welds(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    group: CableGroupDefinition,
) -> dict[UUID, tuple[float, float]]:
    """
    Resolve current leaf-face weld diameters at the group's main-route ends.
    """
    expected: dict[UUID, tuple[float, float]] = {}
    for connection_id in group.connection_ids:
        endpoint = _service("_connection_endpoint_weld")(design, definition, group, connection_id)
        if endpoint is not None:
            expected[endpoint.attachment_id] = (
                endpoint.diameter_mm,
                endpoint.conductor_diameter_mm,
            )
    return expected


# noinspection DuplicatedCode
def apply_cable_group_materials(
    design: adsk.fusion.Design,
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
) -> int:
    """
    Apply resolved materials to existing generated cable-group components.

    Stored component-local leg curves are reused to replace stripe presentation.
    Finalized groups are rebuilt when leaf pullback or weld dimensions change,
    because those material settings also define body boundaries.
    """
    groups = {group.cable_group_id: group for group in definition.cable_groups}
    occurrences = _cable_solid_services().generated_cable_group_occurrences(harness)
    geometry_changed_ids: set[UUID] = set()
    for occurrence in occurrences:
        if (
            _cable_solid_services().generated_cable_group_output_mode(occurrence)
            != FINALIZED_OUTPUT_MODE
        ):
            continue
        attribute = occurrence.component.attributes.itemByName(
            ATTRIBUTE_GROUP, GENERATED_CABLE_GROUP_ATTRIBUTE
        )
        if attribute is None:
            continue
        try:
            metadata = json.loads(attribute.value)
            group_id = UUID(metadata["cable_group_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("A generated cable group has invalid identity metadata.") from error
        group = groups.get(group_id)
        if group is None:
            continue
        stored_main_pullbacks = {
            attachment_id: (requested_mm, diameter_mm)
            for attachment_id, requested_mm, _route_id, _boundary, _length_mm, diameter_mm in (
                _main_pullbacks_from_metadata(metadata)
            )
        }
        expected_main_pullbacks = _expected_main_pullbacks(definition, group)
        if stored_main_pullbacks.keys() != expected_main_pullbacks.keys() or any(
            not math.isclose(
                stored_main_pullbacks[attachment_id][0],
                requested[0],
                abs_tol=1e-6,
            )
            or not math.isclose(
                stored_main_pullbacks[attachment_id][1],
                requested[1],
                abs_tol=1e-6,
            )
            for attachment_id, requested in expected_main_pullbacks.items()
        ):
            geometry_changed_ids.add(group_id)
            continue
        stored_main_welds = {
            attachment_id: (diameter_mm, conductor_diameter_mm)
            for (
                attachment_id,
                _route_id,
                _boundary,
                diameter_mm,
                conductor_diameter_mm,
                _length_mm,
            ) in _main_welds_from_metadata(metadata)
        }
        expected_main_welds = _expected_main_welds(design, definition, group)
        if stored_main_welds.keys() != expected_main_welds.keys() or any(
            not math.isclose(
                stored_main_welds[attachment_id][0],
                expected[0],
                abs_tol=1e-6,
            )
            or not math.isclose(
                stored_main_welds[attachment_id][1],
                expected[1],
                abs_tol=1e-6,
            )
            for attachment_id, expected in expected_main_welds.items()
        ):
            geometry_changed_ids.add(group_id)
            continue
        for branch in connection_branches_from_metadata(metadata):
            requested_mm = _service("_attachment_pullback_mm")(
                definition,
                group,
                branch.attachment_id,
                branch.diameter_mm,
            )
            if not math.isclose(
                requested_mm,
                branch.pullback_requested_mm,
                abs_tol=1e-6,
            ) or not math.isclose(
                _service("_attachment_conductor_diameter_mm")(
                    definition,
                    group,
                    branch.attachment_id,
                    branch.diameter_mm,
                ),
                branch.pullback_diameter_mm,
                abs_tol=1e-6,
            ):
                geometry_changed_ids.add(group_id)
                break
            endpoint = _service("_attachment_weld_endpoint")(
                design,
                definition,
                group,
                branch.attachment_id,
            )
            if (branch.weld_body_count == 1) != (endpoint is not None) or (
                endpoint is not None
                and (
                    not math.isclose(
                        branch.weld_diameter_mm,
                        endpoint.diameter_mm,
                        abs_tol=1e-6,
                    )
                    or not math.isclose(
                        branch.weld_conductor_diameter_mm,
                        endpoint.conductor_diameter_mm,
                        abs_tol=1e-6,
                    )
                )
            ):
                geometry_changed_ids.add(group_id)
                break
    if geometry_changed_ids:
        _service("_refresh_generated_cable_groups")(
            design,
            harness,
            definition,
            frozenset(geometry_changed_ids),
        )
        occurrences = _cable_solid_services().generated_cable_group_occurrences(harness)
    applied = 0
    for occurrence in occurrences:
        component = occurrence.component
        attribute = component.attributes.itemByName(
            ATTRIBUTE_GROUP, GENERATED_CABLE_GROUP_ATTRIBUTE
        )
        if attribute is None:
            continue
        try:
            metadata = json.loads(attribute.value)
            group_id = UUID(metadata["cable_group_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("A generated cable group has invalid identity metadata.") from error
        group = groups.get(group_id)
        if group is None:
            continue
        materials = definition.cable_group_materials(group)
        branches = connection_branches_from_metadata(metadata)
        main_pullbacks = _main_pullbacks_from_metadata(metadata)
        main_welds = _main_welds_from_metadata(metadata)
        branch_materials = tuple(
            _service("_attachment_materials")(definition, group, branch.attachment_id)
            for branch in branches
        )
        bodies = component.bRepBodies
        if bodies.count == 0:
            raise RuntimeError(f"Generated Cable Group {group_id} has no bodies to color.")
        branch_body_count = sum(
            branch.insulation_body_count + branch.pullback_body_count + branch.weld_body_count
            for branch in branches
        )
        raw_main_insulation_body_count = metadata.get(
            "main_insulation_body_count",
            bodies.count - branch_body_count,
        )
        if (
            isinstance(raw_main_insulation_body_count, bool)
            or not isinstance(raw_main_insulation_body_count, int)
            or raw_main_insulation_body_count < 0
        ):
            raise RuntimeError(f"Generated Cable Group {group_id} has invalid branch bodies.")
        main_insulation_body_count = raw_main_insulation_body_count
        if (
            main_insulation_body_count + len(main_pullbacks) + len(main_welds) + branch_body_count
            != bodies.count
        ):
            raise RuntimeError(f"Generated Cable Group {group_id} has invalid branch bodies.")
        appearance = _cable_solid_services().cable_appearance(
            design, materials.main_color, materials.appearance
        )
        for body_index in range(main_insulation_body_count):
            body = bodies.item(body_index)
            if body is not None:
                body.appearance = appearance
        body_index = main_insulation_body_count
        for (
            attachment_id,
            _requested_mm,
            _route_id,
            _boundary,
            _length_mm,
            _diameter_mm,
        ) in main_pullbacks:
            pullback_materials = _service("_attachment_materials")(
                definition,
                group,
                attachment_id,
            ).pullback
            body = bodies.item(body_index)
            if body is not None:
                body.appearance = _cable_solid_services().cable_appearance(
                    design,
                    pullback_materials.color,
                    pullback_materials.appearance,
                )
            body_index += 1
        for (
            attachment_id,
            _route_id,
            _boundary,
            _diameter_mm,
            _conductor_diameter_mm,
            _length_mm,
        ) in main_welds:
            weld_materials = _service("_attachment_materials")(
                definition,
                group,
                attachment_id,
            ).weld
            body = bodies.item(body_index)
            if body is not None:
                body.appearance = _cable_solid_services().cable_appearance(
                    design,
                    weld_materials.color,
                    weld_materials.appearance,
                )
            body_index += 1
        for branch, branch_settings in zip(branches, branch_materials):
            if branch.insulation_body_count:
                body = bodies.item(body_index)
                if body is not None:
                    body.appearance = _cable_solid_services().cable_appearance(
                        design, branch_settings.main_color, branch_settings.appearance
                    )
                body_index += 1
            if branch.pullback_body_count:
                body = bodies.item(body_index)
                if body is not None:
                    body.appearance = _cable_solid_services().cable_appearance(
                        design,
                        branch_settings.pullback.color,
                        branch_settings.pullback.appearance,
                    )
                body_index += 1
            if branch.weld_body_count:
                body = bodies.item(body_index)
                if body is not None:
                    body.appearance = _cable_solid_services().cable_appearance(
                        design,
                        branch_settings.weld.color,
                        branch_settings.weld.appearance,
                    )
                body_index += 1
        routes = group_routes_from_metadata(metadata)
        if not routes and materials.stripes:
            raise RuntimeError(
                "Generated cable-group metadata has no routes for applying stripe patterns."
            )
        _cable_solid_services().clear_group_stripe_graphics(
            component, group_id, include_legacy=True
        )
        _cable_solid_services().clear_group_stripe_graphics(harness, group_id)
        if (
            _cable_solid_services().generated_cable_group_output_mode(occurrence)
            == FINALIZED_OUTPUT_MODE
        ):
            pullbacks_by_route: dict[UUID, dict[str, float]] = {}
            for (
                _attachment_id,
                _requested_mm,
                route_id,
                boundary,
                length_mm,
                _diameter_mm,
            ) in main_pullbacks:
                pullbacks_by_route.setdefault(route_id, {})[boundary] = length_mm
            insulation_routes = []
            for route in routes:
                route_pullbacks = pullbacks_by_route.get(route.cable_id, {})
                insulation = split_route_endpoint_pullbacks(
                    route,
                    route_pullbacks.get("start", 0.0),
                    route_pullbacks.get("end", 0.0),
                ).insulation
                if insulation is not None:
                    insulation_routes.append(insulation)
            branch_decorations = []
            for branch, settings in zip(branches, branch_materials):
                insulation = split_route_for_pullback(
                    branch.route,
                    branch.pullback_mm,
                ).insulation
                if insulation is not None:
                    branch_decorations.append(
                        (insulation, settings.stripes, branch.diameter_mm / 2.0)
                    )
            replace_group_stripe_bodies(
                component,
                tuple(insulation_routes),
                materials.stripes,
                group.diameter_mm / 2.0,
                design,
                branch_decorations=tuple(branch_decorations),
            )
        else:
            _service("_replace_group_stripe_graphics")(
                harness,
                routes,
                materials.stripes,
                group.diameter_mm / 2.0,
                group_id,
                is_visible=occurrence.isLightBulbOn,
                branch_decorations=tuple(
                    (branch.route, settings.stripes, branch.diameter_mm / 2.0)
                    for branch, settings in zip(branches, branch_materials)
                ),
            )
        metadata.update(material_metadata(materials))
        attribute.value = json.dumps(metadata, sort_keys=True)
        applied += 1
    return applied


# noinspection DuplicatedCode
def restore_cable_group_stripe_graphics(
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
) -> int:
    """
    Recreate transient stripe meshes for existing generated cable-group solids.

    Generated components retain their exact component-local route curves, while
    the harness definition remains authoritative for current stripe settings.
    Rebuilding only Custom Graphics keeps existing solid geometry untouched.
    """
    groups = {group.cable_group_id: group for group in definition.cable_groups}
    restored = 0
    for occurrence in _cable_solid_services().generated_cable_group_occurrences(harness):
        if (
            _cable_solid_services().generated_cable_group_output_mode(occurrence)
            == FINALIZED_OUTPUT_MODE
        ):
            continue
        component = occurrence.component
        attribute = component.attributes.itemByName(
            ATTRIBUTE_GROUP, GENERATED_CABLE_GROUP_ATTRIBUTE
        )
        if attribute is None:
            continue
        try:
            metadata = json.loads(attribute.value)
            group_id = UUID(metadata["cable_group_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("A generated cable group has invalid identity metadata.") from error
        group = groups.get(group_id)
        if group is None:
            continue
        stripes = definition.cable_group_materials(group).stripes
        routes = group_routes_from_metadata(metadata)
        branches = connection_branches_from_metadata(metadata)
        if not routes and stripes:
            raise RuntimeError(
                "Generated cable-group metadata has no routes for restoring stripe patterns."
            )
        _cable_solid_services().clear_group_stripe_graphics(
            component, group_id, include_legacy=True
        )
        restored += _service("_replace_group_stripe_graphics")(
            harness,
            routes,
            stripes,
            group.diameter_mm / 2.0,
            group_id,
            is_visible=occurrence.isLightBulbOn,
            **(
                {
                    "branch_decorations": tuple(
                        (
                            branch.route,
                            _service("_attachment_materials")(
                                definition, group, branch.attachment_id
                            ).stripes,
                            branch.diameter_mm / 2.0,
                        )
                        for branch in branches
                    )
                }
                if branches
                else {}
            ),
        )
    return restored
