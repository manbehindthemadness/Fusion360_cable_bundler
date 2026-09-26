"""
Verify live geometry-name import for Interface contact Values.
"""

from __future__ import annotations

import importlib
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

import pytest

from cable_bundler.domain import (
    AttachmentTargetKind,
    HarnessDefinition,
    InterfaceContact,
    InterfaceDefinition,
    InterfaceTarget,
    InterfaceTargetKind,
    loads,
)
from tests.harness_edit_support import recording_gateway


def test_geo_import_fills_only_empty_values_from_explicit_names(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Import selected live names, then all remaining names, without touching Pins.
    """
    importer = importlib.import_module("cable_bundler.fusion.interface_contact_geo_import")
    contacts = (
        InterfaceContact(UUID(int=900), AttachmentTargetKind.FACE, "body-a", pin="P7"),
        InterfaceContact(UUID(int=901), AttachmentTargetKind.FACE, "body-b", name="Keep", pin="P8"),
        InterfaceContact(UUID(int=902), AttachmentTargetKind.FACE, "unnamed"),
        InterfaceContact(UUID(int=903), AttachmentTargetKind.FACE, "ambiguous"),
        InterfaceContact(UUID(int=904), AttachmentTargetKind.PROFILE, "sketch-e"),
    )
    interface = InterfaceDefinition(
        UUID(int=905), "Socket", (InterfaceTarget(InterfaceTargetKind.BODY, "shell"),), contacts
    )
    gateway = recording_gateway(replace(valid_harness, interfaces=(interface,)))
    design = object()
    monkeypatch.setitem(vars(importer), "_require_active_design", lambda _app: design)
    monkeypatch.setitem(vars(importer), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(vars(importer), "attachment_target_kind", lambda entity: entity.kind)

    def face(name: str) -> SimpleNamespace:
        """
        Expose one body name through a face selection.
        """
        return SimpleNamespace(kind=AttachmentTargetKind.FACE, body=SimpleNamespace(name=name))

    geometry = {
        "body-a": (face("Pin Body A"),),
        "body-b": (face("Would Replace"),),
        "unnamed": (face(""),),
        "ambiguous": (face("First"), face("Second")),
        "sketch-e": (
            SimpleNamespace(
                kind=AttachmentTargetKind.PROFILE,
                parentSketch=SimpleNamespace(name="Profile E"),
            ),
        ),
    }
    monkeypatch.setitem(
        vars(importer), "resolve_contact_entities", lambda _design, token: geometry[token]
    )

    selected_notice = importer.import_interface_contact_geometry_names(
        object(), valid_harness.harness_id, interface.interface_id, (contacts[0].contact_id,)
    )
    assert selected_notice == "Imported geometry Values for 1 of 1 Interface contacts."
    selected = loads(gateway.serialized_definition).interfaces[0]
    assert [contact.name for contact in selected.contacts] == ["Pin Body A", "Keep", "", "", ""]
    assert selected.contacts[0].pin == "P7"

    all_notice = importer.import_interface_contact_geometry_names(
        object(), valid_harness.harness_id, interface.interface_id, ()
    )
    assert all_notice == "Imported geometry Values for 1 of 5 Interface contacts."
    updated = loads(gateway.serialized_definition).interfaces[0]
    assert [contact.name for contact in updated.contacts] == [
        "Pin Body A",
        "Keep",
        "",
        "",
        "Profile E",
    ]
    assert [contact.pin for contact in updated.contacts] == ["P7", "P8", "", "", ""]

    with pytest.raises(ValueError, match="invalid contact identity"):
        importer.import_interface_contact_geometry_names(
            object(), valid_harness.harness_id, interface.interface_id, (UUID(int=999),)
        )
