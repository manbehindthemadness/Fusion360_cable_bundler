"""Standalone-end guide, refine, naming, and deletion edits."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from uuid import UUID, uuid4

from ...domain import (
    Connection,
    ControlKind,
    ControlStructure,
    PathwayEndpoint,
    RefineGeometry,
    next_available_name,
)
from .support import (
    persist_definition,
    prune_cable_groups,
    read_definition,
)
from .types import HarnessEditGateway


# noinspection DuplicatedCode
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
    original, definition = read_definition(harness_id, gateway)
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
        *(group.cable_group_id for group in definition.cable_groups),
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
    persist_definition(harness_id, original, updated, gateway)
    return updated_connection


def switch_standalone_end(
    harness_id: UUID,
    connection_id: UUID,
    gateway: HarnessEditGateway,
) -> None:
    """
    Move one disconnected end to the opposite boundary of its pathway.

    Connected ends must first be detached so this edit cannot silently change
    an existing cable group's route.
    """
    original, definition = read_definition(harness_id, gateway)
    end = next(
        (
            candidate
            for candidate in definition.standalone_ends
            if candidate.connection_id == connection_id
        ),
        None,
    )
    if end is None:
        raise ValueError("Selected standalone end does not exist in this harness.")
    if any(connection_id in group.connection_ids for group in definition.cable_groups):
        raise ValueError("Only disconnected standalone ends can switch pathway boundaries.")
    switched_endpoint = (
        PathwayEndpoint.END if end.endpoint is PathwayEndpoint.START else PathwayEndpoint.START
    )
    updated_end = replace(end, endpoint=switched_endpoint)
    updated = replace(
        definition,
        standalone_ends=tuple(
            updated_end if candidate.connection_id == connection_id else candidate
            for candidate in definition.standalone_ends
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


# noinspection DuplicatedCode
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
    original, definition = read_definition(harness_id, gateway)
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
        *(group.cable_group_id for group in definition.cable_groups),
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
    persist_definition(harness_id, original, updated, gateway)
    return control


def remove_standalone_end(
    harness_id: UUID,
    connection_id: UUID,
    gateway: HarnessEditGateway,
) -> None:
    """
    Remove one disconnected end association and its owned connection metadata.

    Referenced Fusion geometry is not deleted.
    """
    original, definition = read_definition(harness_id, gateway)
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
        cable_groups=prune_cable_groups(
            definition.cable_groups,
            {connection.connection_id for connection in definition.connections} - {connection_id},
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


# noinspection DuplicatedCode
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
    original, definition = read_definition(harness_id, gateway)
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
    persist_definition(harness_id, original, updated, gateway)
