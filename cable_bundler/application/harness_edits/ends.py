"""Standalone-end guide, refine, naming, and deletion edits."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from uuid import UUID, uuid4

from ...domain import (
    CableEndAttachment,
    CableVisualOverrides,
    Connection,
    ControlKind,
    ControlStructure,
    Metadata,
    PathwayEndpoint,
    RefineGeometry,
    StandaloneEndDefinition,
    next_available_name,
)
from .support import (
    persist_definition,
    prune_cable_groups,
    read_definition,
)
from .types import HarnessEditGateway


# noinspection DuplicatedCode
def attach_cable_end(
    harness_id: UUID,
    connection_id: UUID,
    attachment_id: UUID,
    attachment: CableEndAttachment,
    gateway: HarnessEditGateway,
) -> None:
    """
    Attach or reconnect one existing cable end to an external Fusion target.
    """
    if not isinstance(attachment, CableEndAttachment) or not attachment.has_target:
        raise ValueError("Cable-end attachment is invalid.")
    original, definition = read_definition(harness_id, gateway)
    if all(end.connection_id != connection_id for end in definition.standalone_ends):
        raise ValueError("Selected cable end does not exist in this harness.")
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end has a missing connection.")
    existing = _cable_end_attachment(connection, attachment_id)
    if attachment.entity_token in connection.member_tokens:
        raise ValueError("A cable end cannot attach to its own guide geometry.")
    if any(
        item.attachment_id != attachment_id
        and item.has_target
        and item.entity_token == attachment.entity_token
        for item in connection.attachments
    ):
        raise ValueError("Each cable-end connection requires a unique target.")
    completed_attachment = replace(
        attachment,
        attachment_id=attachment_id,
        name=attachment.name or existing.name,
        metadata=existing.metadata,
        ordered_control_ids=existing.ordered_control_ids,
        visual_overrides=existing.visual_overrides,
    )
    updated_connection = _replace_cable_end_attachment(
        connection, attachment_id, completed_attachment
    )
    updated = replace(
        definition,
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


# noinspection DuplicatedCode
def add_cable_end_connection(
    harness_id: UUID,
    connection_id: UUID,
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
) -> CableEndAttachment:
    """
    Persist an unattached external connection node for one cable end.
    """
    original, definition = read_definition(harness_id, gateway)
    if all(end.connection_id != connection_id for end in definition.standalone_ends):
        raise ValueError("Selected cable end does not exist in this harness.")
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end has a missing connection.")
    attachment = CableEndAttachment(None, attachment_id=id_factory())
    if connection.attachment is None:
        updated_connection = replace(connection, attachment=attachment)
    else:
        updated_connection = replace(
            connection,
            additional_attachments=(*connection.additional_attachments, attachment),
        )
    updated = replace(
        definition,
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    persist_definition(harness_id, original, updated, gateway)
    return attachment


def rename_cable_end_attachment(
    harness_id: UUID,
    connection_id: UUID,
    attachment_id: UUID,
    name: str,
    gateway: HarnessEditGateway,
) -> None:
    """
    Set or clear the display-name override for one cable-end attachment.
    """
    if not isinstance(name, str):
        raise ValueError("Connection name must be text.")
    original, definition = read_definition(harness_id, gateway)
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end does not exist.")
    attachment = _cable_end_attachment(connection, attachment_id)
    updated_connection = _replace_cable_end_attachment(
        connection, attachment_id, replace(attachment, name=name.strip())
    )
    updated = replace(
        definition,
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


def set_cable_end_attachment_properties(
    harness_id: UUID,
    connection_id: UUID,
    attachment_id: UUID,
    metadata: Metadata,
    gateway: HarnessEditGateway,
) -> None:
    """
    Replace searchable metadata owned by one external cable-end connection.
    """
    original, definition = read_definition(harness_id, gateway)
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end does not exist.")
    attachment = _cable_end_attachment(connection, attachment_id)
    updated_connection = _replace_cable_end_attachment(
        connection, attachment_id, replace(attachment, metadata=metadata)
    )
    updated = replace(
        definition,
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


def set_cable_end_attachment_visual_overrides(
    harness_id: UUID,
    connection_id: UUID,
    attachment_id: UUID,
    overrides: CableVisualOverrides,
    gateway: HarnessEditGateway,
) -> None:
    """
    Replace branch visuals for one node on a multi-connection cable end.
    """
    if not isinstance(overrides, CableVisualOverrides):
        raise ValueError("Connection material overrides are invalid.")
    original, definition = read_definition(harness_id, gateway)
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end does not exist.")
    if len(connection.attachments) <= 1:
        raise ValueError("A single connection inherits its cable-group materials.")
    attachment = _cable_end_attachment(connection, attachment_id)
    updated_connection = _replace_cable_end_attachment(
        connection,
        attachment_id,
        replace(attachment, visual_overrides=overrides),
    )
    updated = replace(
        definition,
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


def remove_cable_end_attachment(
    harness_id: UUID,
    connection_id: UUID,
    attachment_id: UUID,
    gateway: HarnessEditGateway,
) -> None:
    """
    Detach one cable end without deleting its referenced Fusion target.
    """
    original, definition = read_definition(harness_id, gateway)
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end does not exist.")
    removed_attachment = _cable_end_attachment(connection, attachment_id)
    remaining = tuple(
        attachment
        for attachment in connection.attachments
        if attachment.attachment_id != attachment_id
    )
    if len(remaining) == 1:
        remaining = (replace(remaining[0], visual_overrides=CableVisualOverrides()),)
    updated_connection = replace(
        connection,
        attachment=remaining[0] if remaining else None,
        additional_attachments=remaining[1:],
    )
    updated = replace(
        definition,
        controls=tuple(
            control
            for control in definition.controls
            if control.control_id not in removed_attachment.ordered_control_ids
        ),
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


def _cable_end_attachment(
    connection: Connection,
    attachment_id: UUID,
) -> CableEndAttachment:
    """
    Resolve one external connection node by its stable identity.
    """
    attachment = next(
        (item for item in connection.attachments if item.attachment_id == attachment_id),
        None,
    )
    if attachment is None:
        raise ValueError("Selected cable-end connection does not exist.")
    return attachment


def _replace_cable_end_attachment(
    connection: Connection,
    attachment_id: UUID,
    replacement: CableEndAttachment,
) -> Connection:
    """
    Replace one external connection node without changing collection order.
    """
    attachments = tuple(
        replacement if item.attachment_id == attachment_id else item
        for item in connection.attachments
    )
    return replace(
        connection,
        attachment=attachments[0],
        additional_attachments=attachments[1:],
    )


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


# noinspection DuplicatedCode
def remove_end_guide(
    harness_id: UUID,
    connection_id: UUID,
    member_id: UUID,
    gateway: HarnessEditGateway,
) -> Connection:
    """
    Remove one guide from an end while retaining at least one terminal guide.
    """
    original, definition = read_definition(harness_id, gateway)
    if all(end.connection_id != connection_id for end in definition.standalone_ends):
        raise ValueError("Selected standalone end does not exist in this harness.")
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected standalone end has a missing connection.")
    member_ids = connection.member_identities
    try:
        member_index = member_ids.index(member_id)
    except ValueError as error:
        raise ValueError("Selected guide does not belong to this cable end.") from error
    if len(member_ids) == 1:
        raise ValueError("A cable end must retain at least one guide.")
    remaining_tokens = tuple(
        token for index, token in enumerate(connection.member_tokens) if index != member_index
    )
    remaining_ids = tuple(
        identity for index, identity in enumerate(member_ids) if index != member_index
    )
    remaining_interpolations = (
        tuple(
            settings
            for index, settings in enumerate(connection.member_interpolations)
            if index != member_index
        )
        if connection.member_interpolations
        else ()
    )
    updated_connection = replace(
        connection,
        entity_token=remaining_tokens[0],
        additional_entity_tokens=remaining_tokens[1:],
        member_ids=remaining_ids,
        member_interpolations=remaining_interpolations,
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


def remove_end_control(
    harness_id: UUID,
    connection_id: UUID,
    control_id: UUID,
    gateway: HarnessEditGateway,
) -> StandaloneEndDefinition:
    """
    Remove one end-owned routing control and prune its unreferenced definition.
    """
    original, definition = read_definition(harness_id, gateway)
    end = next(
        (item for item in definition.standalone_ends if item.connection_id == connection_id),
        None,
    )
    if end is None:
        raise ValueError("Selected standalone end does not exist in this harness.")
    if control_id not in end.ordered_control_ids:
        raise ValueError("Selected control does not belong to this cable end.")
    updated_end = replace(
        end,
        ordered_control_ids=tuple(item for item in end.ordered_control_ids if item != control_id),
    )
    standalone_ends = tuple(
        updated_end if item.connection_id == connection_id else item
        for item in definition.standalone_ends
    )
    referenced_control_ids = (
        {item for pathway in definition.pathways for item in pathway.ordered_control_ids}
        | {junction.control_id for junction in definition.junctions}
        | {item for candidate in standalone_ends for item in candidate.ordered_control_ids}
    )
    updated = replace(
        definition,
        controls=tuple(
            control
            for control in definition.controls
            if control.control_id != control_id or control.control_id in referenced_control_ids
        ),
        standalone_ends=standalone_ends,
    )
    persist_definition(harness_id, original, updated, gateway)
    return updated_end


def switch_standalone_end(
    harness_id: UUID,
    connection_id: UUID,
    gateway: HarnessEditGateway,
) -> None:
    """
    Move one unassigned end to the opposite boundary of its pathway.

    Assigned ends must first be detached so this edit cannot silently change
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
        raise ValueError("Only unassigned standalone ends can switch pathway boundaries.")
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


