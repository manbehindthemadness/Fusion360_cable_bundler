"""
Validate saved-Interface selection for projected contact imports.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.application.interface_projection_copy import OrientedContact
from cable_bundler.domain import InterfaceDefinition, InterfaceTarget, InterfaceTargetKind


def test_source_picker_accepts_only_another_saved_interface_target(
    addin_module: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Reject random geometry, self-picks, and shared ambiguous targets.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_projection_copy")
    destination = InterfaceDefinition(
        UUID(int=1), "Destination", (InterfaceTarget(InterfaceTargetKind.BODY, "current"),)
    )
    source = InterfaceDefinition(
        UUID(int=2), "Source", (InterfaceTarget(InterfaceTargetKind.BODY, "saved"),)
    )
    resolved = {
        "current": SimpleNamespace(entityToken="current"),
        "saved": SimpleNamespace(entityToken="saved"),
    }
    monkeypatch.setitem(
        vars(module),
        "resolve_interface_target",
        lambda _design, target: resolved.get(target.entity_token),
    )

    assert (
        module.picked_source_interface(
            object(), (destination, source), destination.interface_id, resolved["saved"]
        )
        == source
    )
    for token in ("current", "random", ""):
        with pytest.raises(ValueError, match="Interface"):
            module.picked_source_interface(
                object(),
                (destination, source),
                destination.interface_id,
                SimpleNamespace(entityToken=token),
            )
    shared = InterfaceDefinition(
        UUID(int=3), "Shared", (InterfaceTarget(InterfaceTargetKind.BODY, "saved"),)
    )
    with pytest.raises(ValueError, match="exactly one"):
        module.picked_source_interface(
            object(),
            (destination, source, shared),
            destination.interface_id,
            resolved["saved"],
        )


def test_selected_contact_uses_full_orientation_frame(
    addin_module: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Filtering one destination still finds its source by physical position.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_projection_copy")
    target_contacts = tuple(
        SimpleNamespace(contact_id=UUID(int=10 + index), name="", pin="") for index in range(2)
    )
    source_contacts = tuple(
        SimpleNamespace(contact_id=UUID(int=20 + index), name=f"V{index}", pin=f"P{index}")
        for index in range(2)
    )
    destination = SimpleNamespace(interface_id=UUID(int=1), contacts=target_contacts)
    source = SimpleNamespace(interface_id=UUID(int=2), contacts=source_contacts, name="Board")
    definition = SimpleNamespace(interfaces=(destination, source))
    gateway = SimpleNamespace(read_harness_definition=Mock(return_value="saved"))
    monkeypatch.setitem(vars(module), "_require_active_design", lambda _application: object())
    monkeypatch.setitem(vars(module), "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setitem(vars(module), "loads", lambda _serialized: definition)
    monkeypatch.setitem(
        vars(module),
        "_oriented_contacts",
        lambda _design, contacts: tuple(
            OrientedContact(
                contact.contact_id,
                (0, index * 2.5, 10 if contact.contact_id.int < 20 else 0),
                (0, 0, 1),
            )
            for index, contact in enumerate(contacts)
        ),
    )
    fill = Mock(return_value=(1, 1))
    monkeypatch.setitem(vars(module), "fill_interface_contact_details", fill)

    notice, conflicts = module.copy_projected_interface_details(
        object(),
        UUID(int=3),
        destination.interface_id,
        source.interface_id,
        (target_contacts[1].contact_id,),
        True,
    )

    assert "Copied 1 Values and 1 Pins" in notice
    assert conflicts == ()
    fill.assert_called_once_with(
        UUID(int=3),
        destination.interface_id,
        {target_contacts[1].contact_id: ("V1", "P1")},
        True,
        gateway,
    )
    fill.reset_mock()
    module.copy_projected_interface_details(
        object(),
        UUID(int=3),
        destination.interface_id,
        source.interface_id,
        (target_contacts[1].contact_id,),
        True,
        copy_values=False,
    )
    fill.assert_called_once_with(
        UUID(int=3),
        destination.interface_id,
        {target_contacts[1].contact_id: ("", "P1")},
        True,
        gateway,
    )
    with pytest.raises(ValueError, match="Values, Pins, or both"):
        module.copy_projected_interface_details(
            object(),
            UUID(int=3),
            destination.interface_id,
            source.interface_id,
            (),
            False,
            copy_values=False,
        )


def test_dense_projection_requires_a_reviewed_saved_source(
    addin_module: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Surface both metadata choices and reject a choice outside live geometry.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_projection_copy")
    destination_contact = SimpleNamespace(contact_id=UUID(int=10), name="", pin="")
    source_contacts = tuple(
        SimpleNamespace(contact_id=UUID(int=20 + index), name=f"V{index}", pin=f"P{index}")
        for index in range(2)
    )
    destination = SimpleNamespace(interface_id=UUID(int=1), contacts=(destination_contact,))
    source = SimpleNamespace(interface_id=UUID(int=2), contacts=source_contacts, name="Board")
    definition = SimpleNamespace(interfaces=(destination, source))
    gateway = SimpleNamespace(read_harness_definition=Mock(return_value="saved"))
    monkeypatch.setitem(vars(module), "_require_active_design", lambda _application: object())
    monkeypatch.setitem(vars(module), "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setitem(vars(module), "loads", lambda _serialized: definition)
    monkeypatch.setitem(
        vars(module),
        "_oriented_contacts",
        lambda _design, contacts: tuple(
            OrientedContact(
                contact.contact_id,
                (0.25 if contact.contact_id.int == 10 else index * 0.5, 0, 10),
                (0, 0, 1),
            )
            for index, contact in enumerate(contacts)
        ),
    )
    fill = Mock(return_value=(0, 0))
    monkeypatch.setitem(vars(module), "fill_interface_contact_details", fill)
    arguments = (object(), UUID(int=3), destination.interface_id, source.interface_id, (), True)

    _notice, conflicts = module.copy_projected_interface_details(*arguments)
    assert len(conflicts) == 1
    assert [item["value"] for item in conflicts[0]["suggestions"]] == ["V0", "V1"]
    fill.assert_called_once_with(UUID(int=3), destination.interface_id, {}, True, gateway)
    with pytest.raises(ValueError, match="no longer matches"):
        module.copy_projected_interface_details(
            *arguments, {destination_contact.contact_id: UUID(int=999)}
        )
    fill.reset_mock()
    _notice, remaining = module.copy_projected_interface_details(
        *arguments, {destination_contact.contact_id: source_contacts[1].contact_id}
    )
    assert remaining == ()
    fill.assert_called_once_with(
        UUID(int=3),
        destination.interface_id,
        {destination_contact.contact_id: ("V1", "P1")},
        True,
        gateway,
    )
