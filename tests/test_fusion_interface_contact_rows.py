"""
Fusion ownership, hole-center discovery, and row command dispatch regressions.
"""

import importlib
import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.application.interface_contact_rows import ContactSelectionMode, RowTarget
from cable_bundler.domain import AttachmentTargetKind


def _collection(*items: object) -> SimpleNamespace:
    """
    Represent indexed Fusion collections without Python iteration.
    """
    return SimpleNamespace(count=len(items), item=lambda index: items[index])


def _face(token: str, x: float, owner: object, occurrence: object) -> SimpleNamespace:
    """
    Create an asymmetric copper face whose single circular hole locates its pad.
    """
    geometry = SimpleNamespace(
        objectType="adsk::core::Circle3D", center=SimpleNamespace(x=x, y=0, z=0)
    )
    edge = SimpleNamespace(geometry=geometry, assemblyContext=occurrence)
    loop = SimpleNamespace(isOuter=False, coEdges=_collection(SimpleNamespace(edge=edge)))
    return SimpleNamespace(
        kind=AttachmentTargetKind.FACE,
        entityToken=token,
        assemblyContext=occurrence,
        body=SimpleNamespace(parentComponent=owner),
        geometry=SimpleNamespace(objectType="adsk::core::Plane"),
        centroid=SimpleNamespace(x=x, y=0.3, z=0),
        loops=_collection(loop),
    )


