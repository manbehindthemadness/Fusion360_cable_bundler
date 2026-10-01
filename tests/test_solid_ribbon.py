"""
Verify Solid ribbon contact planning without a live Fusion design.
"""

from __future__ import annotations

import json
from dataclasses import replace
from importlib import import_module
from types import SimpleNamespace
from uuid import UUID

import pytest

from cable_bundler.application import CableGroupRouteLeg
from cable_bundler.domain import (
    AttachmentTargetKind,
    CableEndAttachment,
    CableGroupType,
    HarnessDefinition,
    InterfaceContact,
    InterfaceDefinition,
    InterfaceTarget,
    InterfaceTargetKind,
    RibbonBodyType,
)
from cable_bundler.routing import CubicBezier, RibbonFrame, RibbonShape, RoutePreview, Vector3
from tests.fusion_ui_support import _PaletteLifecycleModule


def _route(identity: int, start: Vector3, end: Vector3) -> RoutePreview:
    """
    Create one deterministic contact-to-guide cubic.
    """
    return RoutePreview(
        UUID(int=identity),
        f"Route {identity}",
        (start, end),
        (CubicBezier(start, start, end, end),),
    )


def _fixture(
    definition: HarnessDefinition,
) -> tuple[
    HarnessDefinition,
    CableGroupRouteLeg,
    tuple[tuple[CableGroupRouteLeg, RoutePreview], ...],
    RibbonShape,
]:
    """
    Connect three persistent lines to wider and tighter inline contacts.
    """
    group = replace(
        definition.cable_groups[0],
        group_type=CableGroupType.RIBBON,
        ribbon_body_type=RibbonBodyType.SOLID,
        ribbon_lines=3,
    )
    endpoints = ((-3.0, 0.0, 3.0), (-0.8, 0.0, 0.8))
    connections = []
    interfaces = []
    branches = []
    for end_index, connection in enumerate(definition.connections):
        roots = tuple(
            CableEndAttachment(
                AttachmentTargetKind.SKETCH_POINT,
                f"contact-{end_index}-{line}",
                f"Contact {line}",
                attachment_id=UUID(int=100 + end_index * 3 + line),
                pin_number=str(line),
            )
            for line in range(1, 4)
        )
        connections.append(
            replace(connection, attachment=roots[0], additional_attachments=roots[1:])
        )
        interfaces.append(
            InterfaceDefinition(
                UUID(int=200 + end_index),
                f"Interface {end_index}",
                (InterfaceTarget(InterfaceTargetKind.OCCURRENCE, f"interface-{end_index}"),),
                tuple(
                    InterfaceContact(
                        UUID(int=300 + end_index * 3 + line),
                        root.target_kind,
                        root.entity_token,
                    )
                    for line, root in enumerate(roots)
                ),
            )
        )
        for line, root in enumerate(roots):
            contact = Vector3(endpoints[end_index][line], 0.0, 0.0 if end_index == 0 else 100.0)
            guide = Vector3(float(line - 1), 0.0, 10.0 if end_index == 0 else 90.0)
            route = _route(400 + end_index * 3 + line, contact, guide)
            branches.append(
                (
                    CableGroupRouteLeg(
                        route.cable_id,
                        group.cable_group_id,
                        route.cable_number,
                        connection.connection_id,
                        None,
                        (),
                        (),
                        is_connection_branch=True,
                        attachment_id=root.attachment_id,
                    ),
                    route,
                )
            )
    definition = replace(
        definition,
        connections=tuple(connections),
        cable_groups=(group,),
        interfaces=tuple(interfaces),
    )
    frames = tuple(
        RibbonFrame(
            Vector3(0.0, 0.0, z),
            Vector3(0.0, 0.0, 1.0),
            Vector3(1.0, 0.0, 0.0),
            Vector3(0.0, 1.0, 0.0),
        )
        for z in (10.0, 90.0)
    )
    lanes = tuple(
        (Vector3(float(line - 1), 0.0, 10.0), Vector3(float(line - 1), 0.0, 90.0))
        for line in range(3)
    )
    shape = RibbonShape(frames, lanes, (80.0, 80.0, 80.0), 0.0, False, 1.0)
    leg = CableGroupRouteLeg(
        UUID(int=500),
        group.cable_group_id,
        "Main",
        connections[0].connection_id,
        connections[1].connection_id,
        (),
        (),
    )
    return definition, leg, tuple(branches), shape


