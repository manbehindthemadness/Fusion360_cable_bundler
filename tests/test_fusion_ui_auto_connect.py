"""
Focused native-picker coverage for Interface Auto Connect.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.domain import (
    AttachmentTargetKind,
    CableEndAttachment,
    HarnessDefinition,
    InterfaceContact,
    loads,
)
from tests.test_batch_connect_interface_contacts import _contact_harness
from tests.test_edit_harness import _recording_gateway


def test_auto_connect_picker_only_accepts_grouped_end_profiles(
    addin_module: object,
    valid_harness: HarnessDefinition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reject unrelated geometry while retaining each cable end's first guide.
    """
    del addin_module
    commands = importlib.import_module("cable_bundler.fusion.ui.commands.interface_auto_connect")
    fusion = sys.modules["adsk.fusion"]
    monkeypatch.setitem(
        vars(fusion),
        "Profile",
        SimpleNamespace(cast=lambda value: value if getattr(value, "is_profile", False) else None),
    )
    first = SimpleNamespace(is_profile=True, nativeObject=None, entityToken="first")
    second = SimpleNamespace(is_profile=True, nativeObject=None, entityToken="second")
    unrelated = SimpleNamespace(is_profile=True, nativeObject=None, entityToken="unrelated")
    entities = {
        "fusion-start-token": (first,),
        "fusion-end-token": (second,),
    }
    design = SimpleNamespace(findEntityByToken=lambda token: entities.get(token, ()))
    candidates = commands._grouped_end_profiles(valid_harness, design)
    assert tuple(item[0] for item in candidates) == tuple(
        item.connection_id for item in valid_harness.connections
    )
    assert commands._picked_ending(first, candidates) == (
        valid_harness.connections[0].connection_id,
        None,
    )
    with pytest.raises(ValueError, match="existing cable group"):
        commands._picked_ending(unrelated, candidates)
    only_first_grouped = SimpleNamespace(
        cable_groups=(
            replace(
                valid_harness.cable_groups[0],
                connection_ids=(valid_harness.connections[0].connection_id,),
            ),
        ),
        connections=valid_harness.connections,
    )
    assert tuple(
        item[0] for item in commands._grouped_end_profiles(only_first_grouped, design)
    ) == (valid_harness.connections[0].connection_id,)
    parent_id = UUID(int=910)
    parent_profile = SimpleNamespace(
        is_profile=True, nativeObject=None, entityToken="parent-profile"
    )
    entities["parent-profile"] = (parent_profile,)
    connected = replace(
        valid_harness.connections[0],
        attachment=CableEndAttachment(
            AttachmentTargetKind.PROFILE,
            "parent-profile",
            "Connector",
            attachment_id=parent_id,
        ),
    )
    with_parent = replace(valid_harness, connections=(connected, valid_harness.connections[1]))
    candidates = commands._grouped_end_profiles(with_parent, design)
    assert commands._picked_ending(parent_profile, candidates) == (
        connected.connection_id,
        parent_id,
    )


