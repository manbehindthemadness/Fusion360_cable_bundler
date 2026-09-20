"""Junction creation, relationship, naming, and deletion edits."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from uuid import UUID, uuid4

from ...domain import (
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    JunctionDefinition,
    JunctionPathwayRelationship,
    PathwayEndpoint,
    next_available_name,
    validate_harness,
)
from .support import (
    persist_definition,
    read_definition,
    require_junction,
)
from .types import HarnessEditGateway


def suggest_junction_name(
    harness_id: UUID,
    requested_name: str,
    gateway: HarnessEditGateway,
) -> str:
    """
    Return a normalized conflict-free junction name for one harness.
    """
    if not isinstance(requested_name, str):
        raise ValueError("Junction name must be a string.")
    normalized_name = requested_name.strip()
    if not normalized_name:
        raise ValueError("Junction name must not be empty.")
    _, definition = read_definition(harness_id, gateway)
    return next_available_name(
        normalized_name,
        (candidate.name for candidate in definition.junctions),
    )


# noinspection DuplicatedCode
def add_junction(
    harness_id: UUID,
    name: str,
    entity_token: str,
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
) -> JunctionDefinition:
    """
    Persist one named unconnected routing-gate junction from unused Fusion geometry.
    """
    if not isinstance(name, str):
        raise ValueError("Junction name must be a string.")
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Junction name must not be empty.")
    normalized_token = entity_token.strip()
    if not normalized_token:
        raise ValueError("A junction must reference Fusion geometry.")
    original, definition = read_definition(harness_id, gateway)
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
        *(group.cable_group_id for group in definition.cable_groups),
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
            normalized_name, (candidate.name for candidate in definition.junctions)
        ),
        control_id=control.control_id,
    )
    updated = replace(
        definition,
        controls=(*definition.controls, control),
        junctions=(*definition.junctions, junction),
    )
    persist_definition(harness_id, original, updated, gateway)
    return junction


def update_junction_relationships(
    harness_id: UUID,
    junction_id: UUID,
    pathway_relationships: tuple[JunctionPathwayRelationship, ...],
    gateway: HarnessEditGateway,
) -> JunctionDefinition:
    """
    Replace one junction's endpoint relationships and preserve cable control order.
    """
    if any(
        not isinstance(relationship, JunctionPathwayRelationship)
        for relationship in pathway_relationships
    ):
        raise ValueError("Every junction relationship must identify a pathway endpoint.")
    original, definition = read_definition(harness_id, gateway)
    updated_junction, updated = _replace_junction_relationships(
        definition,
        junction_id,
        pathway_relationships,
    )
    persist_definition(harness_id, original, updated, gateway)
    return updated_junction


# noinspection DuplicatedCode
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
    original, definition = read_definition(harness_id, gateway)
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
    persist_definition(harness_id, original, updated, gateway)
    return updated_junction


# noinspection DuplicatedCode
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
    original, definition = read_definition(harness_id, gateway)
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
    persist_definition(harness_id, original, updated, gateway)
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
    original, definition = read_definition(harness_id, gateway)
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
    persist_definition(
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
    generation readiness, so a cable-free draft remains editable.
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


def remove_junction(
    harness_id: UUID,
    junction_id: UUID,
    gateway: HarnessEditGateway,
) -> None:
    """
    Remove one junction and its dedicated control without changing neighboring topology.
    """
    original, definition = read_definition(harness_id, gateway)
    junction = require_junction(definition, junction_id)
    updated = replace(
        definition,
        controls=tuple(
            control for control in definition.controls if control.control_id != junction.control_id
        ),
        junctions=tuple(
            candidate for candidate in definition.junctions if candidate.junction_id != junction_id
        ),
    )
    persist_definition(harness_id, original, updated, gateway)
