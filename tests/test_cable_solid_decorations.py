"""
Regression tests for decoration continuity across generated solid segments.
"""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Callable
from dataclasses import replace
from types import ModuleType, SimpleNamespace
from typing import Any, Iterator, Optional, Protocol, cast
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.domain import (
    AttachmentTargetKind,
    CableColor,
    CableEndAttachment,
    CablePullbackSettings,
    CableStripe,
    CableVisualOverrides,
    HarnessDefinition,
    PullbackMode,
    StripePattern,
)
from cable_bundler.routing import CubicBezier, RoutePreview, StripeMeshResult, Vector3
from cable_bundler.routing.geometry import difference, dot, unit


class _SweepSegment(Protocol):
    """
    Describe one private junction-bounded solid construction segment.
    """

    route: RoutePreview
    source_route_index: int
    segment_index: int
    segment_count: int


class _PullbackSplit(Protocol):
    """
    Describe the two exact route spans produced for finalized pullback geometry.
    """

    insulation: Optional[RoutePreview]
    pullback: Optional[RoutePreview]
    pullback_length_mm: float


class _EndpointPullbackSplit(Protocol):
    """
    Describe target-facing pullback spans at both ends of a main route.
    """

    insulation: Optional[RoutePreview]
    start_pullback: Optional[RoutePreview]
    end_pullback: Optional[RoutePreview]


class _VisibilityState(Protocol):
    """
    Describe captured generated body and stripe visibility.
    """

    occurrences: tuple[tuple[object, bool], ...]
    stripe_groups: tuple[tuple[object, bool], ...]


class _CableSolidsModule(Protocol):
    """
    Describe the host adapter functions exercised without a live Fusion process.
    """

    GENERATED_STRIPE_GROUP_ID: str
    _prepare_group_sweep_segments: Callable[
        [tuple[RoutePreview, ...]],
        tuple[
            tuple[_SweepSegment, ...],
            tuple[Optional[int], ...],
            tuple[Optional[int], ...],
        ],
    ]
    _split_route_for_pullback: Callable[[RoutePreview, float], _PullbackSplit]
    _split_route_endpoint_pullbacks: Callable[..., _EndpointPullbackSplit]
    _attachment_pullback_mm: Callable[..., float]
    _connection_endpoint_pullback: Callable[..., tuple[float, object, Optional[UUID], float]]
    _build_continuous_segment_stripes: Callable[
        [
            tuple[_SweepSegment, ...],
            tuple[Optional[int], ...],
            tuple[Optional[int], ...],
            CableStripe,
            float,
        ],
        tuple[tuple[_SweepSegment, StripeMeshResult], ...],
    ]
    restore_cable_group_stripe_graphics: Callable[[object, object], int]
    apply_cable_group_materials: Callable[[object, object, HarnessDefinition], int]
    generated_cable_group_occurrences: Callable[[object], tuple[object, ...]]
    generated_cable_group_output_mode: Callable[[object], str]
    clear_group_stripe_graphics: Callable[..., None]
    cable_appearance: Callable[..., object]
    refresh_changed_generated_cable_groups: Callable[..., int]
    refresh_generated_cable_groups_for_connection: Callable[..., int]
    solve_cable_group_centerlines: Callable[..., object]
    world_to_harness: Callable[..., object]
    route_in_component_space: Callable[..., RoutePreview]
    build_cable_group_solid: Callable[..., None]
    _refresh_generated_cable_groups: Callable[..., int]
    hide_generated_cable_group_solids: Callable[[object], _VisibilityState]
    restore_generated_cable_group_visibility: Callable[[_VisibilityState], None]
    _replace_group_stripe_graphics: Callable[..., int]
    _replace_group_stripe_bodies: Callable[..., int]


@pytest.fixture
def cable_solids(monkeypatch: pytest.MonkeyPatch) -> Iterator[_CableSolidsModule]:
    """
    Import the solid adapter against minimal Fusion module stubs.
    """
    adsk_module = ModuleType("adsk")
    core_module = ModuleType("adsk.core")
    fusion_module = ModuleType("adsk.fusion")
    adsk_module.core = core_module  # type: ignore[attr-defined]
    adsk_module.fusion = fusion_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "adsk", adsk_module)
    monkeypatch.setitem(sys.modules, "adsk.core", core_module)
    monkeypatch.setitem(sys.modules, "adsk.fusion", fusion_module)
    module_names = (
        "cable_bundler.fusion.cable_solids",
        "cable_bundler.fusion.route_preview",
        "cable_bundler.fusion.harness_gateway",
    )
    fusion_package = importlib.import_module("cable_bundler.fusion")
    missing = object()
    previous_attributes = {
        module_name.rsplit(".", 1)[-1]: getattr(
            fusion_package, module_name.rsplit(".", 1)[-1], missing
        )
        for module_name in module_names
    }
    for module_name in module_names:
        monkeypatch.delitem(sys.modules, module_name, raising=False)
    module = importlib.import_module("cable_bundler.fusion.cable_solids")
    yield cast(_CableSolidsModule, cast(object, module))
    for name, previous in previous_attributes.items():
        if previous is missing:
            if hasattr(fusion_package, name):
                delattr(fusion_package, name)
        else:
            setattr(fusion_package, name, previous)


