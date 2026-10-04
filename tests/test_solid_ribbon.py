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
    InterfaceBehavior,
    InterfaceContact,
    InterfaceDefinition,
    InterfaceTarget,
    InterfaceTargetKind,
    RibbonBodyType,
)
from cable_bundler.routing import (
    CubicBezier,
    RibbonEndFit,
    RibbonFrame,
    RibbonShape,
    RoutePreview,
    Vector3,
)
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
    endpoints: tuple[tuple[float, float, float], tuple[float, float, float]] = (
        (-3.0, 0.0, 3.0),
        (-3.0, 0.0, 3.0),
    ),
) -> tuple[
    HarnessDefinition,
    CableGroupRouteLeg,
    tuple[tuple[CableGroupRouteLeg, RoutePreview], ...],
    RibbonShape,
]:
    """
    Connect three persistent lines to matching inline contact banks.
    """
    group = replace(
        definition.cable_groups[0],
        group_type=CableGroupType.RIBBON,
        ribbon_body_type=RibbonBodyType.SOLID,
        ribbon_lines=3,
    )
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


@pytest.mark.parametrize("contact_pitch", (3.0, 0.8))
def test_solid_plan_uses_contact_pitch_at_every_station(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
    contact_pitch: float,
) -> None:
    """
    Keep one contact-sized width and lobe size through the complete route.
    """
    del addin_module
    solid = import_module("cable_bundler.fusion.solid_ribbon")
    frames = import_module("cable_bundler.fusion.route_preview_parts.frames")
    endpoints = (-contact_pitch, 0.0, contact_pitch)
    definition, leg, branches, shape = _fixture(valid_harness, (endpoints, endpoints))
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
    expected_lobe = min(1.2, contact_pitch * 0.98)
    assert all(section.lobe_width_mm == pytest.approx(expected_lobe) for section in plan.sections)
    assert all(
        abs(section.centers[-1].x - section.centers[0].x) == pytest.approx(2 * contact_pitch)
        for section in plan.sections
    )
    assert tuple(point.x for point in plan.sections[0].centers) == endpoints
    assert tuple(point.x for point in plan.sections[-1].centers) == endpoints
    assert all(point.z == 0.0 for point in plan.sections[0].centers)
    assert all(point.z == 100.0 for point in plan.sections[-1].centers)
    assert len(plan.lanes) == 3
    assert len(plan.contact_ids[0]) == len(plan.contact_ids[1]) == 3
    assert plan.contact_ids[0][0] == str(UUID(int=300))
    assert plan.attachment_ids[0][0] == str(UUID(int=101))


