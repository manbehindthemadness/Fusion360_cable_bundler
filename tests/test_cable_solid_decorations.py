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
    CableEndAttachment,
    CablePullbackSettings,
    CableStripe,
    HarnessDefinition,
    PullbackMode,
)
from cable_bundler.routing import CubicBezier, RoutePreview, StripeMeshResult, Vector3


# noinspection DuplicatedCode
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
    _attachment_weld_endpoint: Callable[..., Any]
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
    generated_attachment_bodies: Callable[..., tuple[object, ...]]
    generated_cable_group_output_mode: Callable[[object], str]
    clear_group_stripe_graphics: Callable[..., None]
    cable_appearance: Callable[..., object]
    refresh_changed_generated_cable_groups: Callable[..., int]
    refresh_generated_cable_groups_for_connection: Callable[..., int]
    solve_cable_group_centerlines: Callable[..., object]
    world_to_harness: Callable[..., object]
    resolve_attachment_target: Callable[..., object]
    route_in_component_space: Callable[..., RoutePreview]
    build_cable_group_solid: Callable[..., None]
    _refresh_generated_cable_groups: Callable[..., int]
    hide_generated_cable_group_solids: Callable[[object], _VisibilityState]
    restore_generated_cable_group_visibility: Callable[[_VisibilityState], None]
    _replace_group_stripe_graphics: Callable[..., int]
    _replace_group_stripe_bodies: Callable[..., int]


# noinspection DuplicatedCode
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


def test_generated_attachment_bodies_selects_only_matching_sweeps(
    cable_solids: _CableSolidsModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Select insulation and pullback proxies without selecting weld or adjacent bodies.
    """
    attachment_id = UUID(int=901)
    route_curves = [[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3.0, 0.0, 0.0]]]
    metadata = {
        "route_legs": [],
        "connection_branches": [
            {
                "route_id": str(UUID(int=902)),
                "label": "Adjacent branch",
                "diameter_mm": 1.0,
                "attachment_id": str(UUID(int=903)),
                "route_curves_mm": route_curves,
            },
            {
                "route_id": str(UUID(int=904)),
                "label": "Selected branch",
                "diameter_mm": 1.0,
                "attachment_id": str(attachment_id),
                "route_curves_mm": route_curves,
                "insulation_body_count": 1,
                "pullback_body_count": 1,
                "weld_body_count": 1,
                "weld_diameter_mm": 1.2,
                "weld_conductor_diameter_mm": 0.8,
                "weld_length_mm": 0.5,
            },
        ],
    }

    def collection(items: list[object]) -> SimpleNamespace:
        """
        Provide the indexed Fusion collection surface used by the adapter.
        """
        return SimpleNamespace(count=len(items), item=lambda index: items[index])

    native_bodies = [object() for _ in range(5)]
    proxy_bodies = [object() for _ in range(5)]
    component = SimpleNamespace(
        attributes=SimpleNamespace(
            itemByName=lambda _group, _name: SimpleNamespace(value=json.dumps(metadata))
        ),
        bRepBodies=collection(native_bodies),
    )
    occurrence = SimpleNamespace(component=component)
    root_occurrence = SimpleNamespace(bRepBodies=collection(proxy_bodies))
    root = SimpleNamespace(
        allOccurrencesByComponent=lambda _component: collection([root_occurrence])
    )
    monkeypatch.setattr(
        cable_solids,
        "generated_cable_group_occurrences",
        lambda _harness: (occurrence,),
    )

    assert cable_solids.generated_attachment_bodies(root, object(), attachment_id) == tuple(
        proxy_bodies[2:4]
    )


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


def test_resolves_weld_from_leaf_face_and_conductor_diameter(
    cable_solids: _CableSolidsModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Scale weld diameter and reach from the resolved leaf conductor.
    """
    group = valid_harness.cable_groups[0]
    connection = valid_harness.connections[0]
    attachment = CableEndAttachment(
        target_kind=AttachmentTargetKind.FACE,
        entity_token="leaf-face",
        inherited_name="Terminal Face",
        parameters=(0.25, 0.75),
        attachment_id=UUID(int=695),
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(connection, attachment=attachment),
            *valid_harness.connections[1:],
        ),
    )
    face = object()
    fusion_module = sys.modules["adsk.fusion"]
    fusion_module.BRepFace = SimpleNamespace(cast=lambda entity: entity)  # type: ignore[attr-defined]
    monkeypatch.setattr(cable_solids, "resolve_attachment_target", lambda *_args: face)

    endpoint = cable_solids._attachment_weld_endpoint(
        object(),
        definition,
        group,
        attachment.attachment_id,
    )

    assert endpoint is not None
    assert endpoint.target_face is face
    assert endpoint.conductor_diameter_mm == pytest.approx(group.diameter_mm * 0.75)
    assert endpoint.diameter_mm == pytest.approx(group.diameter_mm * 0.75 * 1.5)
    assert endpoint.radius_mm == pytest.approx(group.diameter_mm * 0.75 * 0.75)