# noinspection DuplicatedCode
def _straight_route(identity: int, start: Vector3, end: Vector3) -> RoutePreview:
    """
    Build one exact straight route with stable identity.
    """
    delta = Vector3(
        (end.x - start.x) / 3.0,
        (end.y - start.y) / 3.0,
        (end.z - start.z) / 3.0,
    )
    curve = CubicBezier(
        start,
        start.translated(delta, 1.0),
        end.translated(delta, -1.0),
        end,
    )
    return RoutePreview(UUID(int=identity), f"Leg {identity}", (start, end), (curve,))


def _radial(result: StripeMeshResult, boundary: str) -> tuple[float, float, float]:
    """
    Return one required continuation radial for approximate comparisons.
    """
    continuation = result.start if boundary == "start" else result.end
    assert continuation is not None
    return continuation.radial.x, continuation.radial.y, continuation.radial.z


def test_splits_pullback_from_connection_facing_route_start(
    cable_solids: _CableSolidsModule,
) -> None:
    """
    Preserve the endpoint and total centerline while replacing its first span.
    """
    route = _straight_route(690, Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0))

    split = cable_solids._split_route_for_pullback(route, 2.5)

    assert split.pullback_length_mm == pytest.approx(2.5)
    assert split.pullback is not None
    assert split.insulation is not None
    assert split.pullback.curves[0].start == route.curves[0].start
    assert split.pullback.curves[-1].end.x == pytest.approx(2.5)
    assert split.insulation.curves[0].start == split.pullback.curves[-1].end
    assert split.insulation.curves[-1].end == route.curves[-1].end


def test_clamps_pullback_to_short_connection_route(
    cable_solids: _CableSolidsModule,
) -> None:
    """
    Replace the full branch when its configured pullback exceeds available length.
    """
    route = _straight_route(691, Vector3(0.0, 0.0, 0.0), Vector3(3.0, 0.0, 0.0))

    split = cable_solids._split_route_for_pullback(route, 12.0)

    assert split.pullback_length_mm == pytest.approx(3.0)
    assert split.pullback == route
    assert split.insulation is None


def test_splits_independent_pullbacks_from_both_main_route_ends(
    cable_solids: _CableSolidsModule,
) -> None:
    """
    Leave the middle insulation span while both connection endpoints remain fixed.
    """
    route = _straight_route(695, Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0))

    split = cable_solids._split_route_endpoint_pullbacks(route, 2.0, 3.0)

    assert split.start_pullback is not None
    assert split.end_pullback is not None
    assert split.insulation is not None
    assert split.start_pullback.curves[0].start.x == pytest.approx(0.0)
    assert split.start_pullback.curves[-1].end.x == pytest.approx(2.0)
    assert split.insulation.curves[0].start.x == pytest.approx(2.0)
    assert split.insulation.curves[-1].end.x == pytest.approx(7.0)
    assert split.end_pullback.curves[0].start.x == pytest.approx(7.0)
    assert split.end_pullback.curves[-1].end.x == pytest.approx(10.0)

    overlapping = cable_solids._split_route_endpoint_pullbacks(route, 8.0, 12.0)
    assert overlapping.insulation is None
    assert overlapping.start_pullback is not None
    assert overlapping.end_pullback is not None
    assert overlapping.start_pullback.curves[-1].end.x == pytest.approx(4.0)
    assert overlapping.end_pullback.curves[0].start.x == pytest.approx(4.0)


