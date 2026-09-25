"""
Focused regressions for Interface contact picking and diagram projection.
"""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.domain import AttachmentTargetKind, InterfaceContact


def _collection(*items: object) -> SimpleNamespace:
    """
    Mimic a Fusion indexed collection.
    """
    return SimpleNamespace(count=len(items), item=lambda index: items[index])


def test_picker_accepts_multiple_connection_targets_across_occurrences(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep picker order without requiring a brittle owner/proxy match.
    """
    command = importlib.import_module("cable_bundler.fusion.ui.commands.interface_contacts")
    core = sys.modules["adsk.core"]
    monkeypatch.setitem(
        vars(core), "SelectionCommandInput", SimpleNamespace(cast=lambda item: item)
    )
    face = SimpleNamespace(entityToken="face", kind=AttachmentTargetKind.FACE)
    edge = SimpleNamespace(entityToken="edge", kind=AttachmentTargetKind.CIRCULAR_EDGE)
    monkeypatch.setitem(vars(command), "attachment_target_kind", lambda entity: entity.kind)
    picker = SimpleNamespace(
        selectionCount=2,
        selection=lambda index: SimpleNamespace(entity=(face, edge)[index]),
    )
    inputs = SimpleNamespace(itemById=lambda _identifier: picker)
    contacts = command._selected_contacts(inputs)
    assert [contact.kind for contact in contacts] == [
        AttachmentTargetKind.FACE,
        AttachmentTargetKind.CIRCULAR_EDGE,
    ]
    assert [contact.entity_token for contact in contacts] == ["face", "edge"]


def test_native_picker_uses_filters_without_a_preselect_veto(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Let Fusion offer all supported targets without an owner-dependent callback.
    """
    command_module = importlib.import_module("cable_bundler.fusion.ui.commands.interface_contacts")
    application = object()
    core = sys.modules["adsk.core"]
    monkeypatch.setitem(vars(core), "Application", SimpleNamespace(get=lambda: application))
    monkeypatch.setitem(vars(command_module), "_require_active_design", lambda _app: object())
    monkeypatch.setitem(
        vars(command_module),
        "_create_harness_gateway",
        lambda _app: SimpleNamespace(read_harness_definition=lambda _id: "definition"),
    )
    interface_id = UUID(int=911)
    monkeypatch.setitem(
        vars(command_module),
        "loads",
        lambda _text: SimpleNamespace(interfaces=(SimpleNamespace(interface_id=interface_id),)),
    )
    filters: list[str] = []
    picker = SimpleNamespace(
        addSelectionFilter=lambda value: filters.append(value) or True,
        setSelectionLimits=Mock(return_value=True),
    )
    inputs = SimpleNamespace(addSelectionInput=Mock(return_value=picker))
    native_command = SimpleNamespace(
        commandInputs=inputs,
        preSelect=SimpleNamespace(add=Mock(return_value=True)),
        validateInputs=SimpleNamespace(add=Mock(return_value=True)),
        execute=SimpleNamespace(add=Mock(return_value=True)),
        destroy=SimpleNamespace(add=Mock(return_value=True)),
    )
    command_module._runtime.pending_interface_contacts.prepare((UUID(int=910), interface_id))
    command_module.SelectInterfaceContactsCreatedHandler().notify(
        SimpleNamespace(command=native_command)
    )
    assert filters == list(command_module._FILTERS)
    picker.setSelectionLimits.assert_called_once_with(1, 0)
    native_command.preSelect.add.assert_not_called()
    native_command.validateInputs.add.assert_called_once()
    native_command.execute.add.assert_called_once()


def test_projection_samples_profile_boundaries_and_keeps_mm_coordinates(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve sampled profile shape and placement for the diagram layer.
    """
    projection = importlib.import_module("cable_bundler.fusion.interface_contact_projection")

    def point(x: float, y: float, z: float = 0.0) -> SimpleNamespace:
        """
        Build one mock Fusion point in centimeters.
        """
        return SimpleNamespace(x=x, y=y, z=z)

    evaluator = SimpleNamespace(
        getParameterExtents=lambda: (True, 0.0, 1.0),
        getStrokes=lambda _start, _end, _tolerance: (
            True,
            [point(0, 0), point(1, 0), point(1, 2)],
        ),
    )
    sketch = SimpleNamespace(
        xDirection=point(1, 0),
        yDirection=point(0, 1),
        sketchToModelSpace=lambda sample: point(sample.x + 3, sample.y + 4, sample.z),
    )
    profile = SimpleNamespace(
        parentSketch=sketch,
        profileLoops=_collection(
            SimpleNamespace(
                profileCurves=_collection(
                    SimpleNamespace(geometry=SimpleNamespace(evaluator=evaluator)),
                )
            )
        ),
    )
    monkeypatch.setitem(
        vars(projection), "attachment_target_kind", lambda _entity: AttachmentTargetKind.PROFILE
    )
    monkeypatch.setitem(vars(projection), "attachment_target_name", lambda _entity, _kind: "Socket")
    design = SimpleNamespace(findEntityByToken=lambda _token: [profile])
    contact = InterfaceContact(UUID(int=901), AttachmentTargetKind.PROFILE, "profile")
    payload = projection.project_interface_contact(design, contact)
    assert payload["normal"] == [0.0, 0.0, 1.0]
    assert payload["loops"] == [[[30.0, 40.0, 0.0], [40.0, 40.0, 0.0], [40.0, 60.0, 0.0]]]
