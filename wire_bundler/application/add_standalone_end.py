"""
Create disconnected end stacks anchored to pathway boundaries.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Protocol
from uuid import UUID, uuid4

from ..domain import (
    Connection,
    PathwayEndpoint,
    StandaloneEndDefinition,
    dumps,
    loads,
    next_available_name,
)


class StandaloneEndGateway(Protocol):
    """
    Describe persisted harness operations required by standalone-end creation.
    """

    def read_harness_definition(self, harness_id: UUID) -> str:
        """
        Return the serialized definition owned by one harness.
        """

    def replace_harness_definition(self, harness_id: UUID, serialized_definition: str) -> None:
        """
        Replace the serialized definition owned by one harness.
        """


class StandaloneEndUpdateError(RuntimeError):
    """
    Report a failed update whose original definition could not be restored.
    """


@dataclass(frozen=True)
class StandaloneEndResult:
    """
    Return the connection and pathway association created together.
    """

    connection: Connection
    standalone_end: StandaloneEndDefinition


def add_standalone_end(
    harness_id: UUID,
    guide_entity_tokens: tuple[str, ...],
    pathway_id: UUID,
    endpoint: PathwayEndpoint,
    gateway: StandaloneEndGateway,
    id_factory: Callable[[], UUID] = uuid4,
) -> StandaloneEndResult:
    """
    Persist one ordered guide stack without creating a conductor or route.

    Raises:
        ValueError: If guide geometry or the pathway boundary is invalid.
        StandaloneEndUpdateError: If persistence and rollback both fail.
    """
    normalized_tokens = tuple(token.strip() for token in guide_entity_tokens)
    if not normalized_tokens or any(not token for token in normalized_tokens):
        raise ValueError("Select at least one valid end guide profile.")
    if not isinstance(endpoint, PathwayEndpoint):
        raise ValueError("Select a valid pathway end.")

    original = gateway.read_harness_definition(harness_id)
    definition = loads(original)
    if all(pathway.pathway_id != pathway_id for pathway in definition.pathways):
        raise ValueError("Selected pathway no longer exists in this harness.")
    connection_id = id_factory()
    existing_ids = {definition.harness_id}
    identity_groups = (
        (connection.connection_id for connection in definition.connections),
        (control.control_id for control in definition.controls),
        (pathway.pathway_id for pathway in definition.pathways),
        (junction.junction_id for junction in definition.junctions),
        (group.wire_group_id for group in definition.wire_groups),
    )
    for identities in identity_groups:
        existing_ids.update(identities)
    if connection_id in existing_ids:
        raise ValueError("Generated standalone-end identity is already in use.")
    side = "A" if endpoint is PathwayEndpoint.START else "B"
    connection = Connection(
        connection_id=connection_id,
        name=next_available_name(f"End {side} 001", (item.name for item in definition.connections)),
        entity_token=normalized_tokens[0],
        additional_entity_tokens=normalized_tokens[1:],
        interpolation=definition.end_defaults,
    )
    standalone_end = StandaloneEndDefinition(connection_id, pathway_id, endpoint)
    updated = replace(
        definition,
        connections=(*definition.connections, connection),
        standalone_ends=(*definition.standalone_ends, standalone_end),
    )
    try:
        gateway.replace_harness_definition(harness_id, dumps(updated))
    except Exception as persistence_error:
        try:
            gateway.replace_harness_definition(harness_id, original)
        except Exception as rollback_error:
            raise StandaloneEndUpdateError(
                "Failed to persist the standalone end and restore the harness definition: "
                f"{rollback_error}"
            ) from persistence_error
        raise
    return StandaloneEndResult(connection, standalone_end)