def test_resolves_pullback_only_for_lowest_connection_children(
    cable_solids: _CableSolidsModule,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Ignore an intermediate profile and honor the leaf's distance-mode setting.
    """
    group = valid_harness.cable_groups[0]
    connection = valid_harness.connections[0]
    parent = CableEndAttachment(
        target_kind=AttachmentTargetKind.PROFILE,
        entity_token="parent-profile",
        inherited_name="Parent",
        attachment_id=UUID(int=692),
    )
    child = CableEndAttachment(
        target_kind=None,
        attachment_id=UUID(int=693),
        parent_attachment_id=parent.attachment_id,
    )
    definition = replace(
        valid_harness,
        material_defaults=replace(
            valid_harness.material_defaults,
            pullback=CablePullbackSettings(PullbackMode.DISTANCE, 4.25),
        ),
        connections=(
            replace(connection, attachment=parent, additional_attachments=(child,)),
            *valid_harness.connections[1:],
        ),
    )

    assert cable_solids._attachment_pullback_mm(definition, group, parent.attachment_id, 0.8) == 0.0
    assert cable_solids._attachment_pullback_mm(
        definition, group, child.attachment_id, 0.4
    ) == pytest.approx(4.25)

    percent_definition = replace(
        definition,
        material_defaults=replace(
            definition.material_defaults,
            pullback=CablePullbackSettings(PullbackMode.PERCENT, 200.0),
        ),
    )
    assert cable_solids._attachment_pullback_mm(
        percent_definition, group, child.attachment_id, 0.4
    ) == pytest.approx(0.8)


def test_pullback_lookup_stays_within_its_cable_group_connections(
    cable_solids: _CableSolidsModule,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Ignore an equal attachment ID owned by a different cable group's end.
    """
    shared_id = UUID(int=698)
    first_connection, second_connection = valid_harness.connections
    first_attachment = CableEndAttachment(
        AttachmentTargetKind.PROFILE,
        "first-profile",
        "First",
        attachment_id=shared_id,
    )
    second_attachment = CableEndAttachment(
        AttachmentTargetKind.PROFILE,
        "second-profile",
        "Second",
        attachment_id=shared_id,
    )
    second_group = replace(
        valid_harness.cable_groups[0],
        connection_ids=(second_connection.connection_id,),
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(first_connection, attachment=first_attachment),
            replace(second_connection, attachment=second_attachment),
        ),
        cable_groups=(second_group,),
    )

    assert cable_solids._attachment_pullback_mm(
        definition,
        second_group,
        shared_id,
        0.5,
    ) == pytest.approx(1.0)


def test_resolves_single_root_leaf_pullback_for_main_route_endpoint(
    cable_solids: _CableSolidsModule,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Apply pullback to an ordinary one-node connection represented by a main leg.
    """
    group = valid_harness.cable_groups[0]
    connection = valid_harness.connections[0]
    attachment = CableEndAttachment(
        target_kind=AttachmentTargetKind.PROFILE,
        entity_token="leaf-profile",
        inherited_name="Leaf",
        attachment_id=UUID(int=694),
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(connection, attachment=attachment),
            *valid_harness.connections[1:],
        ),
    )

    distance_mm, materials, attachment_id, conductor_diameter_mm = (
        cable_solids._connection_endpoint_pullback(
            definition,
            group,
            connection.connection_id,
        )
    )

    assert distance_mm == pytest.approx(group.diameter_mm * 2.0)
    assert materials == definition.cable_group_materials(group)
    assert attachment_id == attachment.attachment_id
    assert conductor_diameter_mm == pytest.approx(group.diameter_mm * 0.75)


def test_finalize_replaces_main_route_endpoint_with_pullback_body(
    cable_solids: _CableSolidsModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Create a separate material body while retaining the complete connection length.
    """
    solid_builder = cast(
        Any,
        sys.modules["cable_bundler.fusion.cable_solid_parts.solid_builder"],
    )
    route = _straight_route(696, Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0))
    group = valid_harness.cable_groups[0]
    materials = valid_harness.material_defaults
    stored_bodies: list[Any] = []

    class _Bodies:
        @property
        def count(self) -> int:
            return len(stored_bodies)

    def build_sweep(
        _component: object,
        sweep_route: RoutePreview,
        diameter_mm: float,
        _transform: object,
        _centerline_name: str,
        _section_name: str,
        _sweep_name: str,
    ) -> tuple[object, float]:
        """
        Record exact split routes without invoking the live Fusion API.
        """
        body = SimpleNamespace(
            name="",
            appearance=None,
            route=sweep_route,
            diameter_mm=diameter_mm,
        )
        stored_bodies.append(body)
        length_mm = abs(sweep_route.curves[-1].end.x - sweep_route.curves[0].start.x)
        return body, length_mm

    add_attribute = Mock(return_value=object())
    component = SimpleNamespace(
        bRepBodies=_Bodies(),
        attributes=SimpleNamespace(add=add_attribute),
        name="",
    )
    stripes = Mock(return_value=0)
    preview_stripes = Mock(return_value=0)
    monkeypatch.setitem(solid_builder.__dict__, "_build_route_sweep", build_sweep)
    monkeypatch.setitem(
        solid_builder.__dict__,
        "route_in_component_space",
        lambda item, _matrix: item,
    )
    monkeypatch.setitem(
        solid_builder.__dict__,
        "cable_appearance",
        lambda _design, color, _reference=None: color.name,
    )
    monkeypatch.setitem(solid_builder.__dict__, "clear_group_stripe_graphics", Mock())
    monkeypatch.setitem(solid_builder.__dict__, "replace_group_stripe_bodies", stripes)
    monkeypatch.setitem(solid_builder.__dict__, "replace_group_stripe_graphics", preview_stripes)

    solid_builder.build_cable_group_solid(
        component,
        object(),
        group,
        0,
        (route,),
        object(),
        valid_harness.harness_id,
        materials,
        object(),
        "finalized",
        route_pullbacks_mm=(2.4,),
        route_end_pullbacks_mm=(0.0,),
        route_pullback_materials=(materials,),
        route_pullback_attachment_ids=(UUID(int=697),),
        route_pullback_diameters_mm=(group.diameter_mm * 0.75,),
        route_end_pullback_diameters_mm=(0.0,),
    )

    assert len(stored_bodies) == 2
    assert stored_bodies[0].appearance == "Black"
    assert stored_bodies[0].diameter_mm == pytest.approx(group.diameter_mm)
    assert stored_bodies[0].route.curves[0].start.x == pytest.approx(2.4)
    assert stored_bodies[1].appearance == "Copper"
    assert stored_bodies[1].diameter_mm == pytest.approx(group.diameter_mm * 0.75)
    assert stored_bodies[1].route.curves[0].start.x == pytest.approx(0.0)
    assert stored_bodies[1].route.curves[-1].end.x == pytest.approx(2.4)
    assert component.name.endswith("_10.00mm")
    metadata = json.loads(add_attribute.call_args.args[2])
    assert metadata["length_mm"] == pytest.approx(10.0)
    assert metadata["main_pullbacks"][0]["requested_mm"] == pytest.approx(2.4)
    assert metadata["main_pullbacks"][0]["diameter_mm"] == pytest.approx(group.diameter_mm * 0.75)
    stripe_routes = stripes.call_args.args[1]
    assert stripe_routes[0].curves[0].start.x == pytest.approx(2.4)

    stored_bodies.clear()
    preview_component = SimpleNamespace(
        bRepBodies=_Bodies(),
        attributes=SimpleNamespace(add=Mock(return_value=object())),
        name="",
    )
    solid_builder.build_cable_group_solid(
        preview_component,
        object(),
        group,
        0,
        (route,),
        object(),
        valid_harness.harness_id,
        materials,
        object(),
        "solids",
        route_pullbacks_mm=(2.4,),
        route_pullback_materials=(materials,),
        route_pullback_attachment_ids=(UUID(int=697),),
    )

    assert len(stored_bodies) == 1
    assert stored_bodies[0].route == route
    assert stored_bodies[0].appearance == "Black"
    preview_routes = preview_stripes.call_args.args[1]
    assert preview_routes == (route,)


