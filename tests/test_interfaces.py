"""
Regression tests for persistent reference-only Interfaces.
"""

from __future__ import annotations

import json
from dataclasses import replace
from uuid import UUID

import pytest

from cable_bundler.application import (
    add_interface,
    add_interface_contacts,
    name_interface_contacts,
    remove_interface,
    remove_interface_contacts,
    rename_interface,
    set_interface_contact_details,
)
from cable_bundler.domain import (
    AttachmentTargetKind,
    DefinitionParseError,
    HarnessDefinition,
    InterfaceContact,
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


def test_interface_contacts_round_trip_and_schema_29_migration(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep contact identity and order while older Interfaces gain no contacts.
    """
    target = InterfaceTarget(InterfaceTargetKind.BODY, "body")
    contacts = (
        InterfaceContact(UUID(int=805), AttachmentTargetKind.FACE, "face"),
        InterfaceContact(UUID(int=806), AttachmentTargetKind.SKETCH_POINT, "point"),
    )
    interface = InterfaceDefinition(UUID(int=807), "Socket", (target,), contacts)
    definition = replace(valid_harness, interfaces=(interface,))
    assert loads(dumps(definition)).interfaces == (interface,)
    payload = json.loads(dumps(definition))
    payload["schema_version"] = 29
    del payload["interfaces"][0]["contacts"]
    assert loads(json.dumps(payload)).interfaces[0].contacts == ()


def test_interface_contact_names_survive_round_trip_and_previous_schema(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Persist imported names while older contacts acquire empty names.
    """
    contact = InterfaceContact(UUID(int=811), AttachmentTargetKind.FACE, "face")
    interface = InterfaceDefinition(
        UUID(int=812),
        "Socket",
        (InterfaceTarget(InterfaceTargetKind.BODY, "body"),),
        (contact,),
    )
    definition = replace(valid_harness, interfaces=(interface,))
    gateway = recording_gateway(definition)
    updated = name_interface_contacts(
        definition.harness_id, interface.interface_id, {contact.contact_id: "J1.2"}, gateway
    )
    assert updated.contacts[0].name == "J1.2"
    assert loads(gateway.serialized_definition).interfaces[0].contacts[0].name == "J1.2"
    cleared = name_interface_contacts(
        definition.harness_id, interface.interface_id, {contact.contact_id: ""}, gateway
    )
    assert cleared.contacts[0].name == ""
    previous = json.loads(dumps(definition))
    previous["schema_version"] = 30
    del previous["interfaces"][0]["contacts"][0]["name"]
    assert loads(json.dumps(previous)).interfaces[0].contacts[0].name == ""


def test_interface_contact_value_and_pin_persist_with_legacy_default(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Save both editor fields atomically and default older contacts to an empty pin.
    """
    contact = InterfaceContact(UUID(int=813), AttachmentTargetKind.FACE, "face", "J1.2")
    interface = InterfaceDefinition(
        UUID(int=814),
        "Socket",
        (InterfaceTarget(InterfaceTargetKind.BODY, "body"),),
        (contact,),
    )
    definition = replace(valid_harness, interfaces=(interface,))
    gateway = recording_gateway(definition)

    updated = set_interface_contact_details(
        definition.harness_id, interface.interface_id, contact.contact_id, " VCC ", " P7 ", gateway
    )

    assert updated.contacts[0].name == "VCC"
    assert updated.contacts[0].pin == "P7"
    assert loads(gateway.serialized_definition).interfaces[0].contacts == updated.contacts
    renamed = name_interface_contacts(
        definition.harness_id, interface.interface_id, {contact.contact_id: "GND"}, gateway
    )
    assert renamed.contacts[0].pin == "P7"
    previous = json.loads(dumps(definition))
    previous["schema_version"] = 31
    del previous["interfaces"][0]["contacts"][0]["pin"]
    assert loads(json.dumps(previous)).interfaces[0].contacts[0].pin == ""
    previous["interfaces"][0]["contacts"][0]["pin"] = 7
    with pytest.raises(DefinitionParseError, match="contact pin"):
        loads(json.dumps(previous))
    with pytest.raises(ValueError, match="contact pin"):
        set_interface_contact_details(
            definition.harness_id,
            interface.interface_id,
            contact.contact_id,
            "VCC",
            "x" * 81,
            gateway,
        )


def test_add_interface_contacts_keeps_existing_order_and_skips_existing_tokens(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Append only new picks without changing the identity of earlier contacts.
    """
    existing = InterfaceContact(UUID(int=808), AttachmentTargetKind.FACE, "face")
    interface = InterfaceDefinition(
        UUID(int=809),
        "Socket",
        (InterfaceTarget(InterfaceTargetKind.BODY, "body"),),
        (existing,),
    )
    definition = replace(valid_harness, interfaces=(interface,))
    gateway = recording_gateway(definition)
    new = InterfaceContact(UUID(int=810), AttachmentTargetKind.CIRCULAR_EDGE, "edge")
    updated = add_interface_contacts(
        definition.harness_id,
        interface.interface_id,
        (existing, new),
        gateway,
    )
    assert updated.contacts == (existing, new)
    assert loads(gateway.serialized_definition).interfaces[0].contacts == (existing, new)
    duplicate = InterfaceContact(definition.harness_id, AttachmentTargetKind.FACE, "other")
    with pytest.raises(ValueError, match="identity is already in use"):
        add_interface_contacts(
            definition.harness_id,
            interface.interface_id,
            (duplicate,),
            gateway,
        )


def test_remove_interface_contacts_preserves_survivors_and_rejects_unknown_ids(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Delete selected identities atomically without changing other contacts or routes.
    """
    contacts = tuple(
        InterfaceContact(UUID(int=820 + index), AttachmentTargetKind.FACE, f"face-{index}")
        for index in range(3)
    )
    interface = InterfaceDefinition(
        UUID(int=830),
        "Socket",
        (InterfaceTarget(InterfaceTargetKind.BODY, "body"),),
        contacts,
    )
    definition = replace(valid_harness, interfaces=(interface,))
    gateway = recording_gateway(definition)
    with pytest.raises(ValueError, match="known selected identities"):
        remove_interface_contacts(
            definition.harness_id, interface.interface_id, (UUID(int=999),), gateway
        )
    assert gateway.serialized_definition == dumps(definition)
    updated = remove_interface_contacts(
        definition.harness_id,
        interface.interface_id,
        (contacts[0].contact_id, contacts[2].contact_id),
        gateway,
    )
    assert updated.contacts == (contacts[1],)
    persisted = loads(gateway.serialized_definition)
    assert persisted.interfaces[0].contacts == (contacts[1],)
    assert persisted.pathways == definition.pathways


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
