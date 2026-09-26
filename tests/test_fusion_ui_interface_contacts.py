"""
Focused regressions for Interface contact picking and diagram projection.
"""

from __future__ import annotations

import importlib
import json
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.application.interface_contact_rows import ContactSelectionMode
from cable_bundler.domain import AttachmentTargetKind, InterfaceContact


def test_contact_name_edit_routes_to_transactional_application_service(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Route the clicked contact identity and text through the normal edit command.
    """
    edits = importlib.import_module("cable_bundler.fusion.ui.edits")
    gateway = object()
    rename = Mock()
    monkeypatch.setitem(vars(edits), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(vars(edits), "name_interface_contacts", rename)
    notice = edits._apply_palette_edit(
        object(),
        "set_interface_contact_name",
        json.dumps(
            {
                "harnessId": str(UUID(int=1)),
                "interfaceId": str(UUID(int=2)),
                "contactId": str(UUID(int=3)),
                "name": "J5.2",
            }
        ),
    )
    assert notice == "Interface contact name updated."
    rename.assert_called_once_with(UUID(int=1), UUID(int=2), {UUID(int=3): "J5.2"}, gateway)


def test_contact_details_edit_routes_value_and_pin_together(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Save both popup fields through one transactional application edit.
    """
    edits = importlib.import_module("cable_bundler.fusion.ui.edits")
    gateway = object()
    update = Mock()
    monkeypatch.setitem(vars(edits), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(vars(edits), "set_interface_contact_details", update)
    payload = {
        "harnessId": str(UUID(int=1)),
        "interfaceId": str(UUID(int=2)),
        "contactId": str(UUID(int=3)),
        "value": "J5.2",
        "pin": "P7",
    }

    notice = edits._apply_palette_edit(
        object(), "set_interface_contact_details", json.dumps(payload)
    )

    assert notice == "Interface contact updated."
    update.assert_called_once_with(UUID(int=1), UUID(int=2), UUID(int=3), "J5.2", "P7", gateway)
    with pytest.raises(ValueError, match="value and pin must be text"):
        edits._apply_palette_edit(
            object(), "set_interface_contact_details", json.dumps({**payload, "pin": None})
        )


def test_contact_deletion_routes_selected_ids_as_one_edit(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse the selected identities before issuing one transactional removal.
    """
    edits = importlib.import_module("cable_bundler.fusion.ui.edits")
    gateway = object()
    remove = Mock()
    monkeypatch.setitem(vars(edits), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(vars(edits), "remove_interface_contacts", remove)
    payload = {
        "harnessId": str(UUID(int=1)),
        "interfaceId": str(UUID(int=2)),
        "contactIds": [str(UUID(int=3)), str(UUID(int=4))],
    }
    notice = edits._apply_palette_edit(object(), "remove_interface_contacts", json.dumps(payload))
    assert notice == "Deleted selected Interface contacts."
    remove.assert_called_once_with(UUID(int=1), UUID(int=2), (UUID(int=3), UUID(int=4)), gateway)
    with pytest.raises(ValueError, match="selected contact IDs"):
        edits._apply_palette_edit(
            object(), "remove_interface_contacts", json.dumps({**payload, "contactIds": []})
        )
    assert remove.call_count == 1


def test_live_board_reader_uses_placed_through_hole_signal_contacts(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Convert real ECAD units without applying element placement a second time.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_naming")
    electron = ModuleType("adsk.electron")
    electron.Board = SimpleNamespace(cast=lambda product: product)
    monkeypatch.setitem(sys.modules, "adsk.electron", electron)
    monkeypatch.setitem(vars(sys.modules["adsk"]), "electron", electron)
    pad = SimpleNamespace(x=569920, y=13574720, diameter=438400, drill=326400)
    contact = SimpleNamespace(name="03", pad=pad)
    element = SimpleNamespace(name="J3", x=100, y=200, angle=270, mirror=True)
    reference = SimpleNamespace(element=element, contact=contact)
    smd_reference = SimpleNamespace(contact=SimpleNamespace(pad=None))
    malformed_reference = SimpleNamespace(contact=None)
    board = SimpleNamespace(
        signals=_collection(
            SimpleNamespace(
                name="P1.09", contactRefs=_collection(reference, smd_reference, malformed_reference)
            )
        )
    )
    application = SimpleNamespace(
        documents=_collection(SimpleNamespace(products=_collection(board)))
    )
    pads = module._live_board_pads(application)
    assert len(pads) == 1
    assert pads[0].label == "J3.03"
    assert pads[0].signal == "P1.09"
    assert (pads[0].x, pads[0].y, pads[0].layer) == pytest.approx((1.781, 42.421, 0))
    assert (pads[0].width, pads[0].height, pads[0].drill_diameter_mm) == pytest.approx(
        (1.37, 1.37, 1.02)
    )
    board.signals = _collection(SimpleNamespace(name="GND", contactRefs=_collection(smd_reference)))
    with pytest.raises(ValueError, match="no connected through-hole pad data"):
        module._live_board_pads(application)


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


@pytest.mark.parametrize(
    "mode, limits",
    [
        (ContactSelectionMode.MANUAL, (1, 0)),
        (ContactSelectionMode.ROW, (2, 2)),
        (ContactSelectionMode.PLANE, (2, 2)),
    ],
)
def test_native_picker_uses_filters_without_a_preselect_veto(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
    mode: ContactSelectionMode,
    limits: tuple[int, int],
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
    command_module._runtime.pending_interface_contacts.prepare((UUID(int=910), interface_id, mode))
    command_module.SelectInterfaceContactsCreatedHandler().notify(
        SimpleNamespace(command=native_command)
    )
    assert filters == list(command_module._FILTERS)
    picker.setSelectionLimits.assert_called_once_with(*limits)
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
    contact = InterfaceContact(UUID(int=901), AttachmentTargetKind.PROFILE, "profile", "J5.2")
    payload = projection.project_interface_contact(design, contact)
    assert payload["name"] == payload["assignedName"] == "J5.2"
    assert payload["normal"] == [0.0, 0.0, 1.0]
    assert payload["parentAxes"] == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    assert payload["loops"] == [[[30.0, 40.0, 0.0], [40.0, 40.0, 0.0], [40.0, 60.0, 0.0]]]


def test_projection_keeps_separated_faces_in_assembly_space(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve pad outlines and spacing when a proxy face yields native loop edges.
    """
    projection = importlib.import_module("cable_bundler.fusion.interface_contact_projection")

    def point(x: float, y: float, z: float = 0.0) -> SimpleNamespace:
        """
        Build a Fusion-like point or vector in centimeters.
        """
        return SimpleNamespace(x=x, y=y, z=z)

    def edge(start: tuple[float, float], end: tuple[float, float]) -> SimpleNamespace:
        """
        Return a native edge whose evaluator must be proxied before sampling.
        """

        def in_context(occurrence: SimpleNamespace) -> SimpleNamespace:
            """
            Expose world-space evaluator coordinates for the face occurrence.
            """
            samples = [point(x + occurrence.x, y + occurrence.y) for x, y in (start, end)]
            evaluator = SimpleNamespace(
                getParameterExtents=lambda: (True, 0.0, 1.0),
                getStrokes=lambda _start, _end, _tolerance: (True, samples),
            )
            return SimpleNamespace(evaluator=evaluator, assemblyContext=occurrence)

        return SimpleNamespace(assemblyContext=None, createForAssemblyContext=in_context)

    corners = ((0.0, 0.0), (0.4, 0.0), (0.4, 0.1), (0.0, 0.1))
    coedges = _collection(
        *(
            SimpleNamespace(edge=edge(corners[index], corners[(index + 1) % 4]))
            for index in range(4)
        )
    )
    faces = {
        f"pad-{index}": SimpleNamespace(
            assemblyContext=SimpleNamespace(x=index * 0.8, y=index * 0.3),
            loops=_collection(SimpleNamespace(coEdges=coedges)),
            geometry=SimpleNamespace(normal=point(0, 0, 1)),
        )
        for index in range(7)
    }
    monkeypatch.setitem(
        vars(projection), "attachment_target_kind", lambda _entity: AttachmentTargetKind.FACE
    )
    monkeypatch.setitem(vars(projection), "attachment_target_name", lambda _entity, _kind: "Pad")
    design = SimpleNamespace(findEntityByToken=lambda token: [faces[token]])
    outlines = [
        projection.project_interface_contact(
            design, InterfaceContact(UUID(int=index + 1), AttachmentTargetKind.FACE, f"pad-{index}")
        )["loops"][0]
        for index in range(7)
    ]
    assert all(len(outline) == 5 for outline in outlines)
    for index, outline in enumerate(outlines):
        assert outline[0][:2] == pytest.approx([index * 8.0, index * 3.0])
    assert [outline[1][0] - outline[0][0] for outline in outlines] == pytest.approx([4.0] * 7)


def test_projection_exposes_parent_axes_without_repositioning_geometry(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Carry the parent's assembly orientation separately from a face's normal.
    """
    projection = importlib.import_module("cable_bundler.fusion.interface_contact_projection")
    origin = SimpleNamespace(x=10.0, y=20.0, z=30.0)
    axes = [
        SimpleNamespace(x=0.0, y=0.0, z=1.0),
        SimpleNamespace(x=1.0, y=0.0, z=0.0),
        SimpleNamespace(x=0.0, y=1.0, z=0.0),
    ]
    face = SimpleNamespace(
        assemblyContext=SimpleNamespace(
            transform2=SimpleNamespace(getAsCoordinateSystem=lambda: (origin, *axes))
        ),
        geometry=SimpleNamespace(normal=SimpleNamespace(x=0.0, y=-1.0, z=0.0)),
        centroid=origin,
    )
    monkeypatch.setitem(
        vars(projection), "attachment_target_kind", lambda _entity: AttachmentTargetKind.FACE
    )
    monkeypatch.setitem(vars(projection), "attachment_target_name", lambda _entity, _kind: "Pad")
    contact = InterfaceContact(UUID(int=950), AttachmentTargetKind.FACE, "face")
    payload = projection.project_interface_contact(
        SimpleNamespace(findEntityByToken=lambda _token: [face]), contact
    )
    assert payload["parentAxes"] == [[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert payload["normal"] == [0.0, -1.0, 0.0]
    assert payload["loops"] == [[[100.0, 200.0, 300.0]]]


def test_unavailable_parent_transform_uses_fallback(addin_module: object) -> None:
    """
    Keep contacts displayable when the host cannot provide their parent frame.
    """
    projection = importlib.import_module("cable_bundler.fusion.interface_contact_projection")
    transform = SimpleNamespace(getAsCoordinateSystem=Mock(side_effect=RuntimeError("unavailable")))
    entity = SimpleNamespace(assemblyContext=SimpleNamespace(transform2=transform))
    assert projection._parent_axes(entity) is None
    assert projection._parent_axes(SimpleNamespace()) is None