def test_restores_transient_stripes_from_generated_routes(
    cable_solids: _CableSolidsModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Recreate decorations after reload without regenerating persistent bodies.
    """
    definition = replace(
        valid_harness,
        material_defaults=replace(
            valid_harness.material_defaults,
            stripes=(CableStripe(CableColor("Red", 255, 0, 0), 0.25),),
        ),
    )
    group = definition.cable_groups[0]
    route = _straight_route(900, Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0))
    metadata = {
        "cable_group_id": str(group.cable_group_id),
        "route_legs": [
            {
                "route_id": str(route.cable_id),
                "label": route.cable_number,
                "route_curves_mm": [
                    [
                        [point.x, point.y, point.z]
                        for point in (
                            route.curves[0].start,
                            route.curves[0].control_a,
                            route.curves[0].control_b,
                            route.curves[0].end,
                        )
                    ]
                ],
            }
        ],
    }
    attribute = type("Attribute", (), {"value": json.dumps(metadata)})()
    attributes = type("Attributes", (), {"itemByName": lambda *_args: attribute})()
    empty_graphics = type("GraphicsGroups", (), {"count": 0})()
    component = type(
        "Component",
        (),
        {"attributes": attributes, "customGraphicsGroups": empty_graphics},
    )()
    occurrence = type(
        "Occurrence",
        (),
        {"component": component, "isLightBulbOn": False},
    )()
    replace_graphics = Mock(return_value=4)
    monkeypatch.setattr(
        cable_solids,
        "generated_cable_group_occurrences",
        lambda _harness: (occurrence,),
    )
    monkeypatch.setattr(
        cable_solids,
        "_replace_group_stripe_graphics",
        replace_graphics,
    )

    harness = object()

    assert cable_solids.restore_cable_group_stripe_graphics(harness, definition) == 4

    assert replace_graphics.call_args.args[0] is harness
    restored_routes = replace_graphics.call_args.args[1]
    assert restored_routes == (route,)
    assert replace_graphics.call_args.args[3] == group.diameter_mm / 2.0
    assert replace_graphics.call_args.args[4] == group.cable_group_id
    assert replace_graphics.call_args.kwargs == {"is_visible": False}


def test_applies_connection_branch_appearance_and_stripe_overrides(
    cable_solids: _CableSolidsModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Recolor and redecorate each generated branch from its persistent node owner.
    """
    inherited_stripe = CableStripe(CableColor("White", 255, 255, 255), 0.2)
    first = CableEndAttachment(
        None,
        attachment_id=UUID(int=920),
        visual_overrides=CableVisualOverrides(
            main_color=CableColor("Red", 255, 0, 0),
            stripes=(),
        ),
    )
    second = CableEndAttachment(None, attachment_id=UUID(int=921))
    connection = replace(
        valid_harness.connections[0],
        attachment=first,
        additional_attachments=(second,),
    )
    definition = replace(
        valid_harness,
        connections=(connection, valid_harness.connections[1]),
        material_defaults=replace(
            valid_harness.material_defaults,
            stripes=(inherited_stripe,),
        ),
    )
    group = definition.cable_groups[0]
    main = _straight_route(922, Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0))
    branch_a = _straight_route(923, Vector3(10.0, 0.0, 0.0), Vector3(15.0, 2.0, 0.0))
    branch_b = _straight_route(924, Vector3(10.0, 0.0, 0.0), Vector3(15.0, -2.0, 0.0))

    def encoded(route: RoutePreview) -> list[list[list[float]]]:
        """
        Encode exact local curves for generated metadata.
        """
        return [
            [
                [point.x, point.y, point.z]
                for point in (curve.start, curve.control_a, curve.control_b, curve.end)
            ]
            for curve in route.curves
        ]

    metadata = {
        "cable_group_id": str(group.cable_group_id),
        "route_legs": [
            {
                "route_id": str(main.cable_id),
                "label": main.cable_number,
                "route_curves_mm": encoded(main),
            }
        ],
        "connection_branches": [
            {
                "route_id": str(route.cable_id),
                "label": route.cable_number,
                "diameter_mm": group.diameter_mm / 2.0,
                "attachment_id": str(attachment.attachment_id),
                "route_curves_mm": encoded(route),
            }
            for route, attachment in ((branch_a, first), (branch_b, second))
        ],
    }
    attribute = SimpleNamespace(value=json.dumps(metadata))
    bodies = [SimpleNamespace(appearance=None) for _index in range(3)]
    component = SimpleNamespace(
        attributes=SimpleNamespace(itemByName=lambda *_args: attribute),
        bRepBodies=SimpleNamespace(count=len(bodies), item=lambda index: bodies[index]),
    )
    occurrence = SimpleNamespace(component=component, isLightBulbOn=True)
    replace_graphics = Mock(return_value=1)
    monkeypatch.setattr(
        cable_solids,
        "generated_cable_group_occurrences",
        lambda _harness: (occurrence,),
    )
    monkeypatch.setattr(cable_solids, "generated_cable_group_output_mode", lambda _item: "solids")
    monkeypatch.setattr(cable_solids, "clear_group_stripe_graphics", Mock())
    monkeypatch.setattr(cable_solids, "_replace_group_stripe_graphics", replace_graphics)
    monkeypatch.setattr(
        cable_solids,
        "cable_appearance",
        lambda _design, color, _appearance=None: color.name,
    )

    assert cable_solids.apply_cable_group_materials(object(), object(), definition) == 1

    assert [body.appearance for body in bodies] == ["Black", "Red", "Black"]
    decorations = replace_graphics.call_args.kwargs["branch_decorations"]
    assert decorations[0][1] == ()
    assert decorations[1][1] == (inherited_stripe,)