def test_row_collects_across_bodies_in_one_occurrence_using_hole_centers(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Collect the actual pad row while rejecting an identical second occurrence.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_rows")
    monkeypatch.setitem(vars(module), "attachment_target_kind", lambda entity: entity.kind)
    monkeypatch.setitem(vars(module), "_face_normal", lambda _: [0, 0, 1])
    owner = SimpleNamespace(entityToken="component")
    occurrence = SimpleNamespace(fullPathName="PCB:1")
    first, middle, last = [
        _face(token, x, owner, occurrence)
        for token, x in (("first", 0), ("middle", 1), ("last", 2))
    ]
    proxy_a = SimpleNamespace(faces=_collection(first, middle))
    proxy_b = SimpleNamespace(faces=_collection(last))
    body_a = SimpleNamespace(createForAssemblyContext=Mock(return_value=proxy_a))
    body_b = SimpleNamespace(createForAssemblyContext=Mock(return_value=proxy_b))
    owner.bRepBodies = _collection(body_a, body_b)
    selected = Mock()
    row = module.collect_contact_row(first, last, on_selected=selected)
    assert [item.token for item in row] == ["first", "middle", "last"]
    assert row[1].center_mm == (10, 0, 0)
    assert [call.args[0] for call in selected.call_args_list] == [first, middle, last]
    body_a.createForAssemblyContext.assert_called_once_with(occurrence)
    body_b.createForAssemblyContext.assert_called_once_with(occurrence)
    nearby = SimpleNamespace(
        boundingBox=SimpleNamespace(
            minPoint=SimpleNamespace(x=0.9, y=-0.1, z=0),
            maxPoint=SimpleNamespace(x=1.1, y=0.1, z=0),
        )
    )
    distant = SimpleNamespace(
        boundingBox=SimpleNamespace(
            minPoint=SimpleNamespace(x=0.9, y=2, z=0),
            maxPoint=SimpleNamespace(x=1.1, y=3, z=0),
        )
    )
    assert module._near_segment_bounds(nearby, (0, 0, 0), (20, 0, 0))
    assert not module._near_segment_bounds(distant, (0, 0, 0), (20, 0, 0))
    last.assemblyContext = SimpleNamespace(fullPathName="PCB:2")
    with pytest.raises(ValueError, match="same sketch or component occurrence"):
        module.validate_row_endpoints(first, last)


@pytest.mark.parametrize(
    "mode, collector",
    [
        (ContactSelectionMode.ROW, "collect_contact_row"),
        (ContactSelectionMode.PLANE, "collect_contact_plane"),
    ],
)
def test_row_command_collects_geometry_between_exactly_two_picks(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
    mode: ContactSelectionMode,
    collector: str,
) -> None:
    """
    Route the two native selections into ordered row collection before persistence.
    """
    module = importlib.import_module("cable_bundler.fusion.ui.commands.interface_contacts")
    monkeypatch.setitem(vars(module), "attachment_target_kind", lambda entity: entity.kind)
    monkeypatch.setitem(
        vars(sys.modules["adsk.core"]),
        "SelectionCommandInput",
        SimpleNamespace(cast=lambda item: item),
    )
    first = SimpleNamespace(entityToken="first", kind=AttachmentTargetKind.FACE)
    last = SimpleNamespace(entityToken="last", kind=AttachmentTargetKind.FACE)
    picker = SimpleNamespace(
        selectionCount=2, selection=lambda i: SimpleNamespace(entity=(first, last)[i])
    )
    inputs = SimpleNamespace(itemById=lambda _: picker)
    collect = Mock(
        return_value=tuple(
            RowTarget(token, AttachmentTargetKind.FACE, "Plane", (i, 0, 0), (0, 0, 1))
            for i, token in enumerate(("first", "middle", "last"))
        )
    )
    monkeypatch.setitem(vars(module), collector, collect)
    contacts = module._selected_contacts(inputs, mode)
    assert [contact.entity_token for contact in contacts] == ["first", "middle", "last"]
    collect.assert_called_once_with(first, last)
    picker.selectionCount = 1
    with pytest.raises(ValueError, match="first and last"):
        module._selected_contacts(inputs, mode)


def test_row_launcher_preserves_mode_and_rejects_unknown_modes(addin_module: object) -> None:
    """
    Pass the explicit row policy to the native command without a second action.
    """
    module = importlib.import_module("cable_bundler.fusion.ui.launchers")
    execute = Mock(return_value=True)
    application = SimpleNamespace(
        userInterface=SimpleNamespace(
            commandDefinitions=SimpleNamespace(itemById=lambda _: SimpleNamespace(execute=execute))
        )
    )
    payload = {"harnessId": str(UUID(int=1)), "interfaceId": str(UUID(int=2)), "mode": "row"}
    module._open_select_interface_contacts_command(application, json.dumps(payload))
    assert module._runtime.pending_interface_contacts.consume() == (
        UUID(int=1),
        UUID(int=2),
        ContactSelectionMode.ROW,
    )
    payload["mode"] = "unknown"
    with pytest.raises(ValueError):
        module._open_select_interface_contacts_command(application, json.dumps(payload))
    execute.assert_called_once()


def test_plane_adapter_collects_rectangle_in_owner_frame(
    addin_module: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Pass the local frame to membership and reject other occurrences or missing frames.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_planes")
    owner = SimpleNamespace(key=("board", "PCB:1"), occurrence=object())
    first = RowTarget("first", AttachmentTargetKind.FACE, "Plane", (0, 0, 0), (0, 0, 1))
    middle = RowTarget("middle", first.kind, "Plane", (1, 1, 0), first.normal)
    last = RowTarget("last", first.kind, "Plane", (2, 2, 0), first.normal)
    entities = [
        SimpleNamespace(target=target, geometry=SimpleNamespace(objectType="Plane"))
        for target in (first, middle, last)
    ]
    monkeypatch.setitem(vars(module), "_scope", lambda _: owner)
    monkeypatch.setitem(vars(module), "_parent_axes", lambda _: [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    monkeypatch.setitem(vars(module), "describe_row_target", lambda entity: entity.target)
    monkeypatch.setitem(vars(module), "_candidates", lambda *_: iter(entities))
    assert module.collect_contact_plane(entities[0], entities[-1]) == (first, middle, last)
    monkeypatch.setitem(vars(module), "_parent_axes", lambda _: None)
    with pytest.raises(ValueError, match="local frame"):
        module.validate_plane_corners(entities[0], entities[-1])
    monkeypatch.setitem(
        vars(module),
        "_scope",
        lambda entity: SimpleNamespace(key=("board", entity.target.token), occurrence=object()),
    )
    with pytest.raises(ValueError, match="same sketch or component occurrence"):
        module.validate_plane_corners(entities[0], entities[-1])
