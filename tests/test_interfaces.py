"""
Regression tests for persistent reference-only Interfaces.
"""

from __future__ import annotations

import json
from dataclasses import replace
from uuid import UUID

import pytest

from cable_bundler.application import add_interface, remove_interface, rename_interface
from cable_bundler.domain import (
    DefinitionParseError,
    HarnessDefinition,
    InterfaceDefinition,
    InterfaceTarget,
    InterfaceTargetKind,
    dumps,
    loads,
    validate_harness,
)
from tests.harness_edit_support import recording_gateway


def test_interface_round_trip_and_previous_schema_migration(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve mixed target order and migrate schema 28 to an empty collection.
    """
    interface = InterfaceDefinition(
        UUID(int=800),
        "Connector Shell",
        (
            InterfaceTarget(InterfaceTargetKind.BODY, "body"),
            InterfaceTarget(InterfaceTargetKind.SKETCH, "sketch"),
        ),
    )
    definition = replace(valid_harness, interfaces=(interface,))

    assert loads(dumps(definition)).interfaces == (interface,)
    payload = json.loads(dumps(valid_harness))
    payload["schema_version"] = 28
    del payload["interfaces"]
    assert loads(json.dumps(payload)).interfaces == ()


def test_interface_edit_sequence_preserves_routing(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Create, rename, and delete an Interface without editing route structures.
    """
    gateway = recording_gateway(valid_harness)
    target = InterfaceTarget(InterfaceTargetKind.OCCURRENCE, "connector:1")

    created = add_interface(
        valid_harness.harness_id, "Connector:1", (target,), gateway, lambda: UUID(int=801)
    )
    assert loads(gateway.serialized_definition).interfaces == (created,)
    renamed = rename_interface(valid_harness.harness_id, created.interface_id, "Socket A", gateway)
    assert renamed.name == "Socket A"
    assert loads(gateway.serialized_definition).pathways == valid_harness.pathways
    remove_interface(valid_harness.harness_id, created.interface_id, gateway)
    assert loads(gateway.serialized_definition).interfaces == ()


def test_interface_rejects_mixed_occurrence_and_repeated_targets() -> None:
    """
    Keep a component occurrence separate and reject repeated target tokens.
    """
    occurrence = InterfaceTarget(InterfaceTargetKind.OCCURRENCE, "occurrence")
    body = InterfaceTarget(InterfaceTargetKind.BODY, "body")
    with pytest.raises(ValueError, match="only Interface target"):
        InterfaceDefinition(UUID(int=802), "Mixed", (occurrence, body))
    with pytest.raises(ValueError, match="must not repeat"):
        InterfaceDefinition(UUID(int=803), "Repeated", (body, body))


def test_interface_names_and_identity_are_validated(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Reject duplicate names and IDs while accepting independent target references.
    """
    target = InterfaceTarget(InterfaceTargetKind.BODY, "body")
    interfaces = (
        InterfaceDefinition(UUID(int=804), "Socket", (target,)),
        InterfaceDefinition(UUID(int=804), "socket", (target,)),
    )
    issues = validate_harness(replace(valid_harness, interfaces=interfaces))
    assert {issue.code for issue in issues} >= {"duplicate_id", "invalid_interface_name"}


def test_interface_codec_rejects_invalid_target_kind(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Reject malformed persisted targets at the JSON boundary.
    """
    payload = json.loads(dumps(valid_harness))
    payload["interfaces"] = [
        {
            "interface_id": str(UUID(int=805)),
            "name": "Socket",
            "targets": [{"kind": "face", "entity_token": "face-token"}],
        }
    ]
    with pytest.raises(DefinitionParseError, match="kind"):
        loads(json.dumps(payload))
