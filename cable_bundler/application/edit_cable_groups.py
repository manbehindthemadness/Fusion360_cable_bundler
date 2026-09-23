"""
Commit the Route Editor's staged end and connectivity changes atomically.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Optional
from uuid import UUID, uuid4

from ..domain import (
    DEFAULT_CABLE_DIAMETER_MM,
    CableGroupDefinition,
    CableMaterialOverrides,
    HarnessDefinition,
    Metadata,
    PathwayEndpoint,
    validate_harness,
)
from .edit_harness import HarnessEditGateway
from .harness_edits.support import persist_definition, read_definition


@dataclass(frozen=True)
class CableEditorPairing:
    """
    Pair one end from each selected Route Editor boundary.
    """

    left_connection_id: UUID
    right_connection_id: UUID


@dataclass(frozen=True)
class CableEditorRename:
    """
    Stage one standalone-end connection-name replacement.
    """

    connection_id: UUID
    name: str


@dataclass
class _MutableCableGroup:
    """
    Retain a group identity while its staged membership is assembled.
    """

    cable_group_id: UUID
    connection_ids: list[UUID]
    diameter_mm: float
    material_overrides: CableMaterialOverrides
    metadata_overrides: Metadata
    name: str
    conductor_diameter_mm: Optional[float]


def save_cable_editor(
    harness_id: UUID,
    left_pathway_id: UUID,
    left_endpoint: PathwayEndpoint,
    right_pathway_id: UUID,
    right_endpoint: PathwayEndpoint,
    pairings: tuple[CableEditorPairing, ...],
    detached_connection_ids: tuple[UUID, ...],
    renames: tuple[CableEditorRename, ...],
    deleted_connection_ids: tuple[UUID, ...],
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
) -> None:
    """
    Commit all staged Route Editor changes as one reversible metadata edit.

    Existing groups are extended or merged. Explicitly detached members are
    removed before final pairings are applied, while temporary one-member
    groups retain their identities until reassignment finishes.
    """
    if (left_pathway_id, left_endpoint) == (right_pathway_id, right_endpoint):
        raise ValueError("Route Editor boundaries must differ.")
    original, definition = read_definition(harness_id, gateway)
    locations = cable_end_locations(definition)
    selected_locations = {
        "left": (left_pathway_id, left_endpoint),
        "right": (right_pathway_id, right_endpoint),
    }
    deleted = set(deleted_connection_ids)
    detached = set(detached_connection_ids)
    if len(deleted) != len(deleted_connection_ids):
        raise ValueError("A Route Editor end may be deleted only once.")
    if len(detached) != len(detached_connection_ids):
        raise ValueError("A Route Editor end may be detached only once.")
    rename_ids = [rename.connection_id for rename in renames]
    if len(set(rename_ids)) != len(rename_ids):
        raise ValueError("A Route Editor end may be renamed only once.")
    if deleted.intersection(rename_ids):
        raise ValueError("A deleted Route Editor end cannot also be renamed.")

    standalone_ids = {end.connection_id for end in definition.standalone_ends}
    selected_ids = {
        connection_id
        for connection_id, location in locations.items()
        if location in selected_locations.values()
    }
    if not deleted.issubset(standalone_ids & selected_ids):
        raise ValueError("A deleted Route Editor end is stale or not standalone.")
    if not set(rename_ids).issubset(standalone_ids & selected_ids):
        raise ValueError("A renamed Route Editor end is stale or not standalone.")
    if not detached.issubset(selected_ids):
        raise ValueError("A detached Route Editor end is stale or outside the selected boundaries.")

    paired_ids: list[UUID] = []
    for pairing in pairings:
        if locations.get(pairing.left_connection_id) != selected_locations["left"]:
            raise ValueError("A pairing contains an end outside the selected left boundary.")
        if locations.get(pairing.right_connection_id) != selected_locations["right"]:
            raise ValueError("A pairing contains an end outside the selected right boundary.")
        paired_ids.extend((pairing.left_connection_id, pairing.right_connection_id))
    if len(set(paired_ids)) != len(paired_ids):
        raise ValueError("A Route Editor end may appear in only one final pairing.")
    if deleted.intersection(paired_ids):
        raise ValueError("A deleted Route Editor end cannot appear in a pairing.")

    groups = [
        _MutableCableGroup(
            group.cable_group_id,
            list(group.connection_ids),
            group.diameter_mm,
            group.material_overrides,
            group.metadata_overrides,
            group.name,
            group.conductor_diameter_mm,
        )
        for group in definition.cable_groups
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
        *(connection.connection_id for connection in definition.connections),
        *(control.control_id for control in definition.controls),
        *(pathway.pathway_id for pathway in definition.pathways),
        *(junction.junction_id for junction in definition.junctions),
        *(group.cable_group_id for group in definition.cable_groups),
    }
    for pairing in pairings:
        left_index = _cable_group_member_index(groups, pairing.left_connection_id)
        right_index = _cable_group_member_index(groups, pairing.right_connection_id)
        if left_index is not None and left_index == right_index:
            continue
        if left_index is None and right_index is None:
            group_id = id_factory()
            if group_id in used_ids:
                raise ValueError("Generated cable-group identity is already in use.")
            used_ids.add(group_id)
            groups.append(
                _MutableCableGroup(
                    group_id,
                    [pairing.left_connection_id, pairing.right_connection_id],
                    DEFAULT_CABLE_DIAMETER_MM,
                    CableMaterialOverrides(),
                    (),
                    "",
                    None,
                )
            )
        elif left_index is None:
            assert right_index is not None
            groups[right_index].connection_ids.append(pairing.left_connection_id)
        elif right_index is None:
            assert left_index is not None
            groups[left_index].connection_ids.append(pairing.right_connection_id)
        else:
            assert left_index is not None and right_index is not None
            keep_index, remove_index = sorted((left_index, right_index))
            groups[keep_index].connection_ids.extend(groups[remove_index].connection_ids)
            groups.pop(remove_index)

    updated_groups = tuple(
        CableGroupDefinition(
            group.cable_group_id,
            tuple(group.connection_ids),
            group.diameter_mm,
            group.material_overrides,
            group.metadata_overrides,
            group.name,
            group.conductor_diameter_mm,
        )
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
        cable_groups=updated_groups,
    )
    group_issues = tuple(
        issue for issue in validate_harness(updated) if issue.path.startswith("cable_groups[")
    )
    if group_issues:
        raise ValueError(group_issues[0].message)
    persist_definition(harness_id, original, updated, gateway)


def set_cable_group_properties(
    harness_id: UUID,
    cable_group_id: UUID,
    diameter_mm: float,
    insulation_material: Optional[str],
    conductor_material: Optional[str],
    shielding: Optional[str],
    dielectric_material: Optional[str],
    manufacturer: Optional[str],
    part_number: Optional[str],
    metadata_overrides: Metadata,
    gateway: HarnessEditGateway,
    *,
    conductor_diameter_mm: Optional[float] = None,
) -> None:
    """
    Replace one connected cable group's construction properties atomically.
    """
    if (
        isinstance(diameter_mm, bool)
        or not isinstance(diameter_mm, (int, float))
        or not math.isfinite(diameter_mm)
        or diameter_mm <= 0
    ):
        raise ValueError("Cable-group diameter must be a finite positive value.")
    if conductor_diameter_mm is not None and (
        isinstance(conductor_diameter_mm, bool)
        or not isinstance(conductor_diameter_mm, (int, float))
        or not math.isfinite(conductor_diameter_mm)
        or conductor_diameter_mm <= 0
        or conductor_diameter_mm > diameter_mm
    ):
        raise ValueError(
            "Conductor diameter must be positive and no larger than the cable diameter."
        )
    _update_cable_group(
        harness_id,
        cable_group_id,
        gateway,
        lambda group: replace(
            group,
            diameter_mm=diameter_mm,
            conductor_diameter_mm=conductor_diameter_mm,
            material_overrides=replace(
                group.material_overrides,
                insulation_material=insulation_material,
                conductor_material=conductor_material,
                shielding=shielding,
                dielectric_material=dielectric_material,
                manufacturer=manufacturer,
                part_number=part_number,
            ),
            metadata_overrides=metadata_overrides,
        ),
    )


def set_cable_group_material_overrides(
    harness_id: UUID,
    cable_group_id: UUID,
    overrides: CableMaterialOverrides,
    gateway: HarnessEditGateway,
) -> None:
    """
    Replace one connected cable group's field-level material overrides.
    """
    if not isinstance(overrides, CableMaterialOverrides):
        raise ValueError("Cable-group material overrides are invalid.")
    _update_cable_group(
        harness_id,
        cable_group_id,
        gateway,
        lambda group: replace(group, material_overrides=overrides),
    )


def _update_cable_group(
    harness_id: UUID,
    cable_group_id: UUID,
    gateway: HarnessEditGateway,
    update: Callable[[CableGroupDefinition], CableGroupDefinition],
) -> None:
    """
    Apply one validated replacement to an existing connected cable group.
    """
    original, definition = read_definition(harness_id, gateway)
    if not any(group.cable_group_id == cable_group_id for group in definition.cable_groups):
        raise ValueError("Selected cable group does not exist in this harness.")
    groups = tuple(
        update(group) if group.cable_group_id == cable_group_id else group
        for group in definition.cable_groups
    )
    updated = replace(definition, cable_groups=groups)
    diameter_issue = next(
        (
            issue
            for issue in validate_harness(updated)
            if issue.code == "connection_diameter_budget_exceeded"
        ),
        None,
    )
    if diameter_issue is not None:
        raise ValueError(diameter_issue.message)
    persist_definition(harness_id, original, updated, gateway)


def rename_cable_group(
    harness_id: UUID,
    cable_group_id: UUID,
    name: str,
    gateway: HarnessEditGateway,
) -> None:
    """
    Rename one connected cable group without changing its members or routing.

    Clearing the custom name restores the palette's generated cable-group label.
    """
    if not isinstance(name, str):
        raise ValueError("Cable-group name must be a string.")
    _update_cable_group(
        harness_id,
        cable_group_id,
        gateway,
        lambda group: replace(group, name=name.strip()),
    )


def cable_end_locations(
    definition: HarnessDefinition,
) -> dict[UUID, tuple[UUID, PathwayEndpoint]]:
    """
    Resolve every physical cable end to its authoritative pathway boundary.
    """
    return {end.connection_id: (end.pathway_id, end.endpoint) for end in definition.standalone_ends}


def _cable_group_member_index(
    groups: list[_MutableCableGroup],
    connection_id: UUID,
) -> Optional[int]:
    """
    Return the current group index containing one connection, if any.
    """
    return next(
        (index for index, group in enumerate(groups) if connection_id in group.connection_ids),
        None,
    )
