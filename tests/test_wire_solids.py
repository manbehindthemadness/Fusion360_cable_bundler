"""
Mocked Fusion regressions for durable wire generation and replacement safety.
"""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Callable
from dataclasses import replace
from types import ModuleType, SimpleNamespace
from typing import Optional, Protocol, cast
from unittest.mock import MagicMock, Mock
from uuid import UUID

import pytest

from wire_bundler.domain import (
    HarnessDefinition,
    PathwayEndpoint,
    StandaloneEndDefinition,
    WireAppearanceReference,
    WireColor,
    WireDefinition,
    WireGroupDefinition,
    WireMaterialSettings,
    WireStripe,
)
from wire_bundler.routing import CubicBezier, RoutePreview, Vector3


class _SweepSegment(Protocol):
    """
    Describe construction ownership returned by the Fusion adapter.
    """

    route: RoutePreview
    source_route_index: int
    segment_index: int
    segment_count: int


class _SolidsModule(Protocol):
    """
    Describe the adapter boundary without importing Fusion during test collection.
    """

    generate_wire_solids: Callable[..., int]
    generate_wire_group_solids: Callable[..., int]
    generated_wire_bodies: Callable[..., tuple[object, ...]]
    generated_wire_group_bodies: Callable[..., tuple[object, ...]]
    clear_wire_solids: Callable[..., int]
    solve_route_centerlines: Callable[..., tuple[RoutePreview, ...]]
    solve_wire_group_centerlines: Callable[..., tuple[tuple[RoutePreview, ...], tuple[object, ...]]]
    build_wire_sweep: Callable[..., None]
    build_wire_group_solid: Callable[..., None]
    apply_wire_materials: Callable[..., int]
    apply_wire_group_materials: Callable[..., int]
    validate_harness: Callable[..., tuple[object, ...]]
    GENERATED_STRIPE_GROUP_ID: str
    _build_route_sweep: Callable[..., tuple[object, float, RoutePreview, object]]
    _orient_group_routes: Callable[
        [tuple[RoutePreview, ...]], tuple[tuple[RoutePreview, ...], tuple[Optional[int], ...]]
    ]
    _prepare_group_sweep_segments: Callable[
        [tuple[RoutePreview, ...]], tuple[tuple[_SweepSegment, ...], tuple[Optional[int], ...]]
    ]
    _reverse_route: Callable[[RoutePreview], RoutePreview]
    _shared_route_endpoints: Callable[..., tuple[tuple[Vector3, tuple[int, ...]], ...]]
    _replace_group_stripe_graphics: Callable[..., int]
    _replace_stripe_graphics: Callable[..., int]
    _route_from_metadata: Callable[..., Optional[RoutePreview]]
    _route_in_component_space: Callable[..., RoutePreview]
    _route_metadata: Callable[..., list[list[list[float]]]]
    _world_to_harness: Callable[..., object]
    _point: Callable[..., object]
    _wire_appearance: Callable[..., object]


@pytest.fixture
def solids(monkeypatch: pytest.MonkeyPatch) -> _SolidsModule:
    """
    Load the production adapter against isolated host modules.
    """
    core = ModuleType("adsk.core")
    fusion = ModuleType("adsk.fusion")
    adsk = ModuleType("adsk")
    vars(adsk).update(core=core, fusion=fusion)
    vars(core).update(
        Matrix3D=SimpleNamespace(create=lambda: Mock()),
        ObjectCollection=SimpleNamespace(create=lambda: Mock(add=Mock(return_value=True))),
        ValueInput=SimpleNamespace(createByReal=lambda number: number),
        Point3D=SimpleNamespace(
            create=lambda x, y, z: Mock(x=x, y=y, z=z, transformBy=Mock(return_value=True))
        ),
    )
    vars(fusion).update(
        Path=SimpleNamespace(create=Mock(side_effect=RuntimeError("Utils::getObjectPath"))),
        ChainedCurveOptions=SimpleNamespace(noChainedCurves=0),
        SplineDegrees=SimpleNamespace(SplineDegreeThree=3),
        FeatureOperations=SimpleNamespace(
            NewBodyFeatureOperation=0,
        ),
    )
    for name, value in (("adsk", adsk), ("adsk.core", core), ("adsk.fusion", fusion)):
        monkeypatch.setitem(sys.modules, name, value)
    module = importlib.import_module("wire_bundler.fusion.wire_solids")
    monkeypatch.setitem(vars(module), "adsk", adsk)
    return cast(_SolidsModule, cast(object, module))


def _route(wire: WireDefinition) -> RoutePreview:
    """
    Provide one curved cubic and one straight span with exact endpoint continuity.
    """
    a, b, c = Vector3(0, 0, 0), Vector3(2, 0, 2), Vector3(2, 0, 5)
    return RoutePreview(
        wire.wire_id,
        wire.wire_number,
        (a, b, c),
        (
            CubicBezier(a, Vector3(0, 0, 1), Vector3(2, 0, 1), b),
            CubicBezier(b, Vector3(2, 0, 3), Vector3(2, 0, 4), c),
        ),
    )


