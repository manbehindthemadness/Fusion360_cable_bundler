"""
Focused native-picker coverage for Interface Auto Connect.
"""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.domain import (
    AttachmentTargetKind,
    CableEndAttachment,
    CableEndShape,
    CableGroupType,
    HarnessDefinition,
    InterfaceContact,
    loads,
)
from tests.test_batch_connect_interface_contacts import _contact_harness
from tests.test_edit_harness import _recording_gateway


def test_auto_connect_launchers_keep_picker_and_apply_requests_distinct(
    addin_module: object,
    valid_harness: HarnessDefinition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Stage a read-only picker first and a reviewed apply only after explicit submission.
    """
    del addin_module
    launchers = importlib.import_module("cable_bundler.fusion.ui.launchers")
    slot = SimpleNamespace(prepare=Mock(), clear=Mock())
    monkeypatch.setattr(launchers._runtime, "pending_auto_connect", slot)
    definition = SimpleNamespace(execute=Mock(return_value=True))
    document = object()
    application = SimpleNamespace(
        activeDocument=document,
        userInterface=SimpleNamespace(
            commandDefinitions=SimpleNamespace(itemById=lambda _identity: definition)
        ),
    )
    launchers._open_auto_connect_picker(
        application,
        json.dumps(
            {
                "harnessId": str(valid_harness.harness_id),
                "side": "source",
                "requestId": "pick-1",
            }
        ),
    )
    pick = slot.prepare.call_args.args[0]
    assert isinstance(pick, launchers.AutoConnectPickRequest)
    assert pick.document is document
    assert pick.request_id == "pick-1"
    launchers._open_auto_connect_command(
        application,
        json.dumps(
            {
                "harnessId": str(valid_harness.harness_id),
                "interfaceId": str(UUID(int=800)),
                "contactIds": [str(UUID(int=801))],
                "connectionId": str(valid_harness.connections[0].connection_id),
                "includePins": True,
                "includeValues": False,
                "diameterMm": None,
            }
        ),
    )
    apply = slot.prepare.call_args.args[0]
    assert isinstance(apply, launchers.AutoConnectApplyRequest)
    assert apply.connection_id == valid_harness.connections[0].connection_id
    assert apply.include_values is False
    assert definition.execute.call_count == 2


def test_auto_connect_picker_returns_ending_without_saving(
    addin_module: object,
    valid_harness: HarnessDefinition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Return the selected ending to the palette only when the picker finishes.
    """
    del addin_module
    commands = importlib.import_module("cable_bundler.fusion.ui.commands.interface_auto_connect")
    gateway = _recording_gateway(valid_harness)
    original = gateway.serialized_definition
    profile = SimpleNamespace(is_profile=True, nativeObject=None)
    document = object()
    send = Mock()
    application = SimpleNamespace(
        activeDocument=document,
        userInterface=SimpleNamespace(
            palettes=SimpleNamespace(
                itemById=lambda _identity: SimpleNamespace(sendInfoToHTML=send)
            )
        ),
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
    monkeypatch.setitem(vars(commands), "_create_harness_gateway", lambda _app: gateway)
    picker = SimpleNamespace(
        selectionCount=1, selection=lambda _index: SimpleNamespace(entity=profile)
    )
    args = SimpleNamespace(
        command=SimpleNamespace(commandInputs=SimpleNamespace(itemById=lambda _identity: picker)),
        executeFailed=False,
        executeFailedMessage="",
    )
    request = commands.AutoConnectPickRequest(
        valid_harness.harness_id, "source", "pick-1", document
    )
    execute = commands._PickExecuteHandler(
        request, ((valid_harness.connections[0].connection_id, None, profile),)
    )
    execute.notify(args)
    assert not args.executeFailed
    assert gateway.serialized_definition == original
    send.assert_not_called()
    commands._PickDestroyedHandler(execute).notify(args)
    action, serialized = send.call_args.args
    assert action == "auto_connect_ending_selected"
    assert json.loads(serialized) == {
        "harnessId": str(valid_harness.harness_id),
        "side": "source",
        "requestId": "pick-1",
        "cancelled": False,
        "connectionId": str(valid_harness.connections[0].connection_id),
        "parentAttachmentId": None,
        "name": valid_harness.connections[0].name,
    }


def test_auto_connect_picker_only_accepts_grouped_closed_end_profiles(
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
    candidates = commands._grouped_end_guides(valid_harness, design)
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
    assert tuple(item[0] for item in commands._grouped_end_guides(only_first_grouped, design)) == (
        valid_harness.connections[0].connection_id,
    )
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
    candidates = commands._grouped_end_guides(with_parent, design)
    assert commands._picked_ending(parent_profile, candidates) == (
        connected.connection_id,
        parent_id,
    )


def test_auto_connect_picker_accepts_only_grouped_open_ribbon_guides(
    addin_module: object,
    valid_harness: HarnessDefinition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    An open sketch curve identifies a ribbon end without becoming a contact target.
    """
    del addin_module
    commands = importlib.import_module("cable_bundler.fusion.ui.commands.interface_auto_connect")
    fusion = sys.modules["adsk.fusion"]
    monkeypatch.setitem(
        vars(fusion),
        "Profile",
        SimpleNamespace(cast=lambda value: value if getattr(value, "is_profile", False) else None),
    )
    monkeypatch.setitem(
        vars(fusion),
        "SketchCurve",
        SimpleNamespace(cast=lambda value: value if getattr(value, "is_curve", False) else None),
    )

    def curve(token: str, distance: float) -> SimpleNamespace:
        """
        Model the Fusion endpoint test used for valid open end guides.
        """
        return SimpleNamespace(
            entityToken=token,
            is_curve=True,
            nativeObject=None,
            geometry=SimpleNamespace(
                evaluator=SimpleNamespace(
                    getEndPoints=lambda: (
                        True,
                        SimpleNamespace(distanceTo=lambda _end: distance),
                        object(),
                    )
                )
            ),
        )

    first = curve("ribbon-a", 1.0)
    first_secondary = curve("ribbon-a-secondary", 1.0)
    second = curve("ribbon-b", 1.0)
    closed = curve("closed", 0.0)
    unrelated = curve("other", 1.0)
    entities = {
        "fusion-start-token": (first,),
        "ribbon-a-secondary": (first_secondary,),
        "fusion-end-token": (second,),
    }
    design = SimpleNamespace(findEntityByToken=lambda token: entities.get(token, ()))
    definition = replace(
        valid_harness,
        connections=(
            replace(
                valid_harness.connections[0],
                additional_entity_tokens=("ribbon-a-secondary",),
            ),
            valid_harness.connections[1],
        ),
        cable_groups=(replace(valid_harness.cable_groups[0], group_type=CableGroupType.RIBBON),),
        standalone_ends=tuple(
            replace(end, shape=CableEndShape.OPEN) for end in valid_harness.standalone_ends
        ),
    )

    candidates = commands._grouped_end_guides(definition, design)

    assert commands._picked_ending(first, candidates) == (
        valid_harness.connections[0].connection_id,
        None,
    )
    assert commands._picked_ending(second, candidates) == (
        valid_harness.connections[1].connection_id,
        None,
    )
    for rejected in (first_secondary, closed, unrelated):
        with pytest.raises(ValueError, match="existing cable group"):
            commands._picked_ending(rejected, candidates)


def test_auto_connect_native_picker_enables_open_curve_selection(
    addin_module: object,
    valid_harness: HarnessDefinition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Fusion offers the same open-curve filter used by standalone end guides.
    """
    del addin_module
    commands = importlib.import_module("cable_bundler.fusion.ui.commands.interface_auto_connect")
    core = sys.modules["adsk.core"]
    fusion = sys.modules["adsk.fusion"]
    profile = SimpleNamespace(is_profile=True, nativeObject=None)
    monkeypatch.setitem(
        vars(fusion),
        "Profile",
        SimpleNamespace(cast=lambda value: value if getattr(value, "is_profile", False) else None),
    )
    document = object()
    application = SimpleNamespace(activeDocument=document)
    monkeypatch.setitem(vars(core), "Application", SimpleNamespace(get=lambda: application))
    design = SimpleNamespace(findEntityByToken=lambda _token: (profile,))
    monkeypatch.setitem(vars(commands), "_require_active_design", lambda _app: design)
    monkeypatch.setitem(
        vars(commands),
        "_create_harness_gateway",
        lambda _app: SimpleNamespace(read_harness_definition=lambda _id: "definition"),
    )
    monkeypatch.setitem(vars(commands), "loads", lambda _serialized: valid_harness)
    filters: list[str] = []
    picker = SimpleNamespace(
        addSelectionFilter=lambda value: filters.append(value) or True,
        setSelectionLimits=Mock(return_value=True),
    )
    event = SimpleNamespace(add=Mock(return_value=True))
    command = SimpleNamespace(
        commandInputs=SimpleNamespace(addSelectionInput=Mock(return_value=picker)),
        preSelect=event,
        validateInputs=event,
        execute=event,
        destroy=event,
    )
    commands._runtime.pending_auto_connect.prepare(
        commands.AutoConnectPickRequest(valid_harness.harness_id, "source", "pick-2", document)
    )

    commands.AutoConnectCreatedHandler().notify(SimpleNamespace(command=command))

    assert filters == ["Profiles", "SketchCurves"]


def test_auto_connect_native_execute_saves_and_refreshes_one_batch(
    addin_module: object,
    valid_harness: HarnessDefinition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Apply a reviewed ending and contact selection in one Fusion transaction.
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
        "fusion-start-token": (profile,),
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
    args = SimpleNamespace(executeFailed=False, executeFailedMessage="")
    request = commands.AutoConnectApplyRequest(
        definition.harness_id,
        definition.interfaces[0].interface_id,
        (UUID(int=801),),
        definition.connections[0].connection_id,
        None,
        True,
        True,
        None,
        document,
    )
    commands._ApplyExecuteHandler(request).notify(args)
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
        findEntityByToken=lambda token: (
            (contact,)
            if token in {"contact-a", "target-a"}
            else (first_profile,)
            if token == "fusion-start-token"
            else (second_profile,)
            if token == "fusion-end-token"
            else ()
        )
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
    args = SimpleNamespace(executeFailed=False, executeFailedMessage="")
    request = commands.AutoConnectApplyRequest(
        definition.harness_id,
        source.interfaces[0].interface_id,
        (UUID(int=801),),
        definition.connections[0].connection_id,
        None,
        True,
        True,
        None,
        document,
        target_interface.interface_id,
        (UUID(int=811),),
        definition.connections[1].connection_id,
        None,
        False,
        False,
        None,
    )
    commands._ApplyExecuteHandler(request).notify(args)
    assert not args.executeFailed
    stored = loads(gateway.serialized_definition)
    assert len(stored.attachment_associations) == 1
    assert stored.attachment_associations[0].attachment_ids == (
        stored.connections[0].attachments[0].attachment_id,
        stored.connections[1].attachments[0].attachment_id,
    )
    assert refresh.call_count == 2