def test_direct_plan_stops_at_fitted_end_gates(
    addin_module: _PaletteLifecycleModule,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Use only the two gate stations while retaining numbered contact identities.
    """
    del addin_module
    solid = import_module("cable_bundler.fusion.solid_ribbon")
    definition, leg, branches, shape = _fixture(valid_harness)
    group = replace(definition.cable_groups[0], interface_behavior=InterfaceBehavior.DIRECT)
    definition = replace(definition, cable_groups=(group,))
    start_fit = RibbonEndFit(
        tuple(lane[0] for lane in shape.lanes), (shape.frames[0].thickness,) * 3
    )
    end_fit = RibbonEndFit(
        tuple(lane[-1] for lane in shape.lanes), (shape.frames[-1].thickness,) * 3
    )
    shape = replace(shape, start_fit=start_fit, end_fit=end_fit)

    plan = solid.solid_ribbon_plan(None, definition, group, leg, branches, shape)

    assert plan.interface_behavior is InterfaceBehavior.DIRECT
    assert len(plan.sections) == len(shape.frames)
    assert tuple(point.z for point in plan.sections[0].centers) == (10.0,) * 3
    assert tuple(point.z for point in plan.sections[-1].centers) == (90.0,) * 3
    assert all(10.0 <= point.z <= 90.0 for lane in plan.lanes for point in lane)
    assert plan.contact_ids[0][0] == str(UUID(int=300))
    assert plan.attachment_ids[1][-1] == str(UUID(int=106))


def test_direct_plan_requires_both_end_gate_fits(
    addin_module: _PaletteLifecycleModule,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Refuse a gate-terminated body when either cable end could not be fitted.
    """
    del addin_module
    solid = import_module("cable_bundler.fusion.solid_ribbon")
    definition, leg, branches, shape = _fixture(valid_harness)
    group = replace(definition.cable_groups[0], interface_behavior=InterfaceBehavior.DIRECT)
    definition = replace(definition, cable_groups=(group,))
    with pytest.raises(ValueError, match="fitted cable-end gate"):
        solid.solid_ribbon_plan(None, definition, group, leg, branches, shape)


def test_solid_section_projects_oblique_lane_centers_onto_one_plane(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Keep a wide, tilted 19-lane station coplanar before sketching its contour.
    """
    del addin_module
    solid = import_module("cable_bundler.fusion.solid_ribbon")
    normal = Vector3(-0.2164505224, 0.9754181554, 0.0413351356)
    lane_direction = Vector3(0.7501628242, 0.0764321807, 0.6568210251)
    origin = Vector3(66.8490159818, 43.9711035568, 7.3029517285)
    centers = tuple(origin.translated(lane_direction, index * 1.4916855) for index in range(19))

    station = solid._section(centers, normal, lane_direction, 1.5)

    assert station.centers[0] == origin
    assert len(station.centers) == 19
    assert station.lobe_width_mm < 1.5
    assert (
        abs(station.width.x * normal.x + station.width.y * normal.y + station.width.z * normal.z)
        < 1e-10
    )
    for center in station.centers:
        displacement = Vector3(center.x - origin.x, center.y - origin.y, center.z - origin.z)
        assert (
            abs(displacement.x * normal.x + displacement.y * normal.y + displacement.z * normal.z)
            < 1e-9
        )


def test_solid_uniform_section_accepts_one_line(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Preserve the valid one-line ribbon case without a pitch denominator.
    """
    del addin_module
    solid = import_module("cable_bundler.fusion.solid_ribbon")
    station = solid.SolidRibbonSection(
        (Vector3(0.0, 0.0, 0.0),),
        Vector3(0.0, 0.0, 1.0),
        Vector3(1.0, 0.0, 0.0),
        1.2,
    )

    assert solid._uniform_sections((station,), 1.2) == (station,)


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


@pytest.mark.parametrize("profile_count", (1, 0, 2))
@pytest.mark.parametrize(
    ("centers", "heights", "lobe_width_mm"),
    (
        ((-3.0, 0.0, 3.0), (0.0, 0.0, 0.0), 1.2),
        ((-1.2, 0.0, 1.2), (0.0, 0.0, 0.0), 1.176),
        ((-0.8, 0.0, 0.8), (0.0, 0.0, 0.0), 0.784),
        ((-1.2, 0.0, 1.2), (0.0, 0.2, 0.0), 1.176),
    ),
)
def test_solid_section_reuses_contour_junctions_and_reports_profile_count(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    profile_count: int,
    centers: tuple[float, float, float],
    heights: tuple[float, float, float],
    lobe_width_mm: float,
) -> None:
    """
    Connect each lobe, web, and cap to the same explicit sketch points.
    """
    del addin_module
    builder = import_module("cable_bundler.fusion.cable_solid_parts.ribbon_builder")
    solid = import_module("cable_bundler.fusion.solid_ribbon")
    junctions = []
    arcs = []
    lines = []

    def add_junction(position: Vector3) -> SimpleNamespace:
        """
        Keep one distinct object for each contour endpoint.
        """
        junction = SimpleNamespace(position=position)
        junctions.append(junction)
        return junction

    def add_arc(start: object, middle: object, end: object) -> object:
        """
        Capture the exact endpoint objects passed to Fusion.
        """
        arcs.append((start, middle, end))
        return object()

    def add_line(start: object, end: object) -> object:
        """
        Capture each web's shared endpoint objects.
        """
        lines.append((start, end))
        return object()

    sketch = SimpleNamespace(
        sketchPoints=SimpleNamespace(add=add_junction),
        sketchCurves=SimpleNamespace(
            sketchArcs=SimpleNamespace(addByThreePoints=add_arc),
            sketchLines=SimpleNamespace(addByTwoPoints=add_line),
        ),
        profiles=SimpleNamespace(count=profile_count),
        modelToSketchSpace=lambda point: point,
    )
    plane = SimpleNamespace()
    component = SimpleNamespace(
        constructionPlanes=SimpleNamespace(
            createInput=lambda: SimpleNamespace(setByPlane=lambda _plane: True),
            add=lambda _input: plane,
        ),
        sketches=SimpleNamespace(add=lambda _plane: sketch),
    )
    monkeypatch.setitem(vars(builder), "_direct_guide_plane", lambda *_args: object())
    monkeypatch.setitem(vars(builder), "fusion_point", lambda point, _transform: point)
    station = solid.SolidRibbonSection(
        tuple(Vector3(position, height, 0.0) for position, height in zip(centers, heights)),
        Vector3(0.0, 0.0, 1.0),
        Vector3(1.0, 0.0, 0.0),
        lobe_width_mm,
    )

    if profile_count != 1:
        with pytest.raises(RuntimeError, match=f"profiles={profile_count}, lines=3"):
            builder._add_solid_section(component, station, 1.2, None)
    else:
        assert builder._add_solid_section(component, station, 1.2, None) == (sketch, plane)
    assert len(junctions) == 12
    assert len(arcs) == 8
    assert len(lines) == 4
    assert arcs[0][2] is lines[0][0]
    assert lines[0][1] is arcs[2][0]
    assert arcs[3][2] is lines[1][0]
    assert lines[1][1] is arcs[1][0]
    assert arcs[6][0] is arcs[0][0]
    assert arcs[6][2] is arcs[1][2]
    assert arcs[7][0] is arcs[4][2]
    assert arcs[7][2] is arcs[5][0]


@pytest.mark.parametrize(
    ("failed_index", "role"),
    ((0, "start contact lead"), (4, "main ribbon"), (8, "end contact lead")),
)
def test_solid_loft_identifies_the_failed_station(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    failed_index: int,
    role: str,
) -> None:
    """
    Keep section failures actionable without falling back to Split geometry.
    """
    del addin_module
    builder = import_module("cable_bundler.fusion.cable_solid_parts.ribbon_builder")
    solid = import_module("cable_bundler.fusion.solid_ribbon")
    stations = tuple(
        solid.SolidRibbonSection(
            (Vector3(float(index), 0.0, 0.0),),
            Vector3(0.0, 0.0, 1.0),
            Vector3(1.0, 0.0, 0.0),
            1.2,
        )
        for index in range(9)
    )
    plan = solid.SolidRibbonPlan(stations, (), ((), ()), ((), ()), ())
    body = SimpleNamespace(isSolid=True, volume=1.0)
    feature = SimpleNamespace(
        isValid=False,
        bodies=SimpleNamespace(count=1, item=lambda _index: body),
    )
    component = SimpleNamespace(
        bRepBodies=SimpleNamespace(count=1),
        features=SimpleNamespace(
            loftFeatures=SimpleNamespace(
                createInput=lambda _operation: SimpleNamespace(
                    loftSections=SimpleNamespace(add=lambda _profile: None), isSolid=False
                ),
                add=lambda _loft_input: feature,
            )
        ),
    )
    monkeypatch.setitem(
        vars(builder.adsk.fusion),
        "FeatureOperations",
        SimpleNamespace(NewBodyFeatureOperation=object()),
    )

    def add_section(
        _component: object,
        current_station: object,
        _diameter_mm: float,
        _transform: object,
    ) -> tuple[SimpleNamespace, SimpleNamespace]:
        """
        Fail at one selected loft station with its original route index.
        """
        if current_station.centers[0].x == failed_index:
            raise RuntimeError("profiles=0")
        sketch = SimpleNamespace(
            isValid=False,
            profiles=SimpleNamespace(item=lambda _index: object()),
        )
        return sketch, SimpleNamespace(isValid=False)

    monkeypatch.setitem(vars(builder), "_add_solid_section", add_section)

    with pytest.raises(
        RuntimeError, match=f"section {failed_index + 1}/9 \\({role}\\): profiles=0"
    ):
        builder._build_solid_loft(component, plan, 1.2, None)


def test_solid_loft_uses_one_feature_with_sparse_uniform_guides(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Use both contacts and a few route guides without segmented joins.
    """
    del addin_module
    builder = import_module("cable_bundler.fusion.cable_solid_parts.ribbon_builder")
    solid = import_module("cable_bundler.fusion.solid_ribbon")
    stations = tuple(
        solid.SolidRibbonSection(
            (Vector3(float(index), 0.0, 0.0),),
            Vector3(0.0, 0.0, 1.0),
            Vector3(1.0, 0.0, 0.0),
            1.2,
        )
        for index in range(40)
    )
    plan = solid.SolidRibbonPlan(stations, (), ((), ()), ((), ()), ())
    new_body = object()
    monkeypatch.setitem(
        vars(builder.adsk.fusion),
        "FeatureOperations",
        SimpleNamespace(NewBodyFeatureOperation=new_body),
    )
    operations: list[object] = []
    profiles: list[list[object]] = []
    features: list[SimpleNamespace] = []

    def create_input(operation: object) -> SimpleNamespace:
        """
        Record the operation and section order for the single loft.
        """
        operations.append(operation)
        section_profiles: list[object] = []
        profiles.append(section_profiles)
        return SimpleNamespace(
            loftSections=SimpleNamespace(add=section_profiles.append), isSolid=False
        )

    def add_loft(_loft_input: object) -> SimpleNamespace:
        """
        Return one positive-volume body for the loft.
        """
        body = SimpleNamespace(isSolid=True, volume=1.0)
        feature = SimpleNamespace(bodies=SimpleNamespace(count=1, item=lambda _index: body))
        features.append(feature)
        return feature

    component = SimpleNamespace(
        bRepBodies=SimpleNamespace(count=1),
        features=SimpleNamespace(
            loftFeatures=SimpleNamespace(createInput=create_input, add=add_loft)
        ),
    )

    def add_section(
        _component: object,
        station: object,
        _diameter_mm: float,
        _transform: object,
    ) -> tuple[SimpleNamespace, SimpleNamespace]:
        """
        Give each station a stable index marker.
        """
        marker = int(station.centers[0].x)
        sketch = SimpleNamespace(profiles=SimpleNamespace(item=lambda _index: marker))
        return sketch, SimpleNamespace()

    monkeypatch.setitem(vars(builder), "_add_solid_section", add_section)

    assert builder._build_solid_loft(component, plan, 1.2, None) is features[0]
    assert operations == [new_body]
    assert profiles == [[0, 4, 12, 20, 28, 35, 39]]
