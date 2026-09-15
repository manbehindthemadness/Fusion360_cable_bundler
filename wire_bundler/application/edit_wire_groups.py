"""
Commit the Wire Editor's staged end and connectivity changes atomically.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Optional
from uuid import UUID, uuid4

from ..domain import (
    HarnessDefinition,
    PathwayEndpoint,
    WireGroupDefinition,
    validate_harness,
)
from .edit_harness import HarnessEditGateway, _persist, _read_definition


@dataclass(frozen=True)
class WireEditorPairing:
    """
    Pair one end from each selected Wire Editor boundary.
    """

    left_connection_id: UUID
    right_connection_id: UUID


@dataclass(frozen=True)
class WireEditorRename:
    """
    Stage one standalone-end connection-name replacement.
    """

    connection_id: UUID
    name: str


@dataclass
class _MutableWireGroup:
    """
    Retain a group identity while its staged membership is assembled.
    """

    wire_group_id: UUID
    connection_ids: list[UUID]


def save_wire_editor(
    harness_id: UUID,
    left_pathway_id: UUID,
    left_endpoint: PathwayEndpoint,
    right_pathway_id: UUID,
    right_endpoint: PathwayEndpoint,
    pairings: tuple[WireEditorPairing, ...],
    detached_connection_ids: tuple[UUID, ...],
    renames: tuple[WireEditorRename, ...],
    deleted_connection_ids: tuple[UUID, ...],
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
) -> None:
    """
    Commit all staged Wire Editor changes as one reversible metadata edit.

    Existing groups are extended or merged. Explicitly detached members are
    removed before final pairings are applied, while temporary one-member
    groups retain their identities until reassignment finishes.
    """
    if (left_pathway_id, left_endpoint) == (right_pathway_id, right_endpoint):
        raise ValueError("Wire Editor boundaries must differ.")
    original, definition = _read_definition(harness_id, gateway)
    locations = _wire_end_locations(definition)
    selected_locations = {
        "left": (left_pathway_id, left_endpoint),
        "right": (right_pathway_id, right_endpoint),
    }
    deleted = set(deleted_connection_ids)
    detached = set(detached_connection_ids)
    if len(deleted) != len(deleted_connection_ids):
        raise ValueError("A Wire Editor end may be deleted only once.")
    if len(detached) != len(detached_connection_ids):
        raise ValueError("A Wire Editor end may be detached only once.")
    rename_ids = [rename.connection_id for rename in renames]
    if len(set(rename_ids)) != len(rename_ids):
        raise ValueError("A Wire Editor end may be renamed only once.")
    if deleted.intersection(rename_ids):
        raise ValueError("A deleted Wire Editor end cannot also be renamed.")

    standalone_ids = {end.connection_id for end in definition.standalone_ends}
    selected_ids = {
        connection_id
        for connection_id, location in locations.items()
        if location in selected_locations.values()
    }
    if not deleted.issubset(standalone_ids & selected_ids):
        raise ValueError("A deleted Wire Editor end is stale or not standalone.")
    if not set(rename_ids).issubset(standalone_ids & selected_ids):
        raise ValueError("A renamed Wire Editor end is stale or not standalone.")
    if not detached.issubset(selected_ids):
        raise ValueError("A detached Wire Editor end is stale or outside the selected boundaries.")

    paired_ids: list[UUID] = []
    for pairing in pairings:
        if locations.get(pairing.left_connection_id) != selected_locations["left"]:
            raise ValueError("A pairing contains an end outside the selected left boundary.")
        if locations.get(pairing.right_connection_id) != selected_locations["right"]:
            raise ValueError("A pairing contains an end outside the selected right boundary.")
        paired_ids.extend((pairing.left_connection_id, pairing.right_connection_id))
    if len(set(paired_ids)) != len(paired_ids):
        raise ValueError("A Wire Editor end may appear in only one final pairing.")
    if deleted.intersection(paired_ids):
        raise ValueError("A deleted Wire Editor end cannot appear in a pairing.")

    groups = [
        _MutableWireGroup(group.wire_group_id, list(group.connection_ids))
        for group in definition.wire_groups
    ]
    removed_ids = deleted | detached
    for group in groups:
        group.connection_ids = [
            connection_id
            for connection_id in group.connection_ids
            if connection_id not in removed_ids
        ]

    used_ids = {
        definition.harness_id,
        *(profile.profile_id for profile in definition.profiles),
        *(connection.connection_id for connection in definition.connections),
        *(control.control_id for control in definition.controls),
        *(pathway.pathway_id for pathway in definition.pathways),
        *(junction.junction_id for junction in definition.junctions),
        *(wire.wire_id for wire in definition.wires),
        *(group.wire_group_id for group in definition.wire_groups),
    }
    for pairing in pairings:
        left_index = _wire_group_member_index(groups, pairing.left_connection_id)
        right_index = _wire_group_member_index(groups, pairing.right_connection_id)
        if left_index is not None and left_index == right_index:
            continue
        if left_index is None and right_index is None:
            group_id = id_factory()
            if group_id in used_ids:
                raise ValueError("Generated wire-group identity is already in use.")
            used_ids.add(group_id)
            groups.append(
                _MutableWireGroup(
                    group_id,
                    [pairing.left_connection_id, pairing.right_connection_id],
                )
            )
        elif left_index is None:
            assert right_index is not None
            groups[right_index].connection_ids.append(pairing.left_connection_id)
        elif right_index is None:
            groups[left_index].connection_ids.append(pairing.right_connection_id)
        else:
            keep_index, remove_index = sorted((left_index, right_index))
            groups[keep_index].connection_ids.extend(groups[remove_index].connection_ids)
            groups.pop(remove_index)

    updated_groups = tuple(
        WireGroupDefinition(group.wire_group_id, tuple(group.connection_ids))
        for group in groups
        if len(group.connection_ids) >= 2
    )
    renamed_connections = {rename.connection_id: rename.name.strip() for rename in renames}
    updated = replace(
        definition,
        connections=tuple(
            replace(connection, name=renamed_connections[connection.connection_id])
            if connection.connection_id in renamed_connections
            else connection
            for connection in definition.connections
            if connection.connection_id not in deleted
        ),
        standalone_ends=tuple(
            end for end in definition.standalone_ends if end.connection_id not in deleted
        ),
        wire_groups=updated_groups,
    )
    group_issues = tuple(
        issue for issue in validate_harness(updated) if issue.path.startswith("wire_groups[")
    )
    if group_issues:
        raise ValueError(group_issues[0].message)
    _persist(harness_id, original, updated, gateway)


def _wire_end_locations(
    definition: HarnessDefinition,
) -> dict[UUID, tuple[UUID, PathwayEndpoint]]:
    """
    Resolve every physical wire end to its authoritative pathway boundary.
    """
    locations = {
        end.connection_id: (end.pathway_id, end.endpoint) for end in definition.standalone_ends
    }
    for wire in definition.wires:
        if not wire.ordered_pathway_ids:
            continue
        locations[wire.start_connection_id] = (
            wire.ordered_pathway_ids[0],
            PathwayEndpoint.START,
        )
        locations[wire.end_connection_id] = (
            wire.ordered_pathway_ids[-1],
            PathwayEndpoint.END,
        )
    return locations


def _wire_group_member_index(
    groups: list[_MutableWireGroup],
    connection_id: UUID,
) -> Optional[int]:
    """
    Return the current group index containing one connection, if any.
    """
    return next(
        (index for index, group in enumerate(groups) if connection_id in group.connection_ids),
        None,
    )