def _straight_route(identity: int, label: str, start: Vector3, end: Vector3) -> RoutePreview:
    """
    Provide one straight route for junction-topology regressions.
    """
    delta = Vector3(
        (end.x - start.x) / 3.0,
        (end.y - start.y) / 3.0,
        (end.z - start.z) / 3.0,
    )
    curve = CubicBezier(
        start,
        Vector3(start.x + delta.x, start.y + delta.y, start.z + delta.z),
        Vector3(end.x - delta.x, end.y - delta.y, end.z - delta.z),
        end,
    )
    return RoutePreview(UUID(int=identity), label, (start, end), (curve,))


def _pass_through_route(
    identity: int,
    label: str,
    start: Vector3,
    junction: Vector3,
    end: Vector3,
) -> RoutePreview:
    """
    Provide one logical route whose exact curves pass through a junction.
    """
    left = _straight_route(identity, label, start, junction).curves[0]
    right = _straight_route(identity, label, junction, end).curves[0]
    return RoutePreview(UUID(int=identity), label, (start, junction, end), (left, right))


def _terminal_lead(identity: int, label: str, junction: Vector3) -> RoutePreview:
    """
    Provide one curved lead with a terminal tangent parallel to the pass-through route.
    """
    start = Vector3(junction.x - 5.0, junction.y - 5.0, junction.z)
    curve = CubicBezier(
        start,
        Vector3(start.x, junction.y - 3.0, junction.z),
        Vector3(junction.x - 2.0, junction.y, junction.z),
        junction,
    )
    return RoutePreview(UUID(int=identity), label, (start, junction), (curve,))


@pytest.mark.parametrize("fail_second", [False, True])
def test_builds_all_replacements_before_deleting_old_output(
    solids: _SolidsModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
    fail_second: bool,
) -> None:
    """
    Preserve original output until every sweep succeeds and clean all staging on failure.
    """
    extra_ends = tuple(
        replace(connection, connection_id=UUID(int=910 + index))
        for index, connection in enumerate(valid_harness.connections)
    )
    definition = replace(
        valid_harness,
        connections=(*valid_harness.connections, *extra_ends),
        wires=(
            valid_harness.wires[0],
            replace(
                valid_harness.wires[0],
                wire_id=UUID(int=900),
                wire_number="002",
                start_connection_id=extra_ends[0].connection_id,
                end_connection_id=extra_ends[1].connection_id,
            ),
        ),
    )
    old = Mock(deleteMe=Mock(return_value=True))
    unrelated = Mock()
    unrelated.component.attributes.itemByName.return_value = None
    created = [Mock(isValid=True, deleteMe=Mock(return_value=True)) for _ in range(2)]
    harness = Mock(occurrences=MagicMock())
    harness.occurrences.__iter__.return_value = iter((old, unrelated))
    harness.occurrences.addNewComponent.side_effect = created
    design = SimpleNamespace(rootComponent=harness)
    monkeypatch.setattr(
        solids,
        "solve_route_centerlines",
        lambda *_args: tuple(_route(wire) for wire in definition.wires),
    )
    builds: list[UUID] = []

    def build(_component: object, wire: WireDefinition, *_args: object) -> None:
        """
        Simulate the kernel succeeding or rejecting the last wire before replacement.
        """
        old.deleteMe.assert_not_called()
        builds.append(wire.wire_id)
        if fail_second and len(builds) == 2:
            raise RuntimeError("sweep rejected")

    monkeypatch.setattr(solids, "build_wire_sweep", build)
    if fail_second:
        with pytest.raises(RuntimeError, match="Wire 002.*sweep rejected"):
            solids.generate_wire_solids(design, harness, definition, True)
        old.deleteMe.assert_not_called()
        for occurrence in created:
            occurrence.deleteMe.assert_called_once()
    else:
        assert solids.generate_wire_solids(design, harness, definition, True) == 2
        old.deleteMe.assert_called_once()
        for occurrence in created:
            occurrence.deleteMe.assert_not_called()
    unrelated.deleteMe.assert_not_called()
    assert builds == [wire.wire_id for wire in definition.wires]