# noinspection DuplicatedCode
def add_connection_refine(
    harness_id: UUID,
    connection_id: UUID,
    attachment_id: UUID,
    insertion_index: int,
    geometry: RefineGeometry,
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
) -> ControlStructure:
    """
    Insert an unconstrained refine between one external target and its end guide.
    """
    if isinstance(insertion_index, bool) or not isinstance(insertion_index, int):
        raise ValueError("Connection refine insertion position must be an integer.")
    if not isinstance(geometry, RefineGeometry):
        raise ValueError("Refine geometry is invalid.")
    original, definition = read_definition(harness_id, gateway)
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end does not exist.")
    attachment = _cable_end_attachment(connection, attachment_id)
    if not attachment.has_target:
        raise ValueError("Connect this node before refining its routing span.")
    if not 0 <= insertion_index <= len(attachment.ordered_control_ids):
        raise ValueError("Connection refine insertion position is outside its routing span.")
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
        *(
            item.attachment_id
            for candidate in definition.connections
            for item in candidate.attachments
        ),
        *(item.control_id for item in definition.controls),
        *(pathway.pathway_id for pathway in definition.pathways),
        *(junction.junction_id for junction in definition.junctions),
        *(group.cable_group_id for group in definition.cable_groups),
    }
    if control.control_id in existing_ids:
        raise ValueError("Generated refine identity is already in use.")
    ordered_control_ids = list(attachment.ordered_control_ids)
    ordered_control_ids.insert(insertion_index, control.control_id)
    updated_attachment = replace(
        attachment,
        ordered_control_ids=tuple(ordered_control_ids),
    )
    updated_connection = _replace_cable_end_attachment(
        connection,
        attachment_id,
        updated_attachment,
    )
    updated = replace(
        definition,
        controls=(*definition.controls, control),
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
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
    Remove one unassigned end association and its owned connection metadata.

    Referenced Fusion geometry is not deleted.
    """
    original, definition = read_definition(harness_id, gateway)
    removed_end = next(
        (end for end in definition.standalone_ends if end.connection_id == connection_id),
        None,
    )
    if removed_end is None:
        raise ValueError("Selected standalone end does not exist in this harness.")
    removed_connection = next(
        (
            connection
            for connection in definition.connections
            if connection.connection_id == connection_id
        ),
        None,
    )
    removed_control_ids = set(removed_end.ordered_control_ids) | {
        control_id
        for attachment in (removed_connection.attachments if removed_connection is not None else ())
        for control_id in attachment.ordered_control_ids
    }
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


# noinspection DuplicatedCode
def set_cable_end_properties(
    harness_id: UUID,
    connection_id: UUID,
    metadata: Metadata,
    gateway: HarnessEditGateway,
) -> None:
    """
    Replace searchable metadata without changing end routing or membership.
    """
    original, definition = read_definition(harness_id, gateway)
    if all(end.connection_id != connection_id for end in definition.standalone_ends):
        raise ValueError("Selected cable end does not exist in this harness.")
    connection = next(
        (
            candidate
            for candidate in definition.connections
            if candidate.connection_id == connection_id
        ),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end has a missing connection.")
    updated_connection = replace(connection, metadata=metadata)
    persist_definition(
        harness_id,
        original,
        replace(
            definition,
            connections=tuple(
                updated_connection if candidate.connection_id == connection_id else candidate
                for candidate in definition.connections
            ),
        ),
        gateway,
    )
