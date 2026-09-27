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


def _face(
    token: str,
    x: float,
    owner: object,
    occurrence: object,
    y: float = 0.0,
) -> SimpleNamespace:
    """
    Create an asymmetric copper face whose single circular hole locates its pad.
    """
    geometry = SimpleNamespace(
        objectType="adsk::core::Circle3D", center=SimpleNamespace(x=x, y=y, z=0)
    )
    edge = SimpleNamespace(geometry=geometry, assemblyContext=occurrence)
    loop = SimpleNamespace(isOuter=False, coEdges=_collection(SimpleNamespace(edge=edge)))
    return SimpleNamespace(
        kind=AttachmentTargetKind.FACE,
        entityToken=token,
        assemblyContext=occurrence,
        body=SimpleNamespace(parentComponent=owner),
        geometry=SimpleNamespace(objectType="adsk::core::Plane"),
        centroid=SimpleNamespace(x=x, y=y + 0.3, z=0),
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
    module.validate_row_endpoints(first, last)


@pytest.mark.parametrize("mode", (ContactSelectionMode.ROW, ContactSelectionMode.PLANE))
def test_row_and_plane_collect_across_children_of_one_parent(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
    mode: ContactSelectionMode,
) -> None:
    """
    Collect sibling subcomponent contacts without including another assembly.
    """
    rows = importlib.import_module("cable_bundler.fusion.interface_contact_rows")
    planes = importlib.import_module("cable_bundler.fusion.interface_contact_planes")
    monkeypatch.setitem(vars(rows), "attachment_target_kind", lambda entity: entity.kind)
    monkeypatch.setitem(vars(rows), "_face_normal", lambda _entity: [0, 0, 1])
    monkeypatch.setitem(
        vars(planes), "_parent_axes", lambda _entity: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    )
    contacts = []
    occurrences = []
    for token, x, path in (
        ("first", 0, "Parent:1+Left:1"),
        ("middle", 1, "Parent:1+Middle:1"),
        ("last", 2, "Parent:1+Right:1"),
        ("unrelated", 1, "Elsewhere:1"),
    ):
        owner = SimpleNamespace(entityToken=f"owner-{token}")
        occurrence = SimpleNamespace(fullPathName=path, component=owner, isVisible=True)
        face = _face(token, x, owner, occurrence, y=x)
        proxy = SimpleNamespace(isVisible=True, faces=_collection(face))
        body = SimpleNamespace(createForAssemblyContext=Mock(return_value=proxy))
        owner.bRepBodies = _collection(body)
        contacts.append(face)
        occurrences.append(occurrence)
    root = SimpleNamespace(
        entityToken="root", bRepBodies=_collection(), allOccurrences=_collection(*occurrences)
    )
    design = SimpleNamespace(rootComponent=root)
    selected = Mock()
    collect = (
        rows.collect_contact_row
        if mode is ContactSelectionMode.ROW
        else planes.collect_contact_plane
    )

    result = collect(contacts[0], contacts[2], on_selected=selected, design=design)

    assert [target.token for target in result] == ["first", "middle", "last"]
    assert [call.args[0] for call in selected.call_args_list] == contacts[:3]


@pytest.mark.parametrize("mode", (ContactSelectionMode.ROW, ContactSelectionMode.PLANE))
def test_row_and_plane_include_child_between_parent_endpoints(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
    mode: ContactSelectionMode,
) -> None:
    """
    Search descendants even when both picked endpoints belong to the parent.
    """
    rows = importlib.import_module("cable_bundler.fusion.interface_contact_rows")
    planes = importlib.import_module("cable_bundler.fusion.interface_contact_planes")
    monkeypatch.setitem(vars(rows), "attachment_target_kind", lambda entity: entity.kind)
    monkeypatch.setitem(vars(rows), "_face_normal", lambda _entity: [0, 0, 1])
    monkeypatch.setitem(
        vars(planes), "_parent_axes", lambda _entity: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    )
    parent = SimpleNamespace(entityToken="parent")
    child = SimpleNamespace(entityToken="child")
    parent_occurrence = SimpleNamespace(fullPathName="Parent:1", component=parent, isVisible=True)
    child_occurrence = SimpleNamespace(
        fullPathName="Parent:1+Child:1", component=child, isVisible=True
    )
    first = _face("first", 0, parent, parent_occurrence, y=0)
    middle = _face("middle", 1, child, child_occurrence, y=1)
    last = _face("last", 2, parent, parent_occurrence, y=2)
    parent.bRepBodies = _collection(
        SimpleNamespace(
            createForAssemblyContext=Mock(
                return_value=SimpleNamespace(isVisible=True, faces=_collection(first, last))
            )
        )
    )
    child.bRepBodies = _collection(
        SimpleNamespace(
            createForAssemblyContext=Mock(
                return_value=SimpleNamespace(isVisible=True, faces=_collection(middle))
            )
        )
    )
    root = SimpleNamespace(
        entityToken="root", allOccurrences=_collection(parent_occurrence, child_occurrence)
    )
    design = SimpleNamespace(rootComponent=root)
    collect = (
        rows.collect_contact_row
        if mode is ContactSelectionMode.ROW
        else planes.collect_contact_plane
    )

    result = collect(first, last, design=design)

    assert [target.token for target in result] == ["first", "middle", "last"]


def test_cross_assembly_sketch_scopes_include_root_and_child_sketches(
    addin_module: object,
) -> None:
    """
    Keep sketch targets scoped to sketches in each relevant component.
    """
    rows = importlib.import_module("cable_bundler.fusion.interface_contact_rows")
    root_sketch = SimpleNamespace(entityToken="root-sketch", isVisible=True)
    child_sketch = SimpleNamespace(entityToken="child-sketch", isVisible=True)
    child_component = SimpleNamespace(sketches=_collection(child_sketch))
    occurrence = SimpleNamespace(fullPathName="Child:1", component=child_component, isVisible=True)
    root = SimpleNamespace(
        sketches=_collection(root_sketch), allOccurrences=_collection(occurrence)
    )
    first = SimpleNamespace(parentSketch=root_sketch, assemblyContext=None)
    last = SimpleNamespace(parentSketch=child_sketch, assemblyContext=occurrence)

    scopes = list(
        rows._candidate_scopes(
            first,
            last,
            AttachmentTargetKind.SKETCH_POINT,
            SimpleNamespace(rootComponent=root),
        )
    )

    assert [(scope.owner, scope.occurrence) for scope in scopes] == [
        (root_sketch, None),
        (child_sketch, occurrence),
    ]


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
    collect.reset_mock()
    design = object()
    module._selected_contacts(inputs, mode, design)
    assert collect.call_args.args == (first, last)
    assert collect.call_args.kwargs["design"] is design
    assert callable(collect.call_args.kwargs["on_selected"])
    picker.selectionCount = 1
    with pytest.raises(ValueError, match="first and last"):
        module._selected_contacts(inputs, mode)


@pytest.mark.parametrize("mode", (ContactSelectionMode.ROW, ContactSelectionMode.PLANE))
def test_row_and_plane_enable_ok_for_two_persistent_targets(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
    mode: ContactSelectionMode,
) -> None:
    """
    Let execution report geometry errors after the picker accepts two targets.
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
    picks = [first]
    picker = SimpleNamespace(
        selectionCount=1,
        selection=lambda index: SimpleNamespace(entity=picks[index]),
    )
    args = SimpleNamespace(
        inputs=SimpleNamespace(itemById=lambda _identifier: picker),
        areInputsValid=False,
    )
    handler = module._ValidateHandler(mode)

    handler.notify(args)
    assert args.areInputsValid is False
    picks.append(last)
    picker.selectionCount = 2
    handler.notify(args)
    assert args.areInputsValid is True
    picks[1] = first
    handler.notify(args)
    assert args.areInputsValid is False


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
    Pass the local frame to membership and reject missing frames.
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
    monkeypatch.setitem(vars(module), "_candidate_scopes", lambda *_: iter((owner,)))
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
    monkeypatch.setitem(vars(module), "_parent_axes", lambda _: [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    assert module.validate_plane_corners(entities[0], entities[-1]).last == last
