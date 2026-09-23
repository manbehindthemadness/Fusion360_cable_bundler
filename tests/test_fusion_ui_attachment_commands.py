"""
Focused Fusion UI regressions for native commands.
"""

from __future__ import annotations

from cable_bundler.domain import AttachmentTargetKind, CableEndAttachment, CableEndTarget
from tests.fusion_ui_support import (
    UUID,
    Mock,
    SimpleNamespace,
    _PaletteLifecycleModule,
    importlib,
    pytest,
    sys,
)


def test_cable_end_attachment_picker_reads_supported_target_and_optional_name(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Convert one named joint origin selection into persistent attachment metadata.
    """
    core_module = sys.modules["adsk.core"]
    fusion_module = sys.modules["adsk.fusion"]
    core_module.SelectionCommandInput = SimpleNamespace(  # type: ignore[attr-defined]
        cast=lambda value: value
    )
    core_module.StringValueCommandInput = SimpleNamespace(  # type: ignore[attr-defined]
        cast=lambda value: value
    )
    entity_types = (
        ("Profile", "profile"),
        ("BRepFace", "face"),
        ("JointOrigin", "joint"),
        ("BRepEdge", "edge"),
        ("ConstructionPoint", "construction"),
        ("SketchPoint", "sketch"),
    )
    for type_name, marker in entity_types:
        setattr(
            fusion_module,
            type_name,
            SimpleNamespace(
                cast=lambda value, expected=marker: value if value.kind == expected else None
            ),
        )
    target = SimpleNamespace(
        kind="joint",
        entityToken="joint-token",
        name="Connector J1",
        nativeObject=None,
    )
    selection_input = SimpleNamespace(
        selectionCount=1,
        selection=lambda _index: SimpleNamespace(entity=target, point=None),
    )
    name_input = SimpleNamespace(value=" Pin 4 ")
    inputs_by_id = {
        addin_module.CABLE_END_ATTACHMENT_TARGET_INPUT_ID: selection_input,
        addin_module.CABLE_END_ATTACHMENT_NAME_INPUT_ID: name_input,
    }
    pending = CableEndAttachment(None, attachment_id=UUID(int=3))
    state = addin_module._AttachCableEndCommandState(
        UUID(int=1), UUID(int=2), pending.attachment_id, (), pending
    )

    attachment = addin_module._read_attachment_inputs(
        SimpleNamespace(itemById=inputs_by_id.get),
        state,
    )

    assert attachment.entity_token == "joint-token"
    assert attachment.inherited_name == "Connector J1"
    assert attachment.name == "Pin 4"
    assert attachment.target_kind.value == "joint_origin"


def test_face_attachment_uses_a_subcomponent_faces_native_center(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Derive stable center parameters without mixing assembly and native coordinates.
    """
    native_center = object()
    native_evaluator = SimpleNamespace(
        getParameterAtPoint=Mock(return_value=[True, SimpleNamespace(x=1.25, y=2.5)]),
        isParameterOnFace=Mock(return_value=True),
    )
    native_face = SimpleNamespace(
        evaluator=native_evaluator,
        centroid=native_center,
        pointOnFace=object(),
    )
    proxy_face = SimpleNamespace(
        nativeObject=native_face,
        evaluator=SimpleNamespace(getParameterAtPoint=Mock(return_value=(False, None))),
        centroid=object(),
        pointOnFace=object(),
    )

    parameters = addin_module._read_face_parameters(proxy_face)

    assert parameters == (1.25, 2.5)
    native_evaluator.getParameterAtPoint.assert_called_once_with(native_center)
    native_evaluator.isParameterOnFace.assert_called_once()


def test_face_attachment_uses_an_interior_point_when_centroid_is_outside_face(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Keep concave and holed faces attachable when their centroid is not on the face.
    """
    centroid = object()
    interior_point = object()
    centroid_parameter = SimpleNamespace(x=1.0, y=2.0)
    interior_parameter = SimpleNamespace(x=3.0, y=4.0)
    evaluator = SimpleNamespace(
        getParameterAtPoint=Mock(
            side_effect=((True, centroid_parameter), (True, interior_parameter))
        ),
        isParameterOnFace=Mock(side_effect=(False, True)),
    )
    face = SimpleNamespace(
        nativeObject=None,
        evaluator=evaluator,
        centroid=centroid,
        pointOnFace=interior_point,
    )

    parameters = addin_module._read_face_parameters(face)

    assert parameters == (3.0, 4.0)
    evaluated_points = [item.args[0] for item in evaluator.getParameterAtPoint.call_args_list]
    assert evaluated_points == [centroid, interior_point]


def test_attachment_completion_partially_refreshes_generated_geometry(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Rebuild generated output for the attached end before refreshing its preview.
    """
    attachments = importlib.import_module("cable_bundler.fusion.ui.commands.attachments")
    harness_id = UUID(int=1)
    connection_id = UUID(int=2)
    attachment_id = UUID(int=3)
    pending = CableEndAttachment(None, attachment_id=attachment_id)
    state = attachments._AttachCableEndCommandState(
        harness_id, connection_id, attachment_id, (), pending
    )
    target = CableEndTarget(
        AttachmentTargetKind.JOINT_ORIGIN,
        "battery-ground",
        "Battery GND",
    )
    attachment = CableEndAttachment(
        AttachmentTargetKind.JOINT_ORIGIN,
        "battery-ground",
        "Battery GND",
        attachment_id=attachment_id,
    )
    definition = object()
    component = object()
    design = object()
    viewport = SimpleNamespace(refresh=Mock())
    application = SimpleNamespace(activeViewport=viewport)
    gateway = SimpleNamespace(
        read_harness_definition=Mock(return_value="definition"),
        harness_component=Mock(return_value=component),
    )
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    attach = Mock()
    refresh_generated = Mock(return_value=1)
    send = Mock()
    monkeypatch.setitem(vars(attachments), "_read_attachment_inputs", lambda *_args: target)
    monkeypatch.setitem(vars(attachments), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(vars(attachments), "attach_cable_end", attach)
    monkeypatch.setitem(vars(attachments), "loads", lambda _serialized: definition)
    monkeypatch.setitem(vars(attachments), "_require_active_design", lambda _app: design)
    monkeypatch.setitem(
        vars(attachments),
        "refresh_generated_cable_groups_for_connection",
        refresh_generated,
    )
    monkeypatch.setitem(vars(attachments), "_refresh_active_preview", lambda *_args: "")
    monkeypatch.setitem(vars(attachments), "_send_palette_state", send)
    args = SimpleNamespace(
        command=SimpleNamespace(commandInputs=object()),
        executeFailed=False,
        executeFailedMessage="",
    )

    attachments._AttachCableEndExecuteHandler(state).notify(args)

    attach.assert_called_once_with(harness_id, connection_id, attachment_id, attachment, gateway)
    refresh_generated.assert_called_once_with(design, component, definition, connection_id)
    viewport.refresh.assert_called_once_with()
    send.assert_called_once_with(
        application,
        "Attached cable end to Battery GND. Updated 1 generated cable group.",
    )
    assert not args.executeFailed


def test_shielding_attachment_completion_skips_geometry_refresh(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Persist the secondary relationship without rebuilding solids or route previews.
    """
    attachments = importlib.import_module("cable_bundler.fusion.ui.commands.attachments")
    harness_id = UUID(int=1)
    connection_id = UUID(int=2)
    attachment_id = UUID(int=3)
    pending = CableEndAttachment(None, attachment_id=attachment_id)
    state = attachments._AttachCableEndCommandState(
        harness_id, connection_id, attachment_id, (), pending, "shielding"
    )
    target = CableEndTarget(
        AttachmentTargetKind.CONSTRUCTION_POINT,
        "shield-stud",
        "Shield stud",
    )
    application = SimpleNamespace(activeViewport=SimpleNamespace(refresh=Mock()))
    gateway = object()
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    attach = Mock()
    refresh_generated = Mock()
    refresh_preview = Mock()
    send = Mock()
    monkeypatch.setitem(vars(attachments), "_read_attachment_inputs", lambda *_args: target)
    monkeypatch.setitem(vars(attachments), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(vars(attachments), "attach_cable_end_shielding", attach)
    monkeypatch.setitem(
        vars(attachments), "refresh_generated_cable_groups_for_connection", refresh_generated
    )
    monkeypatch.setitem(vars(attachments), "_refresh_active_preview", refresh_preview)
    monkeypatch.setitem(vars(attachments), "_send_palette_state", send)
    args = SimpleNamespace(
        command=SimpleNamespace(commandInputs=object()),
        executeFailed=False,
        executeFailedMessage="",
    )

    attachments._AttachCableEndExecuteHandler(state).notify(args)

    attach.assert_called_once_with(harness_id, connection_id, attachment_id, target, gateway)
    refresh_generated.assert_not_called()
    refresh_preview.assert_not_called()
    application.activeViewport.refresh.assert_not_called()
    send.assert_called_once_with(application, "Connected shielding to Shield stud.")
    assert not args.executeFailed


def test_cable_end_attachment_picker_opens_for_an_unresolved_saved_target(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reconnect a stale node while retaining the agreed set of selectable target types.
    """
    harness_id = UUID(int=1)
    connection_id = UUID(int=2)
    attachment_id = UUID(int=3)
    application = object()
    stale_attachment = CableEndAttachment(
        AttachmentTargetKind.JOINT_ORIGIN,
        "missing-joint-token",
        "Missing joint",
        name="Bulkhead",
        attachment_id=attachment_id,
    )
    connection = SimpleNamespace(
        connection_id=connection_id,
        attachments=(stale_attachment,),
        member_tokens=("guide-token",),
    )
    gateway = SimpleNamespace(read_harness_definition=Mock(return_value="definition"))
    design = SimpleNamespace(findEntityByToken=lambda _token: ())
    attachments = importlib.import_module("cable_bundler.fusion.ui.commands.attachments")
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    monkeypatch.setitem(vars(attachments), "_require_active_design", lambda _app: design)
    monkeypatch.setitem(vars(attachments), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(
        vars(attachments),
        "loads",
        lambda _serialized: SimpleNamespace(connections=(connection,)),
    )
    filters: list[str] = []
    selection_input = SimpleNamespace(
        addSelectionFilter=lambda value: filters.append(value) or True,
        setSelectionLimits=Mock(return_value=True),
    )
    command_inputs = SimpleNamespace(
        addSelectionInput=Mock(return_value=selection_input),
        addStringValueInput=Mock(return_value=object()),
    )
    accepted_event = SimpleNamespace(add=Mock(return_value=True))
    command = SimpleNamespace(
        commandInputs=command_inputs,
        preSelect=accepted_event,
        validateInputs=accepted_event,
        execute=accepted_event,
        destroy=accepted_event,
    )
    addin_module._runtime.pending_cable_end_attachment.prepare(
        (harness_id, connection_id, attachment_id, "main")
    )

    addin_module._AttachCableEndCreatedHandler().notify(SimpleNamespace(command=command))

    assert filters == [
        "Profiles",
        "Faces",
        "JointOrigins",
        "CircularEdges",
        "ConstructionPoints",
        "SketchPoints",
    ]
    command_inputs.addStringValueInput.assert_called_once_with(
        addin_module.CABLE_END_ATTACHMENT_NAME_INPUT_ID,
        "Connection Name",
        "Bulkhead",
    )


def test_cable_end_attachment_launcher_preserves_shielding_relationship(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Carry the selected submenu relationship into the shared native picker command.
    """
    harness_id = UUID(int=1)
    connection_id = UUID(int=2)
    attachment_id = UUID(int=3)
    command_definition = SimpleNamespace(execute=Mock(return_value=True))
    application = SimpleNamespace(
        userInterface=SimpleNamespace(
            commandDefinitions=SimpleNamespace(itemById=lambda _identity: command_definition)
        )
    )
    payload = (
        f'{{"harnessId":"{harness_id}","connectionId":"{connection_id}",'
        f'"attachmentId":"{attachment_id}","relationship":"shielding"}}'
    )

    launchers = importlib.import_module("cable_bundler.fusion.ui.launchers")
    launchers._open_attach_cable_end_command(application, payload)

    assert addin_module._runtime.pending_cable_end_attachment.consume() == (
        harness_id,
        connection_id,
        attachment_id,
        "shielding",
    )


@pytest.mark.parametrize(
    "target_kind",
    (
        "profile",
        "face",
        "joint_origin",
        "circular_edge",
        "construction_point",
        "sketch_point",
    ),
)
def test_cable_end_attachment_validation_enables_ok_for_each_filtered_target(
    addin_module: _PaletteLifecycleModule,
    target_kind: str,
) -> None:
    """
    Enable OK without requesting target-specific persistent data during validation.
    """
    core_module = sys.modules["adsk.core"]
    core_module.SelectionCommandInput = SimpleNamespace(  # type: ignore[attr-defined]
        cast=lambda value: value
    )
    selection_input = SimpleNamespace(
        selectionCount=1,
        selection=lambda _index: SimpleNamespace(
            entity=SimpleNamespace(kind=target_kind),
        ),
    )
    inputs = SimpleNamespace(
        itemById=lambda identity: (
            selection_input
            if identity == addin_module.CABLE_END_ATTACHMENT_TARGET_INPUT_ID
            else None
        )
    )
    args = SimpleNamespace(inputs=inputs, areInputsValid=False)
    attachments = importlib.import_module("cable_bundler.fusion.ui.commands.attachments")

    attachments._AttachCableEndValidateInputsHandler().notify(args)

    assert args.areInputsValid, target_kind


def test_relationship_selector_refreshes_only_for_geometry_input_changes(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve an active choice while continuing to respond to geometry changes.
    """
    state = addin_module._AddJunctionRelationshipCommandState(
        UUID(int=1),
        UUID(int=2),
        (),
    )
    update_choices = Mock()
    junction_commands = importlib.import_module("cable_bundler.fusion.ui.commands.junctions")
    monkeypatch.setitem(
        vars(junction_commands),
        "_update_junction_relationship_choices",
        update_choices,
    )

    addin_module._AddJunctionRelationshipInputChangedHandler(state).notify(
        SimpleNamespace(
            input=SimpleNamespace(id=addin_module.JUNCTION_RELATIONSHIP_CHOICE_INPUT_ID),
            inputs=object(),
        )
    )

    update_choices.assert_not_called()

    inputs = object()
    addin_module._AddJunctionRelationshipInputChangedHandler(state).notify(
        SimpleNamespace(
            input=SimpleNamespace(id=addin_module.JUNCTION_RELATIONSHIP_GEOMETRY_INPUT_ID),
            inputs=inputs,
        )
    )

    update_choices.assert_called_once_with(inputs, state)