def test_requires_confirmation_before_replacing_output(
    solids: _SolidsModule,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Reject an unconfirmed rebuild before invoking the solver or creating geometry.
    """
    harness = Mock(occurrences=MagicMock())
    harness.occurrences.__iter__.return_value = iter((Mock(),))
    with pytest.raises(ValueError, match="confirm rebuilding"):
        solids.generate_wire_solids(object(), harness, valid_harness)
    harness.occurrences.addNewComponent.assert_not_called()


@pytest.mark.parametrize("fail_build", [False, True])
def test_group_generation_stages_components_before_replacing_all_managed_output(
    solids: _SolidsModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
    fail_build: bool,
) -> None:
    """
    Preserve old legacy output until every grouped component has been built.
    """
    wire = valid_harness.wires[0]
    group = WireGroupDefinition(
        UUID(int=850),
        (wire.start_connection_id, wire.end_connection_id),
        1.8,
    )
    pathway_id = valid_harness.pathways[0].pathway_id
    definition = replace(
        valid_harness,
        wires=(),
        standalone_ends=(
            StandaloneEndDefinition(
                wire.start_connection_id,
                pathway_id,
                PathwayEndpoint.START,
            ),
            StandaloneEndDefinition(
                wire.end_connection_id,
                pathway_id,
                PathwayEndpoint.END,
            ),
        ),
        wire_groups=(group,),
    )
    route = _route(wire)
    route = replace(route, wire_id=UUID(int=851), wire_number="Group 1 Leg 1")
    leg = SimpleNamespace(route_id=route.wire_id, wire_group_id=group.wire_group_id)
    old_attribute = object()
    old_component = SimpleNamespace(
        attributes=SimpleNamespace(
            itemByName=lambda _group, name: old_attribute if name == "generated_wire" else None
        )
    )
    old = Mock(component=old_component, deleteMe=Mock(return_value=True))
    created = Mock(isValid=True, deleteMe=Mock(return_value=True))
    harness = Mock(occurrences=MagicMock())
    harness.occurrences.__iter__.return_value = iter((old,))
    harness.occurrences.addNewComponent.return_value = created
    design = SimpleNamespace(rootComponent=harness)
    monkeypatch.setattr(
        solids,
        "solve_wire_group_centerlines",
        lambda *_args: ((route,), (leg,)),
    )
    builds: list[UUID] = []

    def build(_component: object, built_group: WireGroupDefinition, *_args: object) -> None:
        """
        Record staged ownership and optionally reproduce a Fusion failure.
        """
        old.deleteMe.assert_not_called()
        builds.append(built_group.wire_group_id)
        if fail_build:
            raise RuntimeError("sweep rejected")

    monkeypatch.setattr(solids, "build_wire_group_solid", build)
    if fail_build:
        with pytest.raises(RuntimeError, match="Wire Group 1.*sweep rejected"):
            solids.generate_wire_group_solids(design, harness, definition, True)
        old.deleteMe.assert_not_called()
        created.deleteMe.assert_called_once_with()
    else:
        assert solids.generate_wire_group_solids(design, harness, definition, True) == 1
        old.deleteMe.assert_called_once_with()
        created.deleteMe.assert_not_called()
    assert builds == [group.wire_group_id]


def test_builds_each_leg_from_one_shared_junction_profile(
    solids: _SolidsModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Reuse one profile without changing metadata route direction or body ownership.
    """
    wire = valid_harness.wires[0]
    group = WireGroupDefinition(
        UUID(int=860),
        (wire.start_connection_id, wire.end_connection_id),
        2.0,
    )
    junction = Vector3(0.0, 0.0, 0.0)
    routes = (
        _pass_through_route(
            861,
            "Group 1 Leg 1",
            Vector3(-10.0, 0.0, 0.0),
            junction,
            Vector3(10.0, 0.0, 0.0),
        ),
        _terminal_lead(862, "Group 1 Leg 2", junction),
    )
    bodies = [SimpleNamespace(name="", appearance=None) for _index in range(3)]
    shared_profile = object()
    supplied_profiles: list[object] = []

    def build_route(*args: object) -> tuple[object, float, RoutePreview, object]:
        """
        Record shared-profile reuse while returning one body per sweep segment.
        """
        route = cast(RoutePreview, args[1])
        profile = args[7]
        supplied_profiles.append(profile)
        sweep_index = len(supplied_profiles) - 1
        return bodies[sweep_index], (10.0, 10.0, 5.0)[sweep_index], route, shared_profile

    attributes = Mock()
    attributes.add.return_value = object()
    component = SimpleNamespace(
        bRepBodies=SimpleNamespace(count=3),
        attributes=attributes,
        name="",
    )
    monkeypatch.setattr(solids, "_route_in_component_space", lambda route, _transform: route)
    monkeypatch.setattr(solids, "_build_route_sweep", Mock(side_effect=build_route))
    appearance = object()
    monkeypatch.setattr(
        solids, "_wire_appearance", lambda _design, _color, _reference=None: appearance
    )
    stripe_refresh = Mock(return_value=0)
    monkeypatch.setattr(solids, "_replace_group_stripe_graphics", stripe_refresh)
    materials = valid_harness.wire_group_materials(group)

    solids.build_wire_group_solid(
        component,
        group,
        0,
        routes,
        object(),
        valid_harness.harness_id,
        materials,
        object(),
    )

    assert supplied_profiles == [None, shared_profile, shared_profile]
    assert component.name == "Wire Group 1_25.00mm"
    assert [body.name for body in bodies] == [
        "Wire Group 1 Leg 1 Segment 1",
        "Wire Group 1 Leg 1 Segment 2",
        "Wire Group 1 Leg 2",
    ]
    assert all(body.appearance is appearance for body in bodies)
    metadata = json.loads(attributes.add.call_args.args[2])
    assert metadata["wire_group_id"] == str(group.wire_group_id)
    assert metadata["length_mm"] == 25.0
    assert [leg["route_id"] for leg in metadata["route_legs"]] == [
        str(route.wire_id) for route in routes
    ]
    assert [leg["length_mm"] for leg in metadata["route_legs"]] == [20.0, 5.0]


def test_splits_pass_through_route_without_changing_exact_cubics(
    solids: _SolidsModule,
) -> None:
    """
    Turn an interior terminal attachment into three junction-bounded sweeps.
    """
    junction = Vector3(0.0, 0.0, 0.0)
    pass_through = _pass_through_route(
        867,
        "Pass Through",
        Vector3(-10.0, 0.0, 0.0),
        junction,
        Vector3(10.0, 0.0, 0.0),
    )
    lead = _terminal_lead(868, "Internal Lead", junction)

    segments, start_junctions = solids._prepare_group_sweep_segments((pass_through, lead))

    assert start_junctions == (0, 0, 0)
    assert [segment.source_route_index for segment in segments] == [0, 0, 1]
    assert [segment.segment_index for segment in segments] == [0, 1, 0]
    assert [segment.segment_count for segment in segments] == [2, 2, 1]
    assert all(segment.route.curves[0].start == junction for segment in segments)
    assert segments[0].route.curves[0] == CubicBezier(
        pass_through.curves[0].end,
        pass_through.curves[0].control_b,
        pass_through.curves[0].control_a,
        pass_through.curves[0].start,
    )
    assert segments[1].route.curves == (pass_through.curves[1],)
    assert pass_through.curves[0].end == junction


def test_splits_one_route_at_multiple_internal_terminal_leads(solids: _SolidsModule) -> None:
    """
    Preserve a connected tree when several internal ends attach to one logical leg.
    """
    start = Vector3(-15.0, 0.0, 0.0)
    first_junction = Vector3(-5.0, 0.0, 0.0)
    second_junction = Vector3(5.0, 0.0, 0.0)
    end = Vector3(15.0, 0.0, 0.0)
    spans = (
        _straight_route(869, "Pass Through", start, first_junction).curves[0],
        _straight_route(869, "Pass Through", first_junction, second_junction).curves[0],
        _straight_route(869, "Pass Through", second_junction, end).curves[0],
    )
    pass_through = RoutePreview(
        UUID(int=869),
        "Pass Through",
        (start, first_junction, second_junction, end),
        spans,
    )
    routes = (
        pass_through,
        _terminal_lead(870, "First Lead", first_junction),
        _terminal_lead(871, "Second Lead", second_junction),
    )

    segments, start_junctions = solids._prepare_group_sweep_segments(routes)

    assert [segment.source_route_index for segment in segments] == [0, 0, 0, 1, 2]
    assert start_junctions == (0, 0, 1, 0, 1)
    assert all(start_junction is not None for start_junction in start_junctions)


def test_detects_shared_route_endpoints_with_tolerance(solids: _SolidsModule) -> None:
    """
    Deduplicate one physical junction without treating free ends as hubs.
    """
    hub = Vector3(1.0, 2.0, 3.0)
    routes = (
        _straight_route(871, "Left", Vector3(-5.0, 2.0, 3.0), hub),
        _straight_route(872, "Right", Vector3(7.0, 2.0, 3.0), hub),
        _straight_route(
            873,
            "Branch",
            Vector3(1.0, -4.0, 3.0),
            Vector3(1.0 + 5e-7, 2.0, 3.0),
        ),
    )

    assert solids._shared_route_endpoints(routes) == ((hub, (0, 1, 2)),)


def test_orients_construction_routes_from_a_stable_shared_profile_root(
    solids: _SolidsModule,
) -> None:
    """
    Reverse exact cubics without changing persistent route identity or originals.
    """
    junction = Vector3(0.0, 0.0, 0.0)
    routes = tuple(
        _straight_route(
            880 + index,
            f"Leg {index + 1}",
            Vector3(float(-10 - index * 5), 0.0, 0.0),
            junction,
        )
        for index in range(3)
    )
    oriented, start_junctions = solids._orient_group_routes(routes)

    assert start_junctions == (0, 0, 0)
    assert all(route.curves[0].start == junction for route in oriented)
    assert oriented[0].wire_id == routes[0].wire_id
    assert oriented[0].curves[0].control_a == routes[0].curves[-1].control_b
    assert routes[0].curves[-1].end == junction


def test_rejects_group_routes_without_one_connected_junction_tree(solids: _SolidsModule) -> None:
    """
    Refuse unrelated visual bodies that cannot share a profile topology.
    """
    routes = (
        _straight_route(890, "Left", Vector3(0.0, 0.0, 0.0), Vector3(5.0, 0.0, 0.0)),
        _straight_route(891, "Right", Vector3(10.0, 0.0, 0.0), Vector3(15.0, 0.0, 0.0)),
    )

    with pytest.raises(RuntimeError, match="do not form one connected tree"):
        solids._orient_group_routes(routes)


def test_rejects_cyclic_group_sweep_segments(solids: _SolidsModule) -> None:
    """
    Refuse two distinct sweep segments joining the same pair of junctions.
    """
    start = Vector3(0.0, 0.0, 0.0)
    end = Vector3(10.0, 0.0, 0.0)
    routes = (
        _straight_route(895, "First", start, end),
        _straight_route(896, "Second", start, end),
    )

    with pytest.raises(RuntimeError, match="contain a cycle"):
        solids._prepare_group_sweep_segments(routes)


def test_rejects_junction_routes_without_one_profile_plane(
    solids: _SolidsModule,
) -> None:
    """
    Reject endpoints whose terminal tangents cannot reuse one circular profile.
    """
    junction = Vector3(0.0, 0.0, 0.0)
    routes = (
        _straight_route(900, "Horizontal", Vector3(-10.0, 0.0, 0.0), junction),
        _straight_route(901, "Vertical", Vector3(0.0, -10.0, 0.0), junction),
    )

    with pytest.raises(RuntimeError, match="do not share one sweep profile plane"):
        solids._orient_group_routes(routes)


def test_clears_only_marked_generated_wire_components(solids: _SolidsModule) -> None:
    """
    Delete generated direct children while preserving unrelated harness content.
    """
    generated = [Mock(deleteMe=Mock(return_value=True)) for _ in range(2)]
    unrelated = Mock()
    harness = Mock(occurrences=MagicMock())
    harness.occurrences.__iter__.return_value = iter((*generated, unrelated))
    for occurrence in generated:
        occurrence.component.attributes.itemByName.return_value = object()
    unrelated.component.attributes.itemByName.return_value = None

    assert solids.clear_wire_solids(harness) == 2

    for occurrence in generated:
        occurrence.deleteMe.assert_called_once()
    unrelated.deleteMe.assert_not_called()


def test_clear_solids_raises_when_fusion_rejects_deletion(solids: _SolidsModule) -> None:
    """
    Fail the native transaction when Fusion cannot delete marked output.
    """
    generated = Mock(deleteMe=Mock(return_value=False))
    generated.component.attributes.itemByName.return_value = object()
    harness = Mock(occurrences=MagicMock())
    harness.occurrences.__iter__.return_value = iter((generated,))

    with pytest.raises(RuntimeError, match="could not delete"):
        solids.clear_wire_solids(harness)


@pytest.mark.parametrize("sweep_failure", [False, True])
def test_creates_exact_curves_diameter_and_identity(
    solids: _SolidsModule,
    valid_harness: HarnessDefinition,
    sweep_failure: bool,
) -> None:
    """
    Build cubic control geometry and a circular profile using host centimeters, then retain UUIDs.
    """
    component = Mock()
    centerline = Mock(modelToSketchSpace=lambda value: value)
    section = Mock(modelToSketchSpace=lambda value: value)
    component.sketches.add.side_effect = (centerline, section)
    centerline.sketchCurves.sketchControlPointSplines.add.return_value = Mock(length=1.25)
    centerline.sketchCurves.sketchLines.addByTwoPoints.return_value = Mock(length=0.3)
    section.profiles.count = 1
    sweep = component.features.sweepFeatures.add.return_value
    sweep.bodies.count = 1
    sweep.bodies.item.return_value = Mock(isSolid=True, volume=0.025)
    path = Mock()
    component.features.createPath.return_value = path
    wire = valid_harness.wires[0]
    if sweep_failure:
        component.features.sweepFeatures.add.side_effect = RuntimeError("ASM_SELF_INTER")
        with pytest.raises(
            RuntimeError,
            match=r"create solid sweep: ASM_SELF_INTER; route diagnostic: "
            r"tightest sampled bend radius .* wire radius 0\.750 mm",
        ):
            solids.build_wire_sweep(
                component, wire, _route(wire), 1.5, Mock(), valid_harness.harness_id
            )
        component.features.pipeFeatures.add.assert_not_called()
        return
    solids.build_wire_sweep(component, wire, _route(wire), 1.5, Mock(), valid_harness.harness_id)
    controls, degree = centerline.sketchCurves.sketchControlPointSplines.add.call_args.args
    assert degree == 3
    assert [(point.x, point.y, point.z) for point in controls] == [
        (0, 0, 0),
        (0, 0, 0.1),
        (0.2, 0, 0.1),
        (0.2, 0, 0.2),
    ]
    curves, chain = component.features.createPath.call_args.args
    assert chain is False
    vars(sys.modules["adsk.fusion"])["Path"].create.assert_not_called()
    component.constructionPlanes.createInput.return_value.setByDistanceOnPath.assert_called_once_with(
        curves.item(0), 0
    )
    center, radius = section.sketchCurves.sketchCircles.addByCenterRadius.call_args.args
    assert (center.x, center.y, center.z) == (0, 0, 0)
    assert radius == 0.075
    component.features.pipeFeatures.add.assert_not_called()
    assert sweep.name == "Wire Sweep"
    assert sweep.bodies.item.return_value.name == "001_15.50mm"
    assert component.name == "001_15.50mm"
    assert not centerline.isLightBulbOn and not section.isLightBulbOn
    assert not component.constructionPlanes.add.return_value.isLightBulbOn
    metadata = json.loads(component.attributes.add.call_args.args[2])
    assert metadata["wire_id"] == str(wire.wire_id)
    assert metadata["length_mm"] == pytest.approx(15.5)


def test_transforms_points_into_harness_placement(solids: _SolidsModule) -> None:
    """
    Invert the unique placement and apply that matrix after unit conversion.
    """
    transform = Mock(invert=Mock(return_value=True))
    placement = Mock()
    placement.transform2.copy.return_value = transform
    design = Mock()
    design.rootComponent.allOccurrencesByComponent.return_value = Mock(
        count=1, item=lambda _index: placement
    )
    # noinspection PyProtectedMember
    matrix = solids._world_to_harness(design, object())
    # noinspection PyProtectedMember
    point = cast(Mock, solids._point(Vector3(10, 20, 30), matrix))
    assert (point.x, point.y, point.z) == (1, 2, 3)
    point.transformBy.assert_called_once_with(transform)
    transform.invert.assert_called_once()


def test_generated_stripes_are_owned_by_wire_component(
    solids: _SolidsModule,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Replace stripe meshes inside the generated component in component-local units.
    """
    wire = valid_harness.wires[0]
    route = _route(wire)
    old_child = Mock(deleteMe=Mock(return_value=True))
    old_group = SimpleNamespace(
        id=solids.GENERATED_STRIPE_GROUP_ID,
        name="Wire 001 Solid Stripes",
        count=1,
        item=lambda _index: old_child,
        deleteMe=Mock(return_value=True),
    )
    meshes: list[SimpleNamespace] = []
    coordinate_calls: list[list[float]] = []

    def add_mesh(*_args: object) -> SimpleNamespace:
        """
        Return one assignable solid-owned stripe mesh.
        """
        mesh = SimpleNamespace()
        meshes.append(mesh)
        return mesh

    new_group = SimpleNamespace(id="", name="", count=0, addMesh=add_mesh)
    groups = SimpleNamespace(count=1, item=lambda _index: old_group, add=lambda: new_group)
    component = SimpleNamespace(customGraphicsGroups=groups)
    core = sys.modules["adsk.core"]
    fusion = sys.modules["adsk.fusion"]
    core.Color = SimpleNamespace(create=lambda *channels: channels)  # type: ignore[attr-defined]
    fusion.CustomGraphicsCoordinates = SimpleNamespace(  # type: ignore[attr-defined]
        create=lambda values: coordinate_calls.append(values) or object()
    )
    fusion.CustomGraphicsSolidColorEffect = SimpleNamespace(  # type: ignore[attr-defined]
        create=lambda color: color
    )
    fusion.CustomGraphicsCullModes = SimpleNamespace(  # type: ignore[attr-defined]
        CustomGraphicsCullNone="none"
    )
    stripe = WireStripe(WireColor("White", 245, 245, 245), 0.3)

    assert solids._replace_stripe_graphics(component, route, (stripe,), 0.75) == 1

    old_child.deleteMe.assert_called_once()
    old_group.deleteMe.assert_called_once()
    assert new_group.id.endswith(str(wire.wire_id))
    assert new_group.name == "Wire 001 Solid Stripes"
    assert coordinate_calls
    assert meshes[0].name == "Wire 001 Stripe 1"
    assert meshes[0].color == (245, 245, 245, 255)
    assert meshes[0].cullMode == "none"


def test_generated_route_metadata_round_trips_component_local_curves(
    solids: _SolidsModule,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Retain the exact solid path so later material edits cannot follow a stale preview.
    """
    wire = valid_harness.wires[0]
    route = _route(wire)
    local_route = solids._route_in_component_space(route, Mock())
    metadata = {"route_curves_mm": solids._route_metadata(local_route)}

    restored = solids._route_from_metadata(wire, metadata)

    assert restored == local_route


def test_creates_and_reuses_document_insulation_appearance(
    solids: _SolidsModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Copy Fusion's released generic appearance once and update its opaque color.
    """
    color = WireColor("Blue", 35, 94, 190)
    color_property = SimpleNamespace(value=None)
    created = SimpleNamespace(
        appearanceProperties=SimpleNamespace(itemById=lambda identity: color_property)
    )
    appearances = Mock()
    appearances.itemByName.side_effect = (None, created)
    appearances.addByCopy.return_value = created
    generic = object()
    library = SimpleNamespace(
        appearances=SimpleNamespace(
            itemById=lambda identity: generic if identity == "Prism-129" else None
        )
    )
    application = SimpleNamespace(
        materialLibraries=SimpleNamespace(
            itemById=lambda identity: (
                library if identity == "BA5EE55E-9982-449B-9D66-9F036540E140" else None
            )
        )
    )
    core = sys.modules["adsk.core"]
    core.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    core.Color = SimpleNamespace(create=lambda *channels: channels)  # type: ignore[attr-defined]
    design = SimpleNamespace(appearances=appearances)

    assert solids._wire_appearance(design, color) is created
    assert color_property.value == (35, 94, 190, 255)
    appearances.addByCopy.assert_called_once_with(generic, "Wire Bundler Insulation #235EBE")
    assert solids._wire_appearance(design, color) is created
    appearances.addByCopy.assert_called_once()


def test_copies_selected_fusion_library_appearance(
    solids: _SolidsModule,
) -> None:
    """
    Preserve a user's library appearance without replacing it with a flat color.
    """
    reference = WireAppearanceReference(
        "custom-library", "My Appearances", "rubber-blue", "Rubber - Blue"
    )
    source = object()
    library = SimpleNamespace(
        appearances=SimpleNamespace(
            itemById=lambda identity: source if identity == "rubber-blue" else None
        )
    )
    application = SimpleNamespace(
        materialLibraries=SimpleNamespace(
            itemById=lambda identity: library if identity == "custom-library" else None
        )
    )
    core = sys.modules["adsk.core"]
    core.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    created = object()
    appearances = Mock(itemByName=Mock(return_value=None), addByCopy=Mock(return_value=created))
    design = SimpleNamespace(appearances=appearances)

    result = solids._wire_appearance(design, WireColor("Blue", 35, 94, 190), reference)

    assert result is created
    appearances.addByCopy.assert_called_once()
    assert appearances.addByCopy.call_args.args[0] is source
    assert "Rubber - Blue" in appearances.addByCopy.call_args.args[1]


def test_applies_saved_materials_to_existing_generated_body(
    solids: _SolidsModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Recolor generated output and refresh its resolved material metadata in place.
    """
    blue = WireColor("Blue", 35, 94, 190)
    stripe = WireStripe(WireColor("White", 245, 245, 245), 0.3)
    definition = replace(
        valid_harness,
        material_defaults=WireMaterialSettings(
            insulation_material="ETFE",
            main_color=blue,
            stripes=(stripe,),
            part_number="WB-001",
        ),
    )
    route = _route(definition.wires[0])
    metadata = {
        "wire_id": str(definition.wires[0].wire_id),
        "length_mm": 42.0,
        "route_curves_mm": solids._route_metadata(route),
    }
    attribute = SimpleNamespace(value=json.dumps(metadata))
    body = SimpleNamespace(appearance=None)
    bodies = SimpleNamespace(count=1, item=lambda _index: body)
    component = SimpleNamespace(
        attributes=SimpleNamespace(itemByName=lambda *_args: attribute),
        bRepBodies=bodies,
    )
    occurrence = SimpleNamespace(component=component)
    harness = SimpleNamespace(occurrences=(occurrence,))
    appearance = object()
    monkeypatch.setattr(
        solids, "_wire_appearance", lambda _design, _color, _reference=None: appearance
    )
    stripe_updates: list[tuple[object, RoutePreview, tuple[WireStripe, ...], float]] = []

    def replace_stripes(
        owner: object,
        saved_route: RoutePreview,
        stripes: tuple[WireStripe, ...],
        radius: float,
    ) -> int:
        """
        Record the component-local stripe refresh performed during material Apply.
        """
        stripe_updates.append((owner, saved_route, stripes, radius))
        return len(stripes)

    monkeypatch.setattr(
        solids,
        "_replace_stripe_graphics",
        replace_stripes,
    )

    assert solids.apply_wire_materials(object(), harness, definition) == 1
    assert body.appearance is appearance
    expected_radius = definition.profiles[0].diameter_mm / 2.0
    assert stripe_updates == [(component, route, (stripe,), expected_radius)]
    stored = json.loads(attribute.value)
    assert stored["length_mm"] == 42.0
    assert stored["main_color"] == "#235EBE"
    assert stored["insulation_material"] == "ETFE"
    assert stored["part_number"] == "WB-001"


def test_applies_group_materials_and_rebuilds_stripes_from_saved_legs(
    solids: _SolidsModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Reuse exact local leg curves and color every grouped solid body.
    """
    wire = valid_harness.wires[0]
    group = WireGroupDefinition(
        UUID(int=865),
        (wire.start_connection_id, wire.end_connection_id),
        1.6,
    )
    definition = replace(valid_harness, wire_groups=(group,))
    route = replace(_route(wire), wire_id=UUID(int=866), wire_number="Group 1 Leg 1")
    attribute = SimpleNamespace(
        value=json.dumps(
            {
                "wire_group_id": str(group.wire_group_id),
                "route_legs": [
                    {
                        "route_id": str(route.wire_id),
                        "label": route.wire_number,
                        "route_curves_mm": solids._route_metadata(route),
                    }
                ],
            }
        )
    )
    bodies = (SimpleNamespace(appearance=None), SimpleNamespace(appearance=None))
    component = SimpleNamespace(
        attributes=SimpleNamespace(itemByName=lambda *_args: attribute),
        bRepBodies=SimpleNamespace(count=2, item=lambda index: bodies[index]),
    )
    harness = SimpleNamespace(occurrences=(SimpleNamespace(component=component),))
    appearance = object()
    monkeypatch.setattr(
        solids, "_wire_appearance", lambda _design, _color, _reference=None: appearance
    )
    stripe_refresh = Mock(return_value=0)
    monkeypatch.setattr(solids, "_replace_group_stripe_graphics", stripe_refresh)

    assert solids.apply_wire_group_materials(object(), harness, definition) == 1

    assert all(body.appearance is appearance for body in bodies)
    assert stripe_refresh.call_args.args[1] == (route,)
    assert stripe_refresh.call_args.args[4] == group.wire_group_id
    stored = json.loads(attribute.value)
    assert stored["main_color"] == definition.material_defaults.main_color.hex_rgb


def test_resolves_generated_bodies_by_persistent_wire_identity(
    solids: _SolidsModule,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Return every body owned by the requested generated wire components.
    """
    selected_wire = valid_harness.wires[0]
    selected_body = object()
    other_body = object()

    def occurrence(
        wire_id: UUID,
        body: object,
    ) -> tuple[SimpleNamespace, SimpleNamespace]:
        """
        Build one marked generated occurrence with identity metadata.
        """
        attribute = SimpleNamespace(value=json.dumps({"wire_id": str(wire_id)}))
        component = SimpleNamespace(
            attributes=SimpleNamespace(itemByName=lambda *_args: attribute),
        )
        root_occurrence = SimpleNamespace(
            bRepBodies=SimpleNamespace(count=1, item=lambda _index: body)
        )
        return SimpleNamespace(component=component), root_occurrence

    other_wire_id = UUID(int=999)
    selected_native, selected_root = occurrence(selected_wire.wire_id, selected_body)
    other_native, other_root = occurrence(other_wire_id, other_body)
    harness = SimpleNamespace(
        occurrences=(selected_native, other_native),
    )
    root_occurrences = {
        id(selected_native.component): selected_root,
        id(other_native.component): other_root,
    }
    root = SimpleNamespace(
        allOccurrencesByComponent=lambda component: SimpleNamespace(
            count=1,
            item=lambda _index: root_occurrences[id(component)],
        )
    )

    assert solids.generated_wire_bodies(root, harness, (selected_wire.wire_id,)) == (selected_body,)


def test_resolves_generated_bodies_by_persistent_wire_group_identity(
    solids: _SolidsModule,
) -> None:
    """
    Return every visual body owned by a requested generated wire group.
    """
    selected_group_id = UUID(int=870)
    selected_bodies = (object(), object(), object())
    attribute = SimpleNamespace(value=json.dumps({"wire_group_id": str(selected_group_id)}))
    component = SimpleNamespace(attributes=SimpleNamespace(itemByName=lambda *_args: attribute))
    harness = SimpleNamespace(occurrences=(SimpleNamespace(component=component),))
    root_occurrence = SimpleNamespace(
        bRepBodies=SimpleNamespace(count=3, item=lambda index: selected_bodies[index])
    )
    root = SimpleNamespace(
        allOccurrencesByComponent=lambda _component: SimpleNamespace(
            count=1,
            item=lambda _index: root_occurrence,
        )
    )

    assert (
        solids.generated_wire_group_bodies(root, harness, (selected_group_id,)) == selected_bodies
    )
