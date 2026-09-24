"""
Pathway segmentation, routing-control, naming, and deletion edits.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from uuid import UUID, uuid4

from ...domain import (
    ControlKind,
    ControlStructure,
    JunctionDefinition,
    JunctionPathwayRelationship,
    Metadata,
    PathwayDefinition,
    PathwayEndpoint,
    RefineGeometry,
    RoutingMode,
    next_available_name,
)
from .support import (
    clamp_pathway_insertion_index,
    locked_pathway_control_indexes,
    pathway_deletion_ids,
    persist_definition,
    prune_attachment_associations,
    prune_cable_groups,
    read_definition,
    replace_pathway,
    require_pathway,
)
from .types import HarnessEditGateway, PathwaySegmentResult


def suggest_pathway_extension_name(
    harness_id: UUID,
    pathway_id: UUID,
    gateway: HarnessEditGateway,
) -> str:
    """
    Return the next root-sequenced extension name for a pathway chain.
    """
    _original, definition = read_definition(harness_id, gateway)
    pathway = require_pathway(definition, pathway_id)
    predecessors: dict[UUID, set[UUID]] = {}
    for junction in definition.junctions:
        preceding_ids = {
            relationship.pathway_id
            for relationship in junction.pathway_relationships
            if relationship.endpoint is PathwayEndpoint.END
        }
        for relationship in junction.pathway_relationships:
            if relationship.endpoint is PathwayEndpoint.START:
                predecessors.setdefault(relationship.pathway_id, set()).update(preceding_ids)
    root_id = pathway.pathway_id
    visited: set[UUID] = set()
    while len(predecessors.get(root_id, ())) == 1:
        if root_id in visited:
            raise ValueError("The pathway junction chain contains a cycle.")
        visited.add(root_id)
        root_id = next(iter(predecessors[root_id]))
    root = require_pathway(definition, root_id)
    return next_available_name(
        f"{root.name} ext 1",
        (candidate.name for candidate in definition.pathways),
    )


def segment_pathway(
    harness_id: UUID,
    pathway_id: UUID,
    control_id: UUID,
    following_name: str,
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
) -> PathwaySegmentResult:
    """
    Split a pathway around one interior control and persist its junction atomically.
    """
    normalized_name = following_name.strip()
    if not normalized_name:
        raise ValueError("New pathway name must not be empty.")
    original, definition = read_definition(harness_id, gateway)
    pathway = require_pathway(definition, pathway_id)
    try:
        control_index = pathway.ordered_control_ids.index(control_id)
    except ValueError as error:
        raise ValueError("Selected control does not belong to this pathway.") from error
    if control_index == 0 or control_index == len(pathway.ordered_control_ids) - 1:
        raise ValueError("Select a pathway control that is not an end.")
    control = next(
        (candidate for candidate in definition.controls if candidate.control_id == control_id),
        None,
    )
    if control is None:
        raise ValueError("Selected pathway control no longer exists.")
    if control.kind not in {ControlKind.ROUTING_GATE, ControlKind.REFINE}:
        raise ValueError("Only routing gates and refine points can currently segment a pathway.")

    following_pathway_id = id_factory()
    junction_id = id_factory()
    existing_ids = {
        definition.harness_id,
        *(connection.connection_id for connection in definition.connections),
        *(candidate.control_id for candidate in definition.controls),
        *(candidate.pathway_id for candidate in definition.pathways),
        *(candidate.junction_id for candidate in definition.junctions),
        *(group.cable_group_id for group in definition.cable_groups),
        *(association.association_id for association in definition.attachment_associations),
    }
    if following_pathway_id in existing_ids or junction_id in existing_ids | {following_pathway_id}:
        raise ValueError("Generated pathway or junction identity is already in use.")
    resolved_name = next_available_name(
        normalized_name,
        (candidate.name for candidate in definition.pathways),
    )
    preceding_pathway = replace(
        pathway,
        ordered_control_ids=pathway.ordered_control_ids[:control_index],
        end_name="",
        end_metadata=(),
    )
    following_pathway = PathwayDefinition(
        pathway_id=following_pathway_id,
        name=resolved_name,
        routing_mode=pathway.routing_mode,
        ordered_control_ids=pathway.ordered_control_ids[control_index + 1 :],
        end_name=pathway.end_name,
        end_metadata=pathway.end_metadata,
    )
    junction = JunctionDefinition(
        junction_id=junction_id,
        name=next_available_name(
            "Junction 01", (candidate.name for candidate in definition.junctions)
        ),
        control_id=control_id,
        pathway_relationships=(
            JunctionPathwayRelationship(pathway.pathway_id, PathwayEndpoint.END),
            JunctionPathwayRelationship(following_pathway.pathway_id, PathwayEndpoint.START),
        ),
    )

    pathways: list[PathwayDefinition] = []
    for candidate in definition.pathways:
        pathways.append(preceding_pathway if candidate.pathway_id == pathway_id else candidate)
        if candidate.pathway_id == pathway_id:
            pathways.append(following_pathway)
    prior_junctions = tuple(
        replace(
            candidate,
            pathway_relationships=tuple(
                JunctionPathwayRelationship(following_pathway.pathway_id, relationship.endpoint)
                if relationship.pathway_id == pathway_id
                and relationship.endpoint is PathwayEndpoint.END
                else relationship
                for relationship in candidate.pathway_relationships
            ),
        )
        for candidate in definition.junctions
    )
    standalone_ends = tuple(
        replace(end, pathway_id=following_pathway.pathway_id)
        if end.pathway_id == pathway_id and end.endpoint is PathwayEndpoint.END
        else end
        for end in definition.standalone_ends
    )
    updated = replace(
        definition,
        pathways=tuple(pathways),
        junctions=(*prior_junctions, junction),
        standalone_ends=standalone_ends,
    )
    persist_definition(harness_id, original, updated, gateway)
    return PathwaySegmentResult(preceding_pathway, following_pathway, junction)


def add_pathway_refine(
    harness_id: UUID,
    pathway_id: UUID,
    insertion_index: int,
    geometry: RefineGeometry,
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
) -> ControlStructure:
    """
    Insert one persistent unconstrained refine into a pathway traversal.
    """
    if isinstance(insertion_index, bool) or not isinstance(insertion_index, int):
        raise ValueError("Refine insertion position must be an integer.")
    if not isinstance(geometry, RefineGeometry):
        raise ValueError("Refine geometry is invalid.")
    original, definition = read_definition(harness_id, gateway)
    pathway = require_pathway(definition, pathway_id)
    if not 0 <= insertion_index <= len(pathway.ordered_control_ids):
        raise ValueError("Refine insertion position is outside the pathway.")
    insertion_index = clamp_pathway_insertion_index(
        definition,
        pathway,
        insertion_index,
    )
    control = ControlStructure(
        control_id=id_factory(),
        name=next_available_name("Refine Point 01", (item.name for item in definition.controls)),
        kind=ControlKind.REFINE,
        entity_token="",
        interpolation=definition.gate_defaults,
        refine_geometry=geometry,
    )
    ordered_ids = list(pathway.ordered_control_ids)
    ordered_ids.insert(insertion_index, control.control_id)
    updated_pathway = replace(pathway, ordered_control_ids=tuple(ordered_ids))
    updated = replace(
        definition,
        controls=(*definition.controls, control),
        pathways=replace_pathway(definition, updated_pathway),
    )
    persist_definition(harness_id, original, updated, gateway)
    return control


def update_pathway_refine(
    harness_id: UUID,
    control_id: UUID,
    geometry: RefineGeometry,
    gateway: HarnessEditGateway,
) -> ControlStructure:
    """
    Persist a new position, orientation, and display radius for one refine.
    """
    if not isinstance(geometry, RefineGeometry):
        raise ValueError("Refine geometry is invalid.")
    original, definition = read_definition(harness_id, gateway)
    control = next(
        (item for item in definition.controls if item.control_id == control_id),
        None,
    )
    if control is None or control.kind is not ControlKind.REFINE:
        raise ValueError("Selected refine point no longer exists.")
    updated_control = replace(control, refine_geometry=geometry)
    updated = replace(
        definition,
        controls=tuple(
            updated_control if item.control_id == control_id else item
            for item in definition.controls
        ),
    )
    persist_definition(harness_id, original, updated, gateway)
    return updated_control


def append_pathway_gates(
    harness_id: UUID,
    pathway_id: UUID,
    gate_entity_tokens: tuple[str, ...],
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
) -> tuple[ControlStructure, ...]:
    """
    Append selected profiles to an existing pathway in selection order.
    """
    normalized_tokens = tuple(token.strip() for token in gate_entity_tokens)
    if not normalized_tokens:
        raise ValueError("Select at least one gate profile to append.")
    if any(not token for token in normalized_tokens):
        raise ValueError("Every pathway gate must reference Fusion geometry.")

    original, definition = read_definition(harness_id, gateway)
    pathway = require_pathway(definition, pathway_id)
    kind = (
        ControlKind.ROUTING_GATE
        if pathway.routing_mode is RoutingMode.ROUTING_GATES
        else ControlKind.PROFILE_GATE
    )
    label = "Routing Gate" if kind is ControlKind.ROUTING_GATE else "Profile Gate"
    existing_names = [control.name for control in definition.controls]
    controls: list[ControlStructure] = []
    for token in normalized_tokens:
        name = next_available_name(f"{label} 01", (*existing_names, *(c.name for c in controls)))
        controls.append(ControlStructure(id_factory(), name, kind, token, definition.gate_defaults))

    insertion_index = clamp_pathway_insertion_index(
        definition,
        pathway,
        len(pathway.ordered_control_ids),
    )
    ordered_control_ids = list(pathway.ordered_control_ids)
    ordered_control_ids[insertion_index:insertion_index] = [
        control.control_id for control in controls
    ]
    updated_pathway = replace(pathway, ordered_control_ids=tuple(ordered_control_ids))
    updated = replace(
        definition,
        controls=(*definition.controls, *controls),
        pathways=replace_pathway(definition, updated_pathway),
    )
    persist_definition(harness_id, original, updated, gateway)
    return tuple(controls)


def move_pathway_gate(
    harness_id: UUID,
    pathway_id: UUID,
    control_id: UUID,
    offset: int,
    gateway: HarnessEditGateway,
) -> PathwayDefinition:
    """
    Insert one gate at a new position within its pathway.
    """
    if isinstance(offset, bool) or not isinstance(offset, int) or offset == 0:
        raise ValueError("Gate movement requires a nonzero integer offset.")
    original, definition = read_definition(harness_id, gateway)
    pathway = require_pathway(definition, pathway_id)
    ordered_ids = list(pathway.ordered_control_ids)
    try:
        current_index = ordered_ids.index(control_id)
    except ValueError as error:
        raise ValueError("Selected gate does not belong to this pathway.") from error
    target_index = current_index + offset
    if target_index < 0 or target_index >= len(ordered_ids):
        raise ValueError("Selected gate is already at that end of the pathway.")
    locked_indexes = locked_pathway_control_indexes(definition, pathway)
    if current_index in locked_indexes or target_index in locked_indexes:
        raise ValueError("A junction-related or standalone pathway endpoint cannot be reordered.")
    ordered_ids.insert(target_index, ordered_ids.pop(current_index))
    updated_pathway = replace(pathway, ordered_control_ids=tuple(ordered_ids))
    updated = replace(definition, pathways=replace_pathway(definition, updated_pathway))
    persist_definition(harness_id, original, updated, gateway)
    return updated_pathway


def remove_pathway_gate(
    harness_id: UUID,
    pathway_id: UUID,
    control_id: UUID,
    gateway: HarnessEditGateway,
) -> PathwayDefinition:
    """
    Remove one gate and prune its control when no pathway still uses it.
    """
    original, definition = read_definition(harness_id, gateway)
    pathway = require_pathway(definition, pathway_id)
    if control_id not in pathway.ordered_control_ids:
        raise ValueError("Selected gate does not belong to this pathway.")
    if len(pathway.ordered_control_ids) == 1:
        raise ValueError("A pathway must retain at least one gate.")
    control_index = pathway.ordered_control_ids.index(control_id)
    if control_index in locked_pathway_control_indexes(definition, pathway):
        raise ValueError("A junction-related or standalone pathway endpoint cannot be removed.")
    updated_pathway = replace(
        pathway,
        ordered_control_ids=tuple(
            item for item in pathway.ordered_control_ids if item != control_id
        ),
    )
    pathways = replace_pathway(definition, updated_pathway)
    referenced_control_ids = {
        item for candidate in pathways for item in candidate.ordered_control_ids
    }
    updated = replace(
        definition,
        controls=tuple(
            control
            for control in definition.controls
            if control.control_id != control_id or control.control_id in referenced_control_ids
        ),
        pathways=pathways,
    )
    persist_definition(harness_id, original, updated, gateway)
    return updated_pathway


def remove_pathway(
    harness_id: UUID,
    pathway_id: UUID,
    gateway: HarnessEditGateway,
) -> None:
    """
    Remove one pathway, its exclusive downstream branch, and owned dependent data.

    Junctions remain in place so pathways shared with the removed branch retain their
    surrounding topology and all remaining relationship identities.
    """
    original, definition = read_definition(harness_id, gateway)
    require_pathway(definition, pathway_id)
    deleted_pathway_ids = pathway_deletion_ids(definition, pathway_id)
    pathways = tuple(
        pathway for pathway in definition.pathways if pathway.pathway_id not in deleted_pathway_ids
    )
    junctions = tuple(
        replace(
            junction,
            pathway_relationships=tuple(
                relationship
                for relationship in junction.pathway_relationships
                if relationship.pathway_id not in deleted_pathway_ids
            ),
        )
        for junction in definition.junctions
    )
    standalone_ends = tuple(
        end for end in definition.standalone_ends if end.pathway_id not in deleted_pathway_ids
    )
    referenced_connection_ids = {end.connection_id for end in standalone_ends}
    referenced_control_ids = (
        {control_id for pathway in pathways for control_id in pathway.ordered_control_ids}
        | {control_id for end in standalone_ends for control_id in end.ordered_control_ids}
        | {junction.control_id for junction in junctions}
    )
    updated = replace(
        definition,
        controls=tuple(
            control
            for control in definition.controls
            if control.control_id in referenced_control_ids
        ),
        connections=tuple(
            connection
            for connection in definition.connections
            if connection.connection_id in referenced_connection_ids
        ),
        junctions=junctions,
        pathways=pathways,
        standalone_ends=standalone_ends,
        cable_groups=prune_cable_groups(definition.cable_groups, referenced_connection_ids),
        attachment_associations=prune_attachment_associations(
            definition.attachment_associations,
            {
                attachment.attachment_id
                for connection in definition.connections
                if connection.connection_id in referenced_connection_ids
                for attachment in connection.attachments
            },
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


def rename_pathway(
    harness_id: UUID,
    pathway_id: UUID,
    field: str,
    name: str,
    gateway: HarnessEditGateway,
) -> None:
    """
    Rename a pathway or either traversal end without changing route identity.

    Clearing the pathway name restores an available generated designation.
    """
    if field not in {"name", "start_name", "end_name"}:
        raise ValueError("Unsupported pathway name field.")
    if not isinstance(name, str):
        raise ValueError("Pathway name must be a string.")
    original, definition = read_definition(harness_id, gateway)
    pathway = require_pathway(definition, pathway_id)
    normalized = name.strip()
    if field == "name":
        normalized = next_available_name(
            normalized or "Pathway 01",
            (item.name for item in definition.pathways if item.pathway_id != pathway_id),
        )
    updated = replace(pathway, **{field: normalized})
    persist_definition(
        harness_id,
        original,
        replace(definition, pathways=replace_pathway(definition, updated)),
        gateway,
    )


def set_pathway_properties(
    harness_id: UUID,
    pathway_id: UUID,
    metadata: Metadata,
    gateway: HarnessEditGateway,
) -> None:
    """
    Replace searchable metadata without changing pathway routing behavior.
    """
    original, definition = read_definition(harness_id, gateway)
    pathway = require_pathway(definition, pathway_id)
    updated = replace(pathway, metadata=metadata)
    persist_definition(
        harness_id,
        original,
        replace(definition, pathways=replace_pathway(definition, updated)),
        gateway,
    )


def set_pathway_end_properties(
    harness_id: UUID,
    pathway_id: UUID,
    endpoint: PathwayEndpoint,
    metadata: Metadata,
    gateway: HarnessEditGateway,
) -> None:
    """
    Replace searchable metadata for one pathway boundary without changing routing.
    """
    original, definition = read_definition(harness_id, gateway)
    pathway = require_pathway(definition, pathway_id)
    field = "start_metadata" if endpoint is PathwayEndpoint.START else "end_metadata"
    updated = replace(pathway, **{field: metadata})
    persist_definition(
        harness_id,
        original,
        replace(definition, pathways=replace_pathway(definition, updated)),
        gateway,
    )