def test_solid_plan_expands_web_and_shrinks_lobes(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep nominal lobe thickness while ending on both contact planes.
    """
    del addin_module
    solid = import_module("cable_bundler.fusion.solid_ribbon")
    frames = import_module("cable_bundler.fusion.route_preview_parts.frames")
    definition, leg, branches, shape = _fixture(valid_harness)
    profile = frames.ProfileFrame(
        Vector3(0.0, 0.0, 0.0),
        Vector3(0.0, 0.0, 1.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
    )
    monkeypatch.setitem(vars(solid), "connection_profile_frames", lambda *_args: (profile,))
    starts = {item[0].attachment_id: item[1].curves[0].start for item in branches}
    monkeypatch.setitem(
        vars(solid),
        "connection_attachment_frame",
        lambda _design, _connection, attachment, _guide, _cache: replace(
            profile, origin=starts[attachment.attachment_id]
        ),
    )

    plan = solid.solid_ribbon_plan(
        None, definition, definition.cable_groups[0], leg, branches, shape
    )

    assert len(plan.sections) == 10
    assert plan.sections[0].lobe_width_mm == pytest.approx(1.2)
    assert plan.sections[-1].lobe_width_mm == pytest.approx(0.8 * 0.98)
    assert tuple(point.x for point in plan.sections[0].centers) == (-3.0, 0.0, 3.0)
    assert tuple(point.x for point in plan.sections[-1].centers) == (-0.8, 0.0, 0.8)
    assert all(point.z == 0.0 for point in plan.sections[0].centers)
    assert all(point.z == 100.0 for point in plan.sections[-1].centers)
    assert len(plan.lanes) == 3
    assert len(plan.contact_ids[0]) == len(plan.contact_ids[1]) == 3
    assert plan.contact_ids[0][0] == str(UUID(int=300))
    assert plan.attachment_ids[0][0] == str(UUID(int=101))


def test_solid_plan_rejects_missing_contact_route(
    addin_module: _PaletteLifecycleModule,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Fail instead of silently producing a partial or Split-style end.
    """
    del addin_module
    solid = import_module("cable_bundler.fusion.solid_ribbon")
    definition, leg, branches, shape = _fixture(valid_harness)
    with pytest.raises(ValueError, match="one routed contact lead"):
        solid.solid_ribbon_plan(
            None, definition, definition.cable_groups[0], leg, branches[1:], shape
        )


def test_zero_body_contact_metadata_is_solid_only(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Preserve contact routing without granting body-free Split branches.
    """
    del addin_module
    metadata_module = import_module("cable_bundler.fusion.cable_solid_parts.metadata")
    route = _route(600, Vector3(0.0, 0.0, 0.0), Vector3(0.0, 0.0, 10.0))
    branch = {
        "route_id": str(route.cable_id),
        "label": route.cable_number,
        "route_curves_mm": metadata_module.route_metadata(route),
        "attachment_id": str(UUID(int=601)),
        "diameter_mm": 1.2,
        "pullback_diameter_mm": 0.9,
        "insulation_body_count": 0,
        "pullback_body_count": 0,
        "weld_body_count": 0,
    }
    solid = {"ribbon_body_type": "solid", "connection_branches": [branch]}
    assert len(metadata_module.connection_branches_from_metadata(solid)) == 1
    with pytest.raises(RuntimeError, match="branch metadata is malformed"):
        metadata_module.connection_branches_from_metadata(
            {"ribbon_body_type": "split", "connection_branches": [branch]}
        )


def test_solid_inherits_opposite_end_pins_by_width_order(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Match a numbered end by contact order without reseeding its saved pins.
    """
    del addin_module
    numbering = import_module("cable_bundler.fusion.ribbon_connections")
    frames = import_module("cable_bundler.fusion.route_preview_parts.frames")
    definition, _leg, branches, _shape = _fixture(valid_harness)
    source, target = definition.connections
    source_roots = tuple(
        replace(root, pin_number=str(4 - index))
        for index, root in enumerate(source.attachments, start=1)
    )
    target_roots = tuple(replace(root, pin_number=None) for root in target.attachments)
    definition = replace(
        definition,
        connections=(
            replace(source, attachment=source_roots[0], additional_attachments=source_roots[1:]),
            replace(target, attachment=target_roots[0], additional_attachments=target_roots[1:]),
        ),
    )
    profile = frames.ProfileFrame(
        Vector3(0.0, 0.0, 0.0),
        Vector3(0.0, 0.0, 1.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
    )
    starts = {item[0].attachment_id: item[1].curves[0].start for item in branches}
    monkeypatch.setitem(vars(numbering), "connection_profile_frames", lambda *_args: (profile,))
    monkeypatch.setitem(
        vars(numbering),
        "connection_attachment_frame",
        lambda _design, _connection, attachment, _guide, _cache: replace(
            profile, origin=starts[attachment.attachment_id]
        ),
    )
    monkeypatch.setitem(
        vars(numbering), "_guide_fit", lambda *_args: pytest.fail("unexpected guide numbering")
    )

    numbered = numbering.number_ribbon_connections(None, definition)

    assert tuple(root.pin_number for root in numbered.connections[0].attachments) == ("3", "2", "1")
    assert tuple(root.pin_number for root in numbered.connections[1].attachments) == ("3", "2", "1")


def test_solid_generation_records_contact_routes_without_branch_bodies(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep line, attachment, and Interface contact identities in generated output.
    """
    del addin_module
    solids = import_module("cable_bundler.fusion.cable_solids")
    solid = import_module("cable_bundler.fusion.solid_ribbon")
    definition, _leg, branches, _shape = _fixture(valid_harness)
    contact_ids = tuple(
        tuple(str(contact.contact_id) for contact in interface.contacts)
        for interface in definition.interfaces
    )
    attachment_ids = tuple(
        tuple(str(root.attachment_id) for root in connection.attachments)
        for connection in definition.connections
    )
    plan = solid.SolidRibbonPlan((), (), contact_ids, attachment_ids, ())
    attribute = SimpleNamespace(value=json.dumps({"diameter_mm": 1.2, "connection_branches": []}))
    component = SimpleNamespace(attributes=SimpleNamespace(itemByName=lambda *_args: attribute))
    monkeypatch.setitem(vars(solids), "route_in_component_space", lambda route, _transform: route)

    solids._record_solid_ribbon_contacts(component, branches, None, definition, plan)

    records = json.loads(attribute.value)["connection_branches"]
    assert len(records) == 6
    assert all(
        record["insulation_body_count"]
        == record["pullback_body_count"]
        == record["weld_body_count"]
        == 0
        for record in records
    )
    assert records[0]["ribbon_line_number"] == 1
    assert records[0]["interface_contact_id"] == contact_ids[0][0]