def test_replacing_harness_owned_stripes_preserves_other_cable_groups(
    cable_solids: _CableSolidsModule,
) -> None:
    """
    Replace one stable harness overlay without deleting a neighboring group.
    """
    target_id = UUID(int=701)
    other_id = UUID(int=702)

    def graphics_group(identity: UUID) -> Any:
        """
        Build one empty deletable stripe-group test double.
        """
        return type(
            "StripeGroup",
            (),
            {
                "id": f"{cable_solids.GENERATED_STRIPE_GROUP_ID}:{identity}",
                "name": "Cable Group Solid Stripes",
                "count": 0,
                "deleteMe": Mock(return_value=True),
            },
        )()

    target = graphics_group(target_id)
    other = graphics_group(other_id)
    stored = (target, other)
    groups = type(
        "GraphicsGroups",
        (),
        {"count": len(stored), "item": lambda _self, index: stored[index]},
    )()
    harness = type("Harness", (), {"customGraphicsGroups": groups})()

    assert cable_solids._replace_group_stripe_graphics(harness, (), (), 0.5, target_id) == 0

    target.deleteMe.assert_called_once_with()
    other.deleteMe.assert_not_called()


def test_finalized_stripes_are_persistent_colored_mesh_bodies(
    cable_solids: _CableSolidsModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Convert the same procedural stripe triangles into renderable component geometry.
    """
    stripe = CableStripe(CableColor("Red", 255, 0, 0), 0.25)
    route = _straight_route(703, Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0))
    body = type("MeshBody", (), {"name": "", "appearance": None})()
    add = Mock(return_value=body)
    mesh_bodies = type(
        "MeshBodies",
        (),
        {"count": 0, "item": lambda _self, _index: None, "addByTriangleMeshData": add},
    )()
    component = type("Component", (), {"meshBodies": mesh_bodies})()
    appearance = object()
    stripes_module = cast(
        Any,
        sys.modules["cable_bundler.fusion.cable_solid_parts.stripes"],
    )
    monkeypatch.setitem(vars(stripes_module), "cable_appearance", Mock(return_value=appearance))

    count = cable_solids._replace_group_stripe_bodies(
        component,
        (route,),
        (stripe,),
        0.5,
        object(),
    )

    assert count == 1
    coordinates, indices, normals, normal_indices = add.call_args.args
    assert coordinates
    assert indices
    assert max(abs(coordinate) for coordinate in coordinates) <= 1.1
    assert normals == []
    assert normal_indices == []
    assert body.name == "Cable Group Leg 1 Stripe 1"
    assert body.appearance is appearance


def test_generated_solids_visibility_round_trip_preserves_prior_state(
    cable_solids: _CableSolidsModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Hide visible managed occurrences temporarily without revealing prior-hidden output.
    """
    visible = type("Occurrence", (), {"isLightBulbOn": True, "isValid": True})()
    hidden = type("Occurrence", (), {"isLightBulbOn": False, "isValid": True})()
    stripe_group = type(
        "StripeGroup",
        (),
        {
            "id": f"{cable_solids.GENERATED_STRIPE_GROUP_ID}:{UUID(int=1)}",
            "name": "Cable Group Solid Stripes",
            "isVisible": True,
            "isValid": True,
        },
    )()
    groups = type(
        "GraphicsGroups",
        (),
        {"count": 1, "item": lambda _self, _index: stripe_group},
    )()
    harness = type("Harness", (), {"customGraphicsGroups": groups})()
    monkeypatch.setattr(
        cable_solids,
        "generated_cable_group_occurrences",
        lambda _harness: (visible, hidden),
    )

    state = cable_solids.hide_generated_cable_group_solids(harness)

    assert state.occurrences == ((visible, True), (hidden, False))
    assert state.stripe_groups == ((stripe_group, True),)
    assert not visible.isLightBulbOn
    assert not hidden.isLightBulbOn
    assert not stripe_group.isVisible

    cable_solids.restore_generated_cable_group_visibility(state)

    assert visible.isLightBulbOn
    assert not hidden.isLightBulbOn
    assert stripe_group.isVisible


def test_connection_completion_rebuilds_its_group_with_branch_sweep_options(
    cable_solids: _CableSolidsModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Replace affected output with reduced branch diameters while preserving its state.
    """
    group = valid_harness.cable_groups[0]
    route = _straight_route(704, Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0))
    branch = _straight_route(705, Vector3(10.0, 0.0, 0.0), Vector3(20.0, 2.0, 0.0))
    leg = SimpleNamespace(
        route_id=route.cable_id,
        cable_group_id=group.cable_group_id,
        diameter_mm=None,
        is_connection_branch=False,
    )
    branch_leg = SimpleNamespace(
        route_id=branch.cable_id,
        cable_group_id=group.cable_group_id,
        diameter_mm=group.diameter_mm / 2.0,
        is_connection_branch=True,
    )

    def occurrence(identity: UUID, *, visible: bool) -> Any:
        """
        Build one generated occurrence with persistent group metadata.
        """
        attribute = SimpleNamespace(
            value=json.dumps(
                {
                    "cable_group_id": str(identity),
                    "output_mode": "finalized",
                }
            )
        )
        return SimpleNamespace(
            component=SimpleNamespace(
                attributes=SimpleNamespace(itemByName=lambda *_args: attribute)
            ),
            isLightBulbOn=visible,
            isValid=True,
            deleteMe=Mock(return_value=True),
        )

    previous = occurrence(group.cable_group_id, visible=False)
    unrelated = occurrence(UUID(int=999), visible=True)
    replacement = SimpleNamespace(
        component=object(),
        isLightBulbOn=True,
        isValid=True,
        deleteMe=Mock(return_value=True),
    )
    add_occurrence = Mock(return_value=replacement)
    harness = SimpleNamespace(occurrences=SimpleNamespace(addNewComponent=add_occurrence))
    build = Mock()
    matrix = object()
    transform = object()
    core_module = sys.modules["adsk.core"]
    core_module.Matrix3D = SimpleNamespace(create=Mock(return_value=matrix))  # type: ignore[attr-defined]
    monkeypatch.setattr(
        cable_solids,
        "generated_cable_group_occurrences",
        lambda _harness: (previous, unrelated),
    )
    monkeypatch.setattr(
        cable_solids,
        "solve_cable_group_centerlines",
        lambda _design, _definition, _notices: (
            (route, branch),
            (leg, branch_leg),
        ),
    )
    monkeypatch.setattr(cable_solids, "world_to_harness", lambda _design, _harness: transform)
    monkeypatch.setattr(cable_solids, "build_cable_group_solid", build)

    updated = cable_solids.refresh_generated_cable_groups_for_connection(
        object(),
        harness,
        valid_harness,
        valid_harness.connections[0].connection_id,
        [],
    )

    assert updated == 1
    add_occurrence.assert_called_once_with(matrix)
    assert build.call_args.args[0] is replacement.component
    assert build.call_args.args[4] == (route, branch)
    assert build.call_args.args[-1] == "finalized"
    assert build.call_args.kwargs == {
        "is_visible": False,
        "route_diameters_mm": (group.diameter_mm, group.diameter_mm / 2.0),
        "connection_branch_indices": frozenset({1}),
    }
    assert replacement.isLightBulbOn is False
    previous.deleteMe.assert_called_once_with()
    unrelated.deleteMe.assert_not_called()


def test_geometry_refresh_rebuilds_only_group_with_changed_branch_curve(
    cable_solids: _CableSolidsModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Include reduced connection branches when detecting locally changed output.
    """
    group = valid_harness.cable_groups[0]
    main = _straight_route(801, Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0))
    old_branch = _straight_route(802, Vector3(10.0, 0.0, 0.0), Vector3(20.0, 0.0, 0.0))
    moved_branch = _straight_route(802, Vector3(10.0, 0.0, 0.0), Vector3(20.0, 5.0, 0.0))

    def encoded(route: RoutePreview) -> list[list[list[float]]]:
        """
        Serialize exact curve controls in generated metadata form.
        """
        return [
            [
                [point.x, point.y, point.z]
                for point in (curve.start, curve.control_a, curve.control_b, curve.end)
            ]
            for curve in route.curves
        ]

    metadata = {
        "cable_group_id": str(group.cable_group_id),
        "route_legs": [
            {
                "route_id": str(main.cable_id),
                "label": main.cable_number,
                "route_curves_mm": encoded(main),
            }
        ],
        "connection_branches": [
            {
                "route_id": str(old_branch.cable_id),
                "label": old_branch.cable_number,
                "route_curves_mm": encoded(old_branch),
            }
        ],
    }
    attribute = SimpleNamespace(value=json.dumps(metadata))
    occurrence = SimpleNamespace(
        component=SimpleNamespace(attributes=SimpleNamespace(itemByName=lambda *_args: attribute))
    )
    legs = (
        SimpleNamespace(route_id=main.cable_id, cable_group_id=group.cable_group_id),
        SimpleNamespace(route_id=moved_branch.cable_id, cable_group_id=group.cable_group_id),
    )
    rebuild = Mock(return_value=1)
    monkeypatch.setattr(
        cable_solids,
        "generated_cable_group_occurrences",
        lambda _harness: (occurrence,),
    )
    monkeypatch.setattr(
        cable_solids,
        "solve_cable_group_centerlines",
        lambda _design, _definition, _notices: ((main, moved_branch), legs),
    )
    monkeypatch.setattr(cable_solids, "world_to_harness", lambda *_args: object())
    monkeypatch.setattr(
        cable_solids,
        "route_in_component_space",
        lambda route, _transform: route,
    )
    monkeypatch.setattr(cable_solids, "_refresh_generated_cable_groups", rebuild)

    updated = cable_solids.refresh_changed_generated_cable_groups(
        object(),
        object(),
        valid_harness,
        [],
    )

    assert updated == 1
    assert rebuild.call_args.args[3] == frozenset({group.cable_group_id})


def test_copies_root_decoration_position_to_every_branch(
    cable_solids: _CableSolidsModule,
) -> None:
    """
    Give every segment leaving one junction the same physical stripe start.
    """
    junction = Vector3(0.0, 0.0, 0.0)
    routes = (
        _straight_route(1, Vector3(-10.0, 0.0, 0.0), junction),
        _straight_route(2, junction, Vector3(10.0, 0.0, 0.0)),
        _straight_route(3, junction, Vector3(15.0, 0.0, 0.0)),
    )
    stripe = CableStripe(CableColor("Red", 255, 0, 0), 0.25, angle_deg=31.0)

    segments, starts, ends = cable_solids._prepare_group_sweep_segments(routes)
    decorated = cable_solids._build_continuous_segment_stripes(segments, starts, ends, stripe, 0.5)

    start_radials = [_radial(result, "start") for _segment, result in decorated]
    assert len(start_radials) == 3
    assert start_radials[1] == pytest.approx(start_radials[0])
    assert start_radials[2] == pytest.approx(start_radials[0])


def test_projects_continuous_decoration_onto_an_angled_branch(
    cable_solids: _CableSolidsModule,
) -> None:
    """
    Accept non-collinear junction tangents and retain a valid stripe radial.
    """
    junction = Vector3(0.0, 0.0, 0.0)
    routes = (
        _straight_route(4, Vector3(-10.0, 0.0, 0.0), junction),
        _straight_route(5, junction, Vector3(10.0, 0.0, 0.0)),
        _straight_route(6, junction, Vector3(0.0, 10.0, 0.0)),
    )
    stripe = CableStripe(CableColor("Green", 0, 180, 80), 0.25, angle_deg=27.0)

    segments, starts, ends = cable_solids._prepare_group_sweep_segments(routes)
    decorated = cable_solids._build_continuous_segment_stripes(
        segments,
        starts,
        ends,
        stripe,
        0.5,
    )

    assert len(segments) == len(decorated) == 3
    for segment, result in decorated:
        assert result.start is not None
        tangent = unit(difference(segment.route.points[1], segment.route.points[0]))
        assert dot(result.start.radial, tangent) == pytest.approx(0.0, abs=1e-9)
        assert result.start.repeat_phase_mm == pytest.approx(0.0)


def test_propagates_decoration_through_a_downstream_junction(
    cable_solids: _CableSolidsModule,
) -> None:
    """
    Continue an upstream helical endpoint onto every downstream child segment.
    """
    root = Vector3(0.0, 0.0, 0.0)
    downstream = Vector3(10.0, 0.0, 0.0)
    routes = (
        _straight_route(10, root, downstream),
        _straight_route(11, root, Vector3(-10.0, 0.0, 0.0)),
        _straight_route(12, root, Vector3(-15.0, 0.0, 0.0)),
        _straight_route(13, downstream, Vector3(20.0, 0.0, 0.0)),
        _straight_route(14, downstream, Vector3(25.0, 0.0, 0.0)),
    )
    stripe = CableStripe(
        CableColor("White", 255, 255, 255),
        0.2,
        StripePattern.HELICAL,
        angle_deg=18.0,
        repeat_mm=7.0,
    )

    segments, starts, ends = cable_solids._prepare_group_sweep_segments(routes)
    decorated = cable_solids._build_continuous_segment_stripes(segments, starts, ends, stripe, 0.5)
    by_identity = {segment.route.cable_id.int: result for segment, result in decorated}

    upstream_end = _radial(by_identity[10], "end")
    assert _radial(by_identity[13], "start") == pytest.approx(upstream_end)
    assert _radial(by_identity[14], "start") == pytest.approx(upstream_end)
    left_start = by_identity[13].start
    right_start = by_identity[14].start
    assert left_start is not None
    assert right_start is not None
    assert left_start.repeat_phase_mm == pytest.approx(3.0)
    assert right_start.repeat_phase_mm == pytest.approx(3.0)


def test_continues_across_an_internally_split_pass_through_route(
    cable_solids: _CableSolidsModule,
) -> None:
    """
    Decorate every solid segment created where a lead meets a logical route interior.
    """
    start = Vector3(-10.0, 0.0, 0.0)
    junction = Vector3(0.0, 0.0, 0.0)
    end = Vector3(10.0, 0.0, 0.0)
    left = _straight_route(20, start, junction).curves[0]
    right = _straight_route(20, junction, end).curves[0]
    pass_through = RoutePreview(UUID(int=20), "Pass Through", (start, junction, end), (left, right))
    lead = _straight_route(21, Vector3(-5.0, 0.0, 0.0), junction)
    stripe = CableStripe(CableColor("Blue", 0, 80, 255), 0.2)

    segments, starts, ends = cable_solids._prepare_group_sweep_segments((pass_through, lead))
    decorated = cable_solids._build_continuous_segment_stripes(segments, starts, ends, stripe, 0.5)

    assert len(segments) == 3
    junction_boundaries = tuple(
        boundary
        for segment in segments
        for boundary in (segment.route.curves[0].start, segment.route.curves[-1].end)
        if boundary == junction
    )
    assert junction_boundaries == (junction,) * 3
    assert len(decorated) == 3
    start_radials = [_radial(result, "start") for _segment, result in decorated]
    assert start_radials[1] == pytest.approx(start_radials[0])
    assert start_radials[2] == pytest.approx(start_radials[0])