def test_resolves_spherical_weld_for_non_face_leaf(
    cable_solids: _CableSolidsModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Retain weld sizing without requiring a conforming BRep face.
    """
    group = valid_harness.cable_groups[0]
    connection = valid_harness.connections[0]
    attachment = CableEndAttachment(
        target_kind=AttachmentTargetKind.CONSTRUCTION_POINT,
        entity_token="leaf-point",
        inherited_name="Terminal Point",
        attachment_id=UUID(int=696),
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(connection, attachment=attachment),
            *valid_harness.connections[1:],
        ),
    )
    resolve_target = Mock(side_effect=AssertionError("Non-face weld resolved a target entity."))
    monkeypatch.setattr(cable_solids, "resolve_attachment_target", resolve_target)

    endpoint = cable_solids._attachment_weld_endpoint(
        object(),
        definition,
        group,
        attachment.attachment_id,
    )

    assert endpoint is not None
    assert endpoint.target_face is None
    assert endpoint.diameter_mm == pytest.approx(group.diameter_mm * 0.75 * 1.5)
    resolve_target.assert_not_called()


def test_rejected_conforming_weld_removes_construction_in_dependency_order(
    cable_solids: _CableSolidsModule,
) -> None:
    """
    Delete rejected weld sketches before their supporting construction planes.
    """
    welds_module = importlib.import_module("cable_bundler.fusion.cable_solid_parts.welds")
    removed: list[str] = []

    def entity(name: str) -> SimpleNamespace:
        """
        Return one valid deletable Fusion construction-feature stand-in.
        """
        return SimpleNamespace(
            isValid=True,
            deleteMe=lambda: removed.append(name) is None,
        )

    welds_module._remove_failed_construction(
        [entity("sketch-1"), entity("sketch-2")],
        [entity("plane-1"), entity("plane-2")],
    )

    assert removed == ["sketch-2", "sketch-1", "plane-2", "plane-1"]


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
    welds_module = importlib.import_module("cable_bundler.fusion.cable_solid_parts.welds")
    weld_endpoint = welds_module.WeldEndpoint(
        UUID(int=697),
        object(),
        group.diameter_mm * 0.75,
        materials.weld,
    )

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

    def build_weld(
        _component: object,
        _route: RoutePreview,
        _transform: object,
        _endpoint: object,
        _name: str,
    ) -> object:
        """
        Record a distinct finalized weld body without invoking Fusion.
        """
        body = SimpleNamespace(name="", appearance=None)
        stored_bodies.append(body)
        return SimpleNamespace(body=body, length_mm=weld_endpoint.radius_mm)

    monkeypatch.setitem(solid_builder.__dict__, "build_weld_body", build_weld)
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
        route_welds=(weld_endpoint,),
    )

    assert len(stored_bodies) == 3
    assert stored_bodies[0].appearance == "Black"
    assert stored_bodies[0].diameter_mm == pytest.approx(group.diameter_mm)
    assert stored_bodies[0].route.curves[0].start.x == pytest.approx(2.4)
    assert stored_bodies[1].appearance == "Copper"
    assert stored_bodies[1].diameter_mm == pytest.approx(group.diameter_mm * 0.75)
    assert stored_bodies[1].route.curves[0].start.x == pytest.approx(0.0)
    assert stored_bodies[1].route.curves[-1].end.x == pytest.approx(2.4)
    assert stored_bodies[2].appearance == "Silver"
    assert component.name.endswith("_10.00mm")
    metadata = json.loads(add_attribute.call_args.args[2])
    assert metadata["length_mm"] == pytest.approx(10.0)
    assert metadata["main_pullbacks"][0]["requested_mm"] == pytest.approx(2.4)
    assert metadata["main_pullbacks"][0]["diameter_mm"] == pytest.approx(group.diameter_mm * 0.75)
    assert metadata["main_welds"][0]["diameter_mm"] == pytest.approx(group.diameter_mm * 0.75 * 1.5)
    assert metadata["main_welds"][0]["length_mm"] == pytest.approx(group.diameter_mm * 0.75 * 0.75)
    assert metadata["weld"] == {
        "appearance": None,
        "color": "#C0C0C0",
        "color_name": "Silver",
        "value": 150.0,
    }
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
        route_welds=(weld_endpoint,),
    )

    assert len(stored_bodies) == 1
    assert stored_bodies[0].route == route
    assert stored_bodies[0].appearance == "Black"
    preview_routes = preview_stripes.call_args.args[1]
    assert preview_routes == (route,)