def test_auto_connect_native_execute_saves_and_refreshes_one_batch(
    addin_module: object,
    valid_harness: HarnessDefinition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Carry picker and contact identities through the normal Fusion transaction.
    """
    del addin_module
    commands = importlib.import_module("cable_bundler.fusion.ui.commands.interface_auto_connect")
    definition = _contact_harness(valid_harness)
    gateway = _recording_gateway(definition)
    gateway.harness_component = lambda _identity: object()
    document = object()
    profile = SimpleNamespace(is_profile=True, nativeObject=None)
    contact = SimpleNamespace(is_profile=False)
    entities = {
        "contact-a": (contact,),
    }
    design = SimpleNamespace(findEntityByToken=lambda token: entities.get(token, ()))
    application = SimpleNamespace(
        activeDocument=document, activeViewport=SimpleNamespace(refresh=Mock())
    )
    core = sys.modules["adsk.core"]
    fusion = sys.modules["adsk.fusion"]
    monkeypatch.setitem(vars(core), "Application", SimpleNamespace(get=lambda: application))
    monkeypatch.setitem(
        vars(core), "SelectionCommandInput", SimpleNamespace(cast=lambda value: value)
    )
    monkeypatch.setitem(
        vars(fusion),
        "Profile",
        SimpleNamespace(cast=lambda value: value if getattr(value, "is_profile", False) else None),
    )
    monkeypatch.setitem(vars(commands), "_require_active_design", lambda _app: design)
    monkeypatch.setitem(vars(commands), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(
        vars(commands), "attachment_target_kind", lambda _entity: AttachmentTargetKind.SKETCH_POINT
    )
    monkeypatch.setitem(vars(commands), "attachment_target_name", lambda *_args: "Pad A")
    refresh = Mock(return_value=1)
    send = Mock()
    monkeypatch.setitem(vars(commands), "refresh_generated_cable_groups_for_connection", refresh)
    monkeypatch.setitem(vars(commands), "_refresh_active_preview", lambda *_args: "")
    monkeypatch.setitem(vars(commands), "_send_palette_state", send)
    picker = SimpleNamespace(
        selectionCount=1, selection=lambda _index: SimpleNamespace(entity=profile)
    )
    inputs = SimpleNamespace(itemById=lambda _identity: picker)
    args = SimpleNamespace(
        command=SimpleNamespace(commandInputs=inputs), executeFailed=False, executeFailedMessage=""
    )
    request = commands._AutoConnectRequest(
        definition.harness_id,
        definition.interfaces[0].interface_id,
        (UUID(int=801),),
        True,
        True,
        None,
        document,
    )
    commands._ExecuteHandler(
        request, ((definition.connections[0].connection_id, None, profile),)
    ).notify(args)
    assert not args.executeFailed
    stored = loads(gateway.serialized_definition)
    assert stored.connections[0].attachments[0].entity_token == "contact-a"
    assert stored.connections[0].attachments[0].name == "VCC"
    refresh.assert_called_once()
    send.assert_called_once()


def test_auto_connect_native_execute_pairs_two_picked_endings(
    addin_module: object,
    valid_harness: HarnessDefinition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Resolve both Fusion selections and save one association with the two batches.
    """
    del addin_module
    commands = importlib.import_module("cable_bundler.fusion.ui.commands.interface_auto_connect")
    source = _contact_harness(valid_harness)
    target_interface = replace(
        source.interfaces[0],
        interface_id=UUID(int=810),
        name="Target",
        contacts=(
            InterfaceContact(
                UUID(int=811), AttachmentTargetKind.SKETCH_POINT, "target-a", "", "A1"
            ),
        ),
    )
    definition = replace(source, interfaces=(*source.interfaces, target_interface))
    gateway = _recording_gateway(definition)
    gateway.harness_component = lambda _identity: object()
    document = object()
    first_profile = SimpleNamespace(is_profile=True, nativeObject=None, token="first")
    second_profile = SimpleNamespace(is_profile=True, nativeObject=None, token="second")
    contact = SimpleNamespace(is_profile=False)
    design = SimpleNamespace(
        findEntityByToken=lambda token: (contact,) if token in {"contact-a", "target-a"} else ()
    )
    application = SimpleNamespace(
        activeDocument=document, activeViewport=SimpleNamespace(refresh=Mock())
    )
    core = sys.modules["adsk.core"]
    fusion = sys.modules["adsk.fusion"]
    monkeypatch.setitem(vars(core), "Application", SimpleNamespace(get=lambda: application))
    monkeypatch.setitem(
        vars(core), "SelectionCommandInput", SimpleNamespace(cast=lambda value: value)
    )
    monkeypatch.setitem(
        vars(fusion),
        "Profile",
        SimpleNamespace(cast=lambda value: value if getattr(value, "is_profile", False) else None),
    )
    monkeypatch.setitem(vars(commands), "_require_active_design", lambda _app: design)
    monkeypatch.setitem(vars(commands), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(
        vars(commands), "attachment_target_kind", lambda _entity: AttachmentTargetKind.SKETCH_POINT
    )
    monkeypatch.setitem(vars(commands), "attachment_target_name", lambda *_args: "Pad")
    refresh = Mock()
    monkeypatch.setitem(vars(commands), "refresh_generated_cable_groups_for_connection", refresh)
    monkeypatch.setitem(vars(commands), "_refresh_active_preview", lambda *_args: "")
    monkeypatch.setitem(vars(commands), "_send_palette_state", Mock())
    pickers = {
        commands.AUTO_CONNECT_END_INPUT_ID: SimpleNamespace(
            selectionCount=1, selection=lambda _index: SimpleNamespace(entity=first_profile)
        ),
        commands.AUTO_CONNECT_TARGET_END_INPUT_ID: SimpleNamespace(
            selectionCount=1, selection=lambda _index: SimpleNamespace(entity=second_profile)
        ),
    }
    args = SimpleNamespace(
        command=SimpleNamespace(
            commandInputs=SimpleNamespace(itemById=lambda identity: pickers.get(identity))
        ),
        executeFailed=False,
        executeFailedMessage="",
    )
    request = commands._AutoConnectRequest(
        definition.harness_id,
        source.interfaces[0].interface_id,
        (UUID(int=801),),
        True,
        True,
        None,
        document,
        target_interface.interface_id,
        (UUID(int=811),),
        False,
        False,
        None,
    )
    candidates = (
        (definition.connections[0].connection_id, None, first_profile),
        (definition.connections[1].connection_id, None, second_profile),
    )
    commands._ExecuteHandler(request, candidates).notify(args)
    assert not args.executeFailed
    stored = loads(gateway.serialized_definition)
    assert len(stored.attachment_associations) == 1
    assert stored.attachment_associations[0].attachment_ids == (
        stored.connections[0].attachments[0].attachment_id,
        stored.connections[1].attachments[0].attachment_id,
    )
    assert refresh.call_count == 2
