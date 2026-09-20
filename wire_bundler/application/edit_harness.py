"""
Edit ordered pathway gates and wire endpoint pairings transactionally.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Optional, Protocol
from uuid import UUID, uuid4

from ..domain import (
    AutoTransitionPreset,
    Connection,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    JunctionDefinition,
    JunctionPathwayRelationship,
    PathwayDefinition,
    PathwayEndpoint,
    RefineGeometry,
    RoutingMode,
    WireGroupDefinition,
    WireMaterialSettings,
    dumps,
    loads,
    next_available_name,
    validate_harness,
)
from ..domain.model import InterpolationSettings


class HarnessEditGateway(Protocol):
    """
    Describe persisted harness operations required by ordered edits.
    """

    def read_harness_definition(self, harness_id: UUID) -> str:
        """
        Return the serialized definition owned by one harness.
        """

    def replace_harness_definition(self, harness_id: UUID, serialized_definition: str) -> None:
        """
        Replace the serialized definition owned by one harness.
        """


class HarnessEditError(RuntimeError):
    """
    Report an edit that failed and could not be rolled back cleanly.
    """


@dataclass(frozen=True)
class PathwaySegmentResult:
    """
    Return the two pathway halves and their intervening junction.
    """

    preceding_pathway: PathwayDefinition
    following_pathway: PathwayDefinition
    junction: JunctionDefinition


def add_junction(
    harness_id: UUID,
    entity_token: str,
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
) -> JunctionDefinition:
    """
    Persist one unconnected routing-gate junction from unused Fusion geometry.
    """
    normalized_token = entity_token.strip()
    if not normalized_token:
        raise ValueError("A junction must reference Fusion geometry.")
    original, definition = _read_definition(harness_id, gateway)
    registered_tokens = {
        token.strip() for connection in definition.connections for token in connection.member_tokens
    } | {control.entity_token.strip() for control in definition.controls if control.entity_token}
    if normalized_token in registered_tokens:
        raise ValueError("Selected geometry is already registered in this harness.")

    control_id = id_factory()
    junction_id = id_factory()
    existing_ids = {
        definition.harness_id,
        *(connection.connection_id for connection in definition.connections),
        *(
            member_id
            for connection in definition.connections
            for member_id in connection.member_identities
        ),
        *(control.control_id for control in definition.controls),
        *(pathway.pathway_id for pathway in definition.pathways),
        *(junction.junction_id for junction in definition.junctions),
        *(group.wire_group_id for group in definition.wire_groups),
    }
    if control_id in existing_ids or junction_id in existing_ids | {control_id}:
        raise ValueError("Generated control or junction identity is already in use.")
    control = ControlStructure(
        control_id=control_id,
        name=next_available_name(
            "Routing Gate 01", (candidate.name for candidate in definition.controls)
        ),
        kind=ControlKind.ROUTING_GATE,
        entity_token=normalized_token,
        interpolation=definition.gate_defaults,
    )
    junction = JunctionDefinition(
        junction_id=junction_id,
        name=next_available_name(
            "Junction 01", (candidate.name for candidate in definition.junctions)
        ),
        control_id=control.control_id,
    )
    updated = replace(
        definition,
        controls=(*definition.controls, control),
        junctions=(*definition.junctions, junction),
    )
    _persist(harness_id, original, updated, gateway)
    return junction


def update_junction_relationships(
    harness_id: UUID,
    junction_id: UUID,
    pathway_relationships: tuple[JunctionPathwayRelationship, ...],
    gateway: HarnessEditGateway,
) -> JunctionDefinition:
    """
    Replace one junction's endpoint relationships and preserve wire control order.
    """
    if any(
        not isinstance(relationship, JunctionPathwayRelationship)
        for relationship in pathway_relationships
    ):
        raise ValueError("Every junction relationship must identify a pathway endpoint.")
    original, definition = _read_definition(harness_id, gateway)
    updated_junction, updated = _replace_junction_relationships(
        definition,
        junction_id,
        pathway_relationships,
    )
    _persist(harness_id, original, updated, gateway)
    return updated_junction


def add_junction_relationship(
    harness_id: UUID,
    junction_id: UUID,
    pathway_relationship: JunctionPathwayRelationship,
    gateway: HarnessEditGateway,
) -> JunctionDefinition:
    """
    Attach one available pathway endpoint to a junction atomically.
    """
    if not isinstance(pathway_relationship, JunctionPathwayRelationship):
        raise ValueError("A junction relationship must identify a pathway endpoint.")
    original, definition = _read_definition(harness_id, gateway)
    junction = next(
        (candidate for candidate in definition.junctions if candidate.junction_id == junction_id),
        None,
    )
    if junction is None:
        raise ValueError("Selected junction does not exist in this harness.")
    if pathway_relationship in junction.pathway_relationships:
        raise ValueError("Selected pathway endpoint is already related to this junction.")
    updated_junction, updated = _replace_junction_relationships(
        definition,
        junction_id,
        (*junction.pathway_relationships, pathway_relationship),
    )
    _persist(harness_id, original, updated, gateway)
    return updated_junction


def remove_junction_relationship(
    harness_id: UUID,
    junction_id: UUID,
    pathway_relationship: JunctionPathwayRelationship,
    gateway: HarnessEditGateway,
) -> JunctionDefinition:
    """
    Detach one exact pathway endpoint from a junction atomically.
    """
    if not isinstance(pathway_relationship, JunctionPathwayRelationship):
        raise ValueError("A junction relationship must identify a pathway endpoint.")
    original, definition = _read_definition(harness_id, gateway)
    junction = next(
        (candidate for candidate in definition.junctions if candidate.junction_id == junction_id),
        None,
    )
    if junction is None:
        raise ValueError("Selected junction does not exist in this harness.")
    if pathway_relationship not in junction.pathway_relationships:
        raise ValueError("Selected junction relationship no longer exists.")
    updated_junction, updated = _replace_junction_relationships(
        definition,
        junction_id,
        tuple(
            relationship
            for relationship in junction.pathway_relationships
            if relationship != pathway_relationship
        ),
    )
    _persist(harness_id, original, updated, gateway)
    return updated_junction


def rename_junction(
    harness_id: UUID,
    junction_id: UUID,
    name: str,
    gateway: HarnessEditGateway,
) -> None:
    """
    Rename one junction without changing its control or pathway relationships.

    Clearing the name restores an available generated junction designation.
    """
    if not isinstance(name, str):
        raise ValueError("Junction name must be a string.")
    original, definition = _read_definition(harness_id, gateway)
    junction = next(
        (candidate for candidate in definition.junctions if candidate.junction_id == junction_id),
        None,
    )
    if junction is None:
        raise ValueError("Selected junction does not exist in this harness.")
    resolved_name = next_available_name(
        name.strip() or "Junction 01",
        (
            candidate.name
            for candidate in definition.junctions
            if candidate.junction_id != junction_id
        ),
    )
    updated = replace(junction, name=resolved_name)
    _persist(
        harness_id,
        original,
        replace(
            definition,
            junctions=tuple(
                updated if candidate.junction_id == junction_id else candidate
                for candidate in definition.junctions
            ),
        ),
        gateway,
    )


def _replace_junction_relationships(
    definition: HarnessDefinition,
    junction_id: UUID,
    pathway_relationships: tuple[JunctionPathwayRelationship, ...],
) -> tuple[JunctionDefinition, HarnessDefinition]:
    """
    Build and validate one deterministic junction-relationship replacement.

    This deliberately validates junction topology rather than whole-harness
    generation readiness, so a wire-free draft remains editable.
    """
    junction = next(
        (candidate for candidate in definition.junctions if candidate.junction_id == junction_id),
        None,
    )
    if junction is None:
        raise ValueError("Selected junction does not exist in this harness.")
    pathway_order = {pathway.pathway_id: index for index, pathway in enumerate(definition.pathways)}
    if any(relationship.pathway_id not in pathway_order for relationship in pathway_relationships):
        raise ValueError("A selected junction pathway no longer exists.")
    relationship_keys = {
        (relationship.pathway_id, relationship.endpoint) for relationship in pathway_relationships
    }
    if len(relationship_keys) != len(pathway_relationships):
        raise ValueError("A pathway endpoint may be selected only once per junction.")
    ordered_relationships = tuple(
        sorted(
            pathway_relationships,
            key=lambda relationship: (
                pathway_order[relationship.pathway_id],
                0 if relationship.endpoint is PathwayEndpoint.START else 1,
            ),
        )
    )
    updated_junction = replace(junction, pathway_relationships=ordered_relationships)
    updated = replace(
        definition,
        junctions=tuple(
            updated_junction if candidate.junction_id == junction_id else candidate
            for candidate in definition.junctions
        ),
    )
    issues = tuple(
        issue for issue in validate_harness(updated) if issue.path.startswith("junctions[")
    )
    if issues:
        raise ValueError(issues[0].message)
    return updated_junction, updated


def suggest_pathway_extension_name(
    harness_id: UUID,
    pathway_id: UUID,
    gateway: HarnessEditGateway,
) -> str:
    """
    Return the next root-sequenced extension name for a pathway chain.
    """
    _original, definition = _read_definition(harness_id, gateway)
    pathway = _require_pathway(definition, pathway_id)
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
    root = _require_pathway(definition, root_id)
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
    original, definition = _read_definition(harness_id, gateway)
    pathway = _require_pathway(definition, pathway_id)
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
        *(group.wire_group_id for group in definition.wire_groups),
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
    )
    following_pathway = PathwayDefinition(
        pathway_id=following_pathway_id,
        name=resolved_name,
        routing_mode=pathway.routing_mode,
        ordered_control_ids=pathway.ordered_control_ids[control_index + 1 :],
        end_name=pathway.end_name,
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
    _persist(harness_id, original, updated, gateway)
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
    original, definition = _read_definition(harness_id, gateway)
    pathway = _require_pathway(definition, pathway_id)
    if not 0 <= insertion_index <= len(pathway.ordered_control_ids):
        raise ValueError("Refine insertion position is outside the pathway.")
    insertion_index = _clamp_pathway_insertion_index(
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
        pathways=_replace_pathway(definition, updated_pathway),
    )
    _persist(harness_id, original, updated, gateway)
    return control


def append_end_guides(
    harness_id: UUID,
    connection_id: UUID,
    guide_entity_tokens: tuple[str, ...],
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
) -> Connection:
    """
    Append ordered guide profiles to one end without modifying its pathway.
    """
    normalized_tokens = tuple(token.strip() for token in guide_entity_tokens)
    if not normalized_tokens or any(not token for token in normalized_tokens):
        raise ValueError("Select at least one valid end guide profile.")
    original, definition = _read_definition(harness_id, gateway)
    if all(end.connection_id != connection_id for end in definition.standalone_ends):
        raise ValueError("Selected standalone end does not exist in this harness.")
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected standalone end has a missing connection.")
    registered_tokens = {
        token.strip() for candidate in definition.connections for token in candidate.member_tokens
    } | {control.entity_token.strip() for control in definition.controls if control.entity_token}
    if len(set(normalized_tokens)) != len(normalized_tokens):
        raise ValueError("Each added end guide must reference distinct geometry.")
    if any(token in registered_tokens for token in normalized_tokens):
        raise ValueError("Selected guide geometry is already registered in this harness.")
    new_member_ids = tuple(id_factory() for _token in normalized_tokens)
    existing_ids = {
        definition.harness_id,
        *(item.connection_id for item in definition.connections),
        *(member_id for item in definition.connections for member_id in item.member_identities),
        *(control.control_id for control in definition.controls),
        *(pathway.pathway_id for pathway in definition.pathways),
        *(junction.junction_id for junction in definition.junctions),
        *(group.wire_group_id for group in definition.wire_groups),
    }
    if len(set(new_member_ids)) != len(new_member_ids) or any(
        identity in existing_ids for identity in new_member_ids
    ):
        raise ValueError("Generated end-guide identity is already in use.")
    member_interpolations = connection.member_interpolations
    if member_interpolations:
        member_interpolations = (*member_interpolations, *(None for _ in normalized_tokens))
    updated_connection = replace(
        connection,
        additional_entity_tokens=(
            *connection.additional_entity_tokens,
            *normalized_tokens,
        ),
        member_ids=(*connection.member_identities, *new_member_ids),
        member_interpolations=member_interpolations,
    )
    updated = replace(
        definition,
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    _persist(harness_id, original, updated, gateway)
    return updated_connection


def add_end_refine(
    harness_id: UUID,
    connection_id: UUID,
    insertion_index: int,
    geometry: RefineGeometry,
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
) -> ControlStructure:
    """
    Insert an unconstrained refine between one end's guides and pathway boundary.
    """
    if isinstance(insertion_index, bool) or not isinstance(insertion_index, int):
        raise ValueError("End refine insertion position must be an integer.")
    if not isinstance(geometry, RefineGeometry):
        raise ValueError("Refine geometry is invalid.")
    original, definition = _read_definition(harness_id, gateway)
    end = next(
        (item for item in definition.standalone_ends if item.connection_id == connection_id),
        None,
    )
    if end is None:
        raise ValueError("Selected standalone end does not exist in this harness.")
    if not 0 <= insertion_index <= len(end.ordered_control_ids):
        raise ValueError("End refine insertion position is outside the end stack.")
    control = ControlStructure(
        control_id=id_factory(),
        name=next_available_name("Refine Point 01", (item.name for item in definition.controls)),
        kind=ControlKind.REFINE,
        entity_token="",
        interpolation=definition.gate_defaults,
        refine_geometry=geometry,
    )
    existing_ids = {
        definition.harness_id,
        *(item.connection_id for item in definition.connections),
        *(member_id for item in definition.connections for member_id in item.member_identities),
        *(item.control_id for item in definition.controls),
        *(pathway.pathway_id for pathway in definition.pathways),
        *(junction.junction_id for junction in definition.junctions),
        *(group.wire_group_id for group in definition.wire_groups),
    }
    if control.control_id in existing_ids:
        raise ValueError("Generated refine identity is already in use.")
    ordered_control_ids = list(end.ordered_control_ids)
    ordered_control_ids.insert(insertion_index, control.control_id)
    updated_end = replace(end, ordered_control_ids=tuple(ordered_control_ids))
    updated = replace(
        definition,
        controls=(*definition.controls, control),
        standalone_ends=tuple(
            updated_end if item.connection_id == connection_id else item
            for item in definition.standalone_ends
        ),
    )
    _persist(harness_id, original, updated, gateway)
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
    original, definition = _read_definition(harness_id, gateway)
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
    _persist(harness_id, original, updated, gateway)
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

    original, definition = _read_definition(harness_id, gateway)
    pathway = _require_pathway(definition, pathway_id)
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

    insertion_index = _clamp_pathway_insertion_index(
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
        pathways=_replace_pathway(definition, updated_pathway),
    )
    _persist(harness_id, original, updated, gateway)
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
    original, definition = _read_definition(harness_id, gateway)
    pathway = _require_pathway(definition, pathway_id)
    ordered_ids = list(pathway.ordered_control_ids)
    try:
        current_index = ordered_ids.index(control_id)
    except ValueError as error:
        raise ValueError("Selected gate does not belong to this pathway.") from error
    target_index = current_index + offset
    if target_index < 0 or target_index >= len(ordered_ids):
        raise ValueError("Selected gate is already at that end of the pathway.")
    locked_indexes = _locked_pathway_control_indexes(definition, pathway)
    if current_index in locked_indexes or target_index in locked_indexes:
        raise ValueError("A junction-related or standalone pathway endpoint cannot be reordered.")
    ordered_ids.insert(target_index, ordered_ids.pop(current_index))
    updated_pathway = replace(pathway, ordered_control_ids=tuple(ordered_ids))
    updated = replace(definition, pathways=_replace_pathway(definition, updated_pathway))
    _persist(harness_id, original, updated, gateway)
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
    original, definition = _read_definition(harness_id, gateway)
    pathway = _require_pathway(definition, pathway_id)
    if control_id not in pathway.ordered_control_ids:
        raise ValueError("Selected gate does not belong to this pathway.")
    if len(pathway.ordered_control_ids) == 1:
        raise ValueError("A pathway must retain at least one gate.")
    control_index = pathway.ordered_control_ids.index(control_id)
    if control_index in _locked_pathway_control_indexes(definition, pathway):
        raise ValueError("A junction-related or standalone pathway endpoint cannot be removed.")
    updated_pathway = replace(
        pathway,
        ordered_control_ids=tuple(
            item for item in pathway.ordered_control_ids if item != control_id
        ),
    )
    pathways = _replace_pathway(definition, updated_pathway)
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
    _persist(harness_id, original, updated, gateway)
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
    original, definition = _read_definition(harness_id, gateway)
    _require_pathway(definition, pathway_id)
    deleted_pathway_ids = _pathway_deletion_ids(definition, pathway_id)
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
        wire_groups=_prune_wire_groups(definition.wire_groups, referenced_connection_ids),
    )
    _persist(harness_id, original, updated, gateway)


def remove_junction(
    harness_id: UUID,
    junction_id: UUID,
    gateway: HarnessEditGateway,
) -> None:
    """
    Remove one junction and its dedicated control without changing neighboring topology.
    """
    original, definition = _read_definition(harness_id, gateway)
    junction = _require_junction(definition, junction_id)
    updated = replace(
        definition,
        controls=tuple(
            control for control in definition.controls if control.control_id != junction.control_id
        ),
        junctions=tuple(
            candidate for candidate in definition.junctions if candidate.junction_id != junction_id
        ),
    )
    _persist(harness_id, original, updated, gateway)


def set_harness_material_defaults(
    harness_id: UUID,
    settings: WireMaterialSettings,
    gateway: HarnessEditGateway,
) -> None:
    """
    Replace the parent material settings inherited by wire groups without overrides.
    """
    if not isinstance(settings, WireMaterialSettings):
        raise ValueError("Harness material defaults are invalid.")
    original, definition = _read_definition(harness_id, gateway)
    _persist(
        harness_id,
        original,
        replace(definition, material_defaults=settings),
        gateway,
    )


def set_harness_properties(
    harness_id: UUID,
    insulation_material: str,
    conductor_material: str,
    manufacturer: str,
    part_number: str,
    notes: str,
    gateway: HarnessEditGateway,
) -> None:
    """
    Replace inheritable construction and catalog properties without changing appearance.
    """
    original, definition = _read_definition(harness_id, gateway)
    updated_defaults = replace(
        definition.material_defaults,
        insulation_material=insulation_material,
        conductor_material=conductor_material,
        manufacturer=manufacturer,
        part_number=part_number,
        notes=notes,
    )
    _persist(
        harness_id,
        original,
        replace(definition, material_defaults=updated_defaults),
        gateway,
    )


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
    original, definition = _read_definition(harness_id, gateway)
    pathway = _require_pathway(definition, pathway_id)
    normalized = name.strip()
    if field == "name":
        normalized = next_available_name(
            normalized or "Pathway 01",
            (item.name for item in definition.pathways if item.pathway_id != pathway_id),
        )
    updated = replace(pathway, **{field: normalized})
    _persist(
        harness_id,
        original,
        replace(definition, pathways=_replace_pathway(definition, updated)),
        gateway,
    )


def remove_standalone_end(
    harness_id: UUID,
    connection_id: UUID,
    gateway: HarnessEditGateway,
) -> None:
    """
    Remove one disconnected end association and its owned connection metadata.

    Referenced Fusion geometry is not deleted.
    """
    original, definition = _read_definition(harness_id, gateway)
    removed_end = next(
        (end for end in definition.standalone_ends if end.connection_id == connection_id),
        None,
    )
    if removed_end is None:
        raise ValueError("Selected standalone end does not exist in this harness.")
    removed_control_ids = set(removed_end.ordered_control_ids)
    updated = replace(
        definition,
        controls=tuple(
            control
            for control in definition.controls
            if control.control_id not in removed_control_ids
        ),
        connections=tuple(
            connection
            for connection in definition.connections
            if connection.connection_id != connection_id
        ),
        standalone_ends=tuple(
            end for end in definition.standalone_ends if end.connection_id != connection_id
        ),
        wire_groups=_prune_wire_groups(
            definition.wire_groups,
            {connection.connection_id for connection in definition.connections} - {connection_id},
        ),
    )
    _persist(harness_id, original, updated, gateway)


def rename_standalone_end(
    harness_id: UUID,
    connection_id: UUID,
    name: str,
    gateway: HarnessEditGateway,
) -> None:
    """
    Rename one pathway end while preserving its connection and route identity.
    """
    if not isinstance(name, str):
        raise ValueError("Standalone end name must be a string.")
    original, definition = _read_definition(harness_id, gateway)
    if all(end.connection_id != connection_id for end in definition.standalone_ends):
        raise ValueError("Selected standalone end does not exist in this harness.")
    connection = next(
        (
            candidate
            for candidate in definition.connections
            if candidate.connection_id == connection_id
        ),
        None,
    )
    if connection is None:
        raise ValueError("Selected standalone end has a missing connection.")
    updated_connection = replace(connection, name=name.strip())
    updated = replace(
        definition,
        connections=tuple(
            updated_connection if candidate.connection_id == connection_id else candidate
            for candidate in definition.connections
        ),
    )
    _persist(harness_id, original, updated, gateway)


def _validate_offset(offset: int) -> None:
    """
    Require a single-position ordered move.
    """
    if offset not in {-1, 1}:
        raise ValueError("Ordered moves must use an offset of -1 or 1.")


def _read_definition(
    harness_id: UUID,
    gateway: HarnessEditGateway,
) -> tuple[str, HarnessDefinition]:
    """
    Read both the exact serialized value and its parsed definition.
    """
    original = gateway.read_harness_definition(harness_id)
    return original, loads(original)


def _require_pathway(
    definition: HarnessDefinition,
    pathway_id: UUID,
) -> PathwayDefinition:
    """
    Return an existing pathway or reject a stale palette identity.
    """
    pathway = next(
        (item for item in definition.pathways if item.pathway_id == pathway_id),
        None,
    )
    if pathway is None:
        raise ValueError("Selected pathway does not exist in this harness.")
    return pathway


def _require_junction(
    definition: HarnessDefinition,
    junction_id: UUID,
) -> JunctionDefinition:
    """
    Return an existing junction or reject a stale palette identity.
    """
    junction = next(
        (item for item in definition.junctions if item.junction_id == junction_id),
        None,
    )
    if junction is None:
        raise ValueError("Selected junction does not exist in this harness.")
    return junction


def _pathway_deletion_ids(
    definition: HarnessDefinition,
    pathway_id: UUID,
) -> set[UUID]:
    """
    Return a pathway and its downstream branch when every junction input is removed.

    A junction always remains. Its following pathways join the cascade only after every
    pathway entering that junction is already scheduled for deletion.
    """
    return _pathway_branch_deletion_ids(definition, {pathway_id})


def _pathway_branch_deletion_ids(
    definition: HarnessDefinition,
    root_pathway_ids: set[UUID],
) -> set[UUID]:
    """
    Return exclusively downstream pathways reached from one or more root pathways.
    """
    deleted_pathway_ids = set(root_pathway_ids)
    changed = True
    while changed:
        changed = False
        for junction in definition.junctions:
            incoming_pathway_ids = {
                relationship.pathway_id
                for relationship in junction.pathway_relationships
                if relationship.endpoint is PathwayEndpoint.END
            }
            if not incoming_pathway_ids or not incoming_pathway_ids <= deleted_pathway_ids:
                continue
            following_pathway_ids = {
                relationship.pathway_id
                for relationship in junction.pathway_relationships
                if relationship.endpoint is PathwayEndpoint.START
            }
            new_pathway_ids = following_pathway_ids - deleted_pathway_ids
            if new_pathway_ids:
                deleted_pathway_ids.update(new_pathway_ids)
                changed = True
    return deleted_pathway_ids


def _replace_pathway(
    definition: HarnessDefinition,
    updated_pathway: PathwayDefinition,
) -> tuple[PathwayDefinition, ...]:
    """
    Replace one pathway without changing collection order.
    """
    return tuple(
        updated_pathway if item.pathway_id == updated_pathway.pathway_id else item
        for item in definition.pathways
    )


def _prune_wire_groups(
    groups: tuple[WireGroupDefinition, ...],
    retained_connection_ids: set[UUID],
) -> tuple[WireGroupDefinition, ...]:
    """
    Remove unavailable members and discard groups that no longer connect two ends.
    """
    pruned = (
        replace(
            group,
            connection_ids=tuple(
                connection_id
                for connection_id in group.connection_ids
                if connection_id in retained_connection_ids
            ),
        )
        for group in groups
    )
    return tuple(group for group in pruned if len(group.connection_ids) >= 2)


def _related_pathway_endpoints(
    definition: HarnessDefinition,
    pathway_id: UUID,
) -> set[PathwayEndpoint]:
    """
    Return endpoint boundaries anchored by junctions or standalone ends.
    """
    junction_endpoints = {
        relationship.endpoint
        for junction in definition.junctions
        for relationship in junction.pathway_relationships
        if relationship.pathway_id == pathway_id
    }
    standalone_endpoints = {
        end.endpoint for end in definition.standalone_ends if end.pathway_id == pathway_id
    }
    return junction_endpoints | standalone_endpoints


def _locked_pathway_control_indexes(
    definition: HarnessDefinition,
    pathway: PathwayDefinition,
) -> set[int]:
    """
    Return control positions that define anchored pathway boundaries.
    """
    if not pathway.ordered_control_ids:
        return set()
    endpoints = _related_pathway_endpoints(definition, pathway.pathway_id)
    locked: set[int] = set()
    if PathwayEndpoint.START in endpoints:
        locked.add(0)
    if PathwayEndpoint.END in endpoints:
        locked.add(len(pathway.ordered_control_ids) - 1)
    return locked


def _clamp_pathway_insertion_index(
    definition: HarnessDefinition,
    pathway: PathwayDefinition,
    requested_index: int,
) -> int:
    """
    Clamp new controls inside endpoint boundaries reserved by junctions.
    """
    endpoints = _related_pathway_endpoints(definition, pathway.pathway_id)
    minimum = 1 if PathwayEndpoint.START in endpoints else 0
    maximum = (
        len(pathway.ordered_control_ids) - 1
        if PathwayEndpoint.END in endpoints
        else len(pathway.ordered_control_ids)
    )
    if maximum < minimum:
        raise ValueError(
            "A one-control pathway related at both ends has no interior insertion position."
        )
    return min(max(requested_index, minimum), maximum)


def _persist(
    harness_id: UUID,
    original_serialized: str,
    definition: HarnessDefinition,
    gateway: HarnessEditGateway,
) -> None:
    """
    Persist one edit and restore the exact prior value after failure.
    """
    try:
        gateway.replace_harness_definition(harness_id, dumps(definition))
    except Exception as persistence_error:
        try:
            gateway.replace_harness_definition(harness_id, original_serialized)
        except Exception as rollback_error:
            message = (
                f"Failed to persist the harness edit and restore its definition: {rollback_error}"
            )
            raise HarnessEditError(message) from persistence_error
        raise


def set_interpolation(
    harness_id: UUID,
    target: str,
    settings: InterpolationSettings,
    gateway: HarnessEditGateway,
    target_id: Optional[UUID] = None,
    end_defaults: Optional[InterpolationSettings] = None,
    apply_existing: bool = False,
    member_id: Optional[UUID] = None,
    use_defaults: bool = False,
    minimum_clearance_mm: Optional[float] = None,
    auto_transition_preset: Optional[AutoTransitionPreset] = None,
) -> None:
    """
    Save section controls or creation defaults in one reversible metadata edit.

    Optionally apply both presets to existing sections in the same transaction.
    """
    original, definition = _read_definition(harness_id, gateway)
    if target == "defaults":
        if end_defaults is None:
            raise ValueError("Both gate and end defaults are required.")
        clearance = (
            definition.minimum_clearance_mm
            if minimum_clearance_mm is None
            else minimum_clearance_mm
        )
        if (
            isinstance(clearance, bool)
            or not isinstance(clearance, (int, float))
            or not math.isfinite(clearance)
            or clearance < 0.0
        ):
            raise ValueError("Minimum member clearance must be finite and nonnegative.")
        updated = replace(
            definition,
            gate_defaults=settings,
            end_defaults=end_defaults,
            minimum_clearance_mm=float(clearance),
            auto_transition_preset=(
                definition.auto_transition_preset
                if auto_transition_preset is None
                else auto_transition_preset
            ),
        )
        if apply_existing:
            updated = replace(
                updated,
                controls=tuple(
                    replace(item, interpolation=settings)
                    if not item.interpolation_is_override
                    else item
                    for item in definition.controls
                ),
                connections=tuple(
                    replace(item, interpolation=end_defaults) for item in definition.connections
                ),
            )
    elif target == "gate":
        if not any(item.control_id == target_id for item in definition.controls):
            raise ValueError("Selected gate no longer exists.")
        updated = replace(
            definition,
            controls=tuple(
                replace(
                    item,
                    interpolation=definition.gate_defaults if use_defaults else settings,
                    interpolation_is_override=not use_defaults,
                )
                if item.control_id == target_id
                else item
                for item in definition.controls
            ),
        )
    elif target == "end":
        connection = next(
            (item for item in definition.connections if item.connection_id == target_id), None
        )
        if connection is None:
            raise ValueError("Selected end section no longer exists.")
        if member_id is None:
            edited = replace(connection, interpolation=settings, member_interpolations=())
        else:
            if member_id not in connection.member_identities:
                raise ValueError("Selected end member no longer exists.")
            edited = replace(
                connection,
                interpolation=definition.end_defaults if use_defaults else connection.interpolation,
                member_interpolations=tuple(
                    (None if use_defaults else settings) if identity == member_id else previous
                    for identity, previous in zip(
                        connection.member_identities,
                        connection.member_interpolations or (None,) * len(connection.member_tokens),
                    )
                ),
            )
        updated = replace(
            definition,
            connections=tuple(
                edited if item.connection_id == target_id else item
                for item in definition.connections
            ),
        )
    else:
        raise ValueError("Unsupported interpolation target.")
    _persist(harness_id, original, updated, gateway)
