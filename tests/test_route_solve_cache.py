"""
Regressions for geometry-validated route-solve reuse.
"""

from __future__ import annotations

import math
from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.application import CableGroupRouteLeg
from cable_bundler.domain import (
    AttachmentTargetKind,
    CableEndAttachment,
    CableVisualOverrides,
    Connection,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    RefineGeometry,
)
from cable_bundler.domain.connection_packing import PackedConnection, pack_connections
from cable_bundler.routing import (
    CubicBezier,
    RefineFrame,
    RoutePreview,
    TransitionLengths,
    Vector3,
    fair_route,
    route_collisions,
)
from cable_bundler.routing.geometry import dot
from tests.fusion_ui_support import _PaletteLifecycleModule


def test_profile_resolution_skips_invalid_candidates_after_geometry_change(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Use a live remapped profile when Fusion retains an invalid historical match.
    """
    from cable_bundler.fusion.route_preview_parts import frames as route_frames

    del addin_module
    invalid = SimpleNamespace(is_profile=True, isValid=False)
    remapped = SimpleNamespace(is_profile=True, isValid=True)
    unrelated = SimpleNamespace(is_profile=False, isValid=True)
    design = SimpleNamespace(findEntityByToken=lambda _entity_token: (invalid, unrelated, remapped))
    profile_type = SimpleNamespace(
        cast=lambda entity: entity if getattr(entity, "is_profile", False) else None
    )
    monkeypatch.setitem(vars(route_frames.adsk.fusion), "Profile", profile_type)

    assert route_frames._resolve_profile(design, "profile-token") is remapped


@pytest.mark.parametrize(
    ("centroid", "hole_center", "expected_x_mm"),
    [
        (SimpleNamespace(x=0.2, y=0.0, z=0.0), SimpleNamespace(x=0.0, y=0.0, z=0.0), 0.0),
        (SimpleNamespace(x=0.0, y=0.0, z=0.0), None, 0.0),
        (SimpleNamespace(x=math.nan, y=0.0, z=0.0), None, 2.5),
        (None, None, 2.5),
    ],
)
def test_face_attachment_anchors_at_contact_center_even_when_sample_is_off_center(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    centroid: object,
    hole_center: object,
    expected_x_mm: float,
) -> None:
    """
    Center an annular pad while retaining its on-face point for normal evaluation.
    """
    from cable_bundler.fusion.route_preview_parts import frames as route_frames

    del addin_module
    parameter = object()
    normal = SimpleNamespace(x=0.0, y=0.0, z=1.0)
    sampled_point = SimpleNamespace(x=0.25, y=0.0, z=0.0)
    evaluator = SimpleNamespace(
        getPointAtParameter=Mock(return_value=(True, sampled_point)),
        getNormalAtParameter=Mock(return_value=(True, normal)),
    )
    loops = SimpleNamespace(count=0, item=Mock())
    if hole_center is not None:
        edge = SimpleNamespace(
            geometry=SimpleNamespace(objectType="adsk::core::Circle3D", center=hole_center),
            assemblyContext=None,
        )
        coedges = SimpleNamespace(count=1, item=Mock(return_value=SimpleNamespace(edge=edge)))
        loops = SimpleNamespace(
            count=1,
            item=Mock(return_value=SimpleNamespace(isOuter=False, coEdges=coedges)),
        )
    face = SimpleNamespace(centroid=centroid, evaluator=evaluator, loops=loops)
    monkeypatch.setitem(
        vars(route_frames.adsk.core),
        "Point2D",
        SimpleNamespace(create=Mock(return_value=parameter)),
    )
    monkeypatch.setitem(vars(route_frames), "resolve_attachment_target", Mock(return_value=face))
    attachment = CableEndAttachment(
        AttachmentTargetKind.FACE,
        "pad-face-token",
        "Pad",
        parameters=(1.0, 2.0),
        attachment_id=UUID(int=900),
    )
    adjacent = route_frames.ProfileFrame(
        Vector3(0.0, 0.0, 10.0),
        Vector3(0.0, 0.0, 1.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
    )

    frame = route_frames._attachment_frame(object(), attachment, adjacent)

    assert frame is not None
    assert frame.origin == Vector3(expected_x_mm, 0.0, 0.0)
    assert frame.normal == Vector3(0.0, 0.0, 1.0)
    evaluator.getNormalAtParameter.assert_called_once_with(parameter)


def test_profile_resolution_materializes_lazy_profiles_after_sketch_move(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Retry a stored token after reading Fusion's lazily rebuilt sketch profiles.
    """
    from cable_bundler.fusion.route_preview_parts import frames as route_frames

    del addin_module
    state = {"materialized": False}
    remapped = SimpleNamespace(is_profile=True, isValid=True)

    class LazyProfile:
        @property
        def entityToken(self) -> str:
            state["materialized"] = True
            return "remapped-token"

    collection = SimpleNamespace(count=1, item=lambda _index: LazyProfile())
    sketch = SimpleNamespace(profiles=collection)
    component = SimpleNamespace(sketches=SimpleNamespace(count=1, item=lambda _index: sketch))
    design = SimpleNamespace(
        allComponents=SimpleNamespace(count=1, item=lambda _index: component),
        findEntityByToken=lambda _token: (remapped,) if state["materialized"] else (),
    )
    profile_type = SimpleNamespace(
        cast=lambda entity: entity if getattr(entity, "is_profile", False) else None
    )
    monkeypatch.setitem(vars(route_frames.adsk.fusion), "Profile", profile_type)

    assert route_frames._resolve_profile(design, "profile-token") is remapped
    assert state["materialized"] is True


def test_attached_connection_prepends_external_contact_frame(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Extend an attached cable end to its target before traversing native guides.
    """
    from cable_bundler.fusion.route_preview_parts import frames as route_frames
    from cable_bundler.fusion.route_preview_parts import solver as route_solver

    del addin_module
    member_frame = route_solver.ProfileFrame(
        Vector3(0.0, 0.0, 10.0),
        Vector3(0.0, 0.0, 1.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
    )
    target_frame = replace(member_frame, origin=Vector3(0.0, 0.0, 0.0))
    connection = Connection(
        UUID(int=1),
        "End 1",
        "member-token",
        attachment=CableEndAttachment(
            AttachmentTargetKind.JOINT_ORIGIN,
            "target-token",
            "Connector J1",
        ),
    )
    monkeypatch.setattr(route_frames, "_profile_frame", lambda _design, _token: member_frame)
    monkeypatch.setattr(
        route_frames,
        "_attachment_frame",
        lambda _design, _attachment, _adjacent: target_frame,
    )

    frames = route_solver.connection_route_frames(object(), connection, {}, {})

    assert frames == (target_frame, member_frame)


def test_multiple_connections_create_loosely_packed_branches(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Size and place branch disks without overlap inside the parent envelope.
    """
    from cable_bundler.fusion.route_preview_parts import frames as route_frames
    from cable_bundler.fusion.route_preview_parts import solver as route_solver

    del addin_module
    refine_id = UUID(int=90)
    first = CableEndAttachment(
        AttachmentTargetKind.JOINT_ORIGIN,
        "target-1",
        "Target 1",
        attachment_id=UUID(int=91),
        ordered_control_ids=(refine_id,),
        visual_overrides=CableVisualOverrides(diameter_mm=0.4),
    )
    second = CableEndAttachment(
        AttachmentTargetKind.JOINT_ORIGIN,
        "target-2",
        "Target 2",
        attachment_id=UUID(int=92),
    )
    connection = replace(
        valid_harness.connections[0],
        attachment=first,
        additional_attachments=(second,),
    )
    definition = replace(
        valid_harness,
        connections=(connection, valid_harness.connections[1]),
        controls=(
            *valid_harness.controls,
            ControlStructure(
                refine_id,
                "Connection Refine",
                ControlKind.REFINE,
                "",
                refine_geometry=RefineGeometry(
                    (0.0, 2.0, 5.0),
                    (1.0, 0.0, 0.0),
                    (0.0, 1.0, 0.0),
                    2.0,
                ),
            ),
        ),
    )
    guide = route_solver.ProfileFrame(
        Vector3(0.0, 0.0, 0.0),
        Vector3(0.0, 0.0, 1.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
    )
    targets = {
        first.attachment_id: replace(guide, origin=Vector3(-5.0, 0.0, 10.0)),
        second.attachment_id: replace(guide, origin=Vector3(5.0, 0.0, 10.0)),
    }
    refine_frame = RefineFrame(
        refine_id,
        "Connection Refine",
        Vector3(0.0, 2.0, 5.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
    )
    solver_namespace = vars(route_solver)
    monkeypatch.setitem(
        solver_namespace,
        "connection_profile_frames",
        lambda _design, _connection, _cache: (guide,),
    )
    monkeypatch.setattr(
        route_frames,
        "connection_attachment_frame",
        lambda _design, _connection, attachment, _guide, _cache: targets[attachment.attachment_id],
    )
    monkeypatch.setitem(
        solver_namespace,
        "fair_route",
        lambda route, *_args, **_kwargs: route,
    )

    routes, legs = route_solver._connection_branch_routes(
        object(),
        definition,
        {item.connection_id: item for item in definition.connections},
        {item.control_id: item for item in definition.controls},
        {refine_id: refine_frame},
        {},
        definition.auto_transition_preset.span_fraction,
        {
            (
                definition.cable_groups[0].cable_group_id,
                connection.connection_id,
            ): route_solver._BranchAnchor(Vector3(2.0, 0.0, 0.0), Vector3(2.0, 0.0, 1.0))
        },
    )

    group = definition.cable_groups[0]
    assert len(routes) == 2
    assert legs[0].diameter_mm == 0.4
    assert group.diameter_mm / 2.0 < legs[1].diameter_mm < 0.8
    assert all(leg.is_connection_branch for leg in legs)
    assert tuple(leg.attachment_id for leg in legs) == (
        first.attachment_id,
        second.attachment_id,
    )
    assert routes[0].points[1] == refine_frame.origin
    origins = tuple(route.points[-1] for route in routes)
    assert all(
        ((point.x - 2.0) ** 2 + point.y**2) ** 0.5 + leg.diameter_mm / 2
        <= group.diameter_mm / 2 + 1e-7
        for point, leg in zip(origins, legs)
    )
    assert ((origins[0].x - origins[1].x) ** 2 + (origins[0].y - origins[1].y) ** 2) ** 0.5 >= (
        legs[0].diameter_mm + legs[1].diameter_mm
    ) / 2 - 1e-7


def test_connection_branches_match_packed_slots_to_shuffled_contacts(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Reorder only equal-size branch disks to avoid crossing a PCB contact row.
    """
    from cable_bundler.fusion.route_preview_parts import branch_layout
    from cable_bundler.fusion.route_preview_parts import solver as route_solver

    del addin_module
    guide = route_solver.ProfileFrame(
        Vector3(0.0, 0.0, 0.0),
        Vector3(0.0, 0.0, 1.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
    )
    packing = pack_connections(4.0, (1.0, 1.0, 1.0))
    assert packing is not None
    targets = (
        replace(guide, origin=Vector3(10.0, 0.0, 10.0)),
        replace(guide, origin=Vector3(-10.0, 0.0, 10.0)),
        replace(guide, origin=Vector3(0.0, 0.0, 10.0)),
    )

    assigned = branch_layout.assign_connection_packing(guide, packing, targets)
    expanded = branch_layout.expand_connection_packing(assigned, 4.0)
    fan_axis = branch_layout.connection_fan_axis(guide, targets)
    assert fan_axis is not None

    assert sorted((circle.x_mm, circle.y_mm) for circle in assigned) == sorted(
        (circle.x_mm, circle.y_mm) for circle in packing
    )
    assert assigned[1].x_mm < assigned[2].x_mm < assigned[0].x_mm
    route_ids = tuple(UUID(int=930 + index) for index in range(3))

    def branch_routes(circles: tuple[PackedConnection, ...]) -> tuple[RoutePreview, ...]:
        """
        Form contact routes through a short parallel lead at each packed cap.
        """
        return tuple(
            RoutePreview(
                route_id,
                str(index),
                tuple(
                    frame.origin
                    for frame in branch_layout.parallel_branch_lead(
                        (
                            target,
                            replace(
                                guide,
                                origin=Vector3(circle.x_mm, circle.y_mm, 0.0),
                            ),
                        ),
                        guide,
                        Vector3(0.0, 0.0, -1.0),
                        4.0,
                        circle.diameter_mm,
                        fan_axis,
                        10.0,
                    )
                ),
            )
            for index, (route_id, target, circle) in enumerate(zip(route_ids, targets, circles))
        )

    original_routes = tuple(
        RoutePreview(
            route_id,
            str(index),
            (target.origin, Vector3(circle.x_mm, circle.y_mm, 0.0)),
        )
        for index, (route_id, target, circle) in enumerate(zip(route_ids, targets, packing))
    )
    assert route_collisions(original_routes, route_ids, (1.0,) * 3)
    assigned_collisions = route_collisions(branch_routes(expanded), route_ids, (1.0,) * 3)
    assert not assigned_collisions, [item.clearance_shortfall_mm for item in assigned_collisions]
    faired = tuple(
        fair_route(
            route,
            (Vector3(0.0, 0.0, -1.0),) * len(route.points),
            minimum_bend_radius_mm=0.525,
            fixed_normal_indices=frozenset({len(route.points) - 1}),
        )
        for route in branch_routes(expanded)
    )
    assert not route_collisions(faired, route_ids, (1.0,) * 3)


def test_dense_contact_row_fairs_without_branch_collisions(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Spread twenty packed conductors into a PCB row without tube intersections.
    """
    from cable_bundler.fusion.route_preview_parts import branch_layout
    from cable_bundler.fusion.route_preview_parts import solver as route_solver

    del addin_module
    guide = route_solver.ProfileFrame(
        Vector3(0.0, 0.0, 0.0),
        Vector3(0.0, 0.0, 1.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
    )
    packing = pack_connections(4.0, (None,) * 20)
    assert packing is not None
    targets = tuple(
        replace(guide, origin=Vector3((index - 9.5) * 2.0, 0.0, 20.0)) for index in range(20)
    )
    assigned = branch_layout.assign_connection_packing(guide, packing, targets)
    assigned = branch_layout.expand_connection_packing(assigned, 4.0)
    fan_axis = branch_layout.connection_fan_axis(guide, targets)
    assert fan_axis is not None
    routes: list[RoutePreview] = []
    route_ids = tuple(UUID(int=1000 + index) for index in range(20))
    for index, (circle, target) in enumerate(zip(assigned, targets)):
        cap = replace(guide, origin=Vector3(circle.x_mm, circle.y_mm, 0.0))
        frames = branch_layout.parallel_branch_lead(
            (target, cap),
            guide,
            Vector3(0.0, 0.0, -1.0),
            4.0,
            circle.diameter_mm,
            fan_axis,
            19.0,
        )
        raw = RoutePreview(route_ids[index], str(index), tuple(frame.origin for frame in frames))
        routes.append(
            fair_route(
                raw,
                (Vector3(0.0, 0.0, -1.0),) * len(raw.points),
                minimum_bend_radius_mm=circle.diameter_mm * 0.525,
                fixed_normal_indices=frozenset({len(raw.points) - 1}),
            )
        )

    diameters = tuple(circle.diameter_mm for circle in assigned)
    assert not route_collisions(tuple(routes), route_ids, diameters)


def test_connection_branch_solver_uses_contact_order_and_checks_sibling_collisions(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Route one cable's split to its pads through reassigned parent-face slots.
    """
    from cable_bundler.fusion.route_preview_parts import frames as route_frames
    from cable_bundler.fusion.route_preview_parts import solver as route_solver

    del addin_module
    siblings = tuple(
        CableEndAttachment(
            AttachmentTargetKind.JOINT_ORIGIN,
            f"pad-{index}",
            f"Pad {index}",
            attachment_id=UUID(int=900 + index),
            visual_overrides=CableVisualOverrides(diameter_mm=0.25),
        )
        for index in range(3)
    )
    connection = replace(
        valid_harness.connections[0],
        attachment=siblings[0],
        additional_attachments=siblings[1:],
    )
    definition = replace(
        valid_harness,
        connections=(connection, valid_harness.connections[1]),
    )
    guide = route_solver.ProfileFrame(
        Vector3(0.0, 0.0, 0.0),
        Vector3(0.0, 0.0, 1.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
    )
    target_positions = (10.0, -10.0, 0.0)
    targets = {
        attachment.attachment_id: replace(guide, origin=Vector3(x, 0.0, 10.0))
        for attachment, x in zip(siblings, target_positions)
    }
    repair_calls: list[tuple[UUID, ...]] = []
    fixed_end_calls: list[tuple[bool, ...]] = []

    def capture_repair(
        routes: tuple[RoutePreview, ...],
        group_ids: tuple[UUID, ...],
        _diameters_mm: tuple[float, ...],
        _normals: tuple[tuple[Vector3, ...], ...],
        _transitions: tuple[tuple[TransitionLengths, ...], ...],
        _radii_mm: tuple[float, ...],
        _clearance_mm: float,
        **_options: Any,
    ) -> tuple[tuple[RoutePreview, ...], tuple[object, ...]]:
        """
        Confirm that sibling branches enter collision repair as distinct routes.
        """
        repair_calls.append(group_ids)
        fixed_end_calls.append(_options["fixed_end_normals"])
        return routes, ()

    monkeypatch.setitem(
        vars(route_solver),
        "connection_profile_frames",
        lambda _design, _connection, _cache: (guide,),
    )
    monkeypatch.setattr(
        route_frames,
        "connection_attachment_frame",
        lambda _design, _connection, attachment, _guide, _cache: targets[attachment.attachment_id],
    )
    monkeypatch.setitem(vars(route_solver), "fair_route", lambda route, *_args, **_kwargs: route)
    monkeypatch.setitem(vars(route_solver), "separate_route_collisions", capture_repair)

    routes, legs = route_solver._connection_branch_routes(
        object(),
        definition,
        {item.connection_id: item for item in definition.connections},
        {item.control_id: item for item in definition.controls},
        {},
        {},
        definition.auto_transition_preset.span_fraction,
        {
            (
                definition.cable_groups[0].cable_group_id,
                connection.connection_id,
            ): route_solver._BranchAnchor(Vector3(0.0, 0.0, 0.0), Vector3(0.0, 0.0, -1.0))
        },
    )

    assert len(routes) == len(legs) == 3
    assert tuple(leg.attachment_id for leg in legs) == tuple(
        attachment.attachment_id for attachment in siblings
    )
    assert routes[1].points[-1].x < routes[2].points[-1].x < routes[0].points[-1].x
    assert repair_calls == [tuple(route.cable_id for route in routes)]
    assert fixed_end_calls == [(True, True, True)]


def test_root_branch_anchors_follow_faired_main_route_endpoints(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Pair each divided end with the actual main-sweep cap and interior direction.
    """
    from cable_bundler.fusion.route_preview_parts import solver as route_solver

    del addin_module
    start = Vector3(1.0, 2.0, 3.0)
    end = Vector3(11.0, 2.0, 3.0)
    route = RoutePreview(
        UUID(int=501),
        "Main",
        (start, end),
        (CubicBezier(start, Vector3(4.0, 2.0, 3.0), Vector3(8.0, 2.0, 3.0), end),),
    )
    leg = CableGroupRouteLeg(
        route.cable_id,
        UUID(int=502),
        "Main",
        UUID(int=503),
        UUID(int=504),
        (),
        (),
    )

    anchors = route_solver._root_branch_anchors((leg,), (route,))

    assert anchors[leg.cable_group_id, leg.start_connection_id].origin == start
    assert anchors[leg.cable_group_id, leg.start_connection_id].interior.x > start.x
    assert anchors[leg.cable_group_id, leg.end_connection_id].origin == end
    assert anchors[leg.cable_group_id, leg.end_connection_id].interior.x < end.x
    flat_handles = replace(route, curves=(CubicBezier(start, start, end, end),))
    fallback = route_solver._root_branch_anchors((leg,), (flat_handles,))
    assert fallback[leg.cable_group_id, leg.start_connection_id].interior.x > start.x
    assert fallback[leg.cable_group_id, leg.end_connection_id].interior.x < end.x


def test_connection_refine_spine_uses_selected_external_branch(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Present the selected target-to-guide branch as the native refine-placement spine.
    """
    from cable_bundler.fusion import refine_graphics
    from cable_bundler.fusion.route_preview_parts import solver as route_solver

    del addin_module
    attachment = CableEndAttachment(
        AttachmentTargetKind.JOINT_ORIGIN,
        "target-token",
        "Target",
        attachment_id=UUID(int=93),
    )
    connection = replace(valid_harness.connections[0], attachment=attachment)
    definition = replace(
        valid_harness,
        connections=(connection, valid_harness.connections[1]),
    )
    guide = route_solver.ProfileFrame(
        Vector3(0.0, 0.0, 0.0),
        Vector3(0.0, 0.0, 1.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
    )
    target = replace(guide, origin=Vector3(0.0, 0.0, 10.0))
    refine_namespace = vars(refine_graphics)
    monkeypatch.setitem(
        refine_namespace,
        "connection_profile_frames",
        lambda _design, _connection, _cache: (guide,),
    )
    branch_frames = Mock(return_value=(target, guide))
    monkeypatch.setitem(refine_namespace, "connection_branch_route_frames", branch_frames)

    spine = refine_graphics.build_connection_spine(
        object(),
        definition,
        connection.connection_id,
        attachment.attachment_id,
    )

    assert spine.points == (target.origin, guide.origin)
    assert branch_frames.call_args.args[1:4] == (connection, attachment, guide)


def test_nested_connection_routes_from_child_target_to_parent_profile(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Continue a connection chain from each child target to its immediate parent.
    """
    from cable_bundler.fusion.route_preview_parts import frames as route_frames
    from cable_bundler.fusion.route_preview_parts import solver as route_solver

    del addin_module
    root = CableEndAttachment(
        AttachmentTargetKind.PROFILE,
        "root-profile",
        "Root",
        attachment_id=UUID(int=94),
    )
    child = CableEndAttachment(
        AttachmentTargetKind.JOINT_ORIGIN,
        "child-target",
        "Child",
        attachment_id=UUID(int=95),
        parent_attachment_id=root.attachment_id,
    )
    connection = replace(
        valid_harness.connections[0],
        attachment=root,
        additional_attachments=(child,),
    )
    definition = replace(
        valid_harness,
        connections=(connection, valid_harness.connections[1]),
    )
    guide = route_solver.ProfileFrame(
        Vector3(0.0, 0.0, 0.0),
        Vector3(0.0, 0.0, 1.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
    )
    targets = {
        root.attachment_id: replace(guide, origin=Vector3(0.0, 0.0, 5.0)),
        child.attachment_id: replace(guide, origin=Vector3(50.0, 0.0, 2.0)),
    }

    def attachment_frame(
        _design: object,
        _connection: Connection,
        attachment: CableEndAttachment,
        _guide: object,
        _cache: dict[str, route_solver.ProfileFrame],
    ) -> route_solver.ProfileFrame:
        """
        Return the deterministic frame assigned to one test attachment.
        """
        return targets[attachment.attachment_id]

    monkeypatch.setitem(
        vars(route_solver),
        "connection_profile_frames",
        lambda _design, _connection, _cache: (guide,),
    )
    monkeypatch.setattr(route_frames, "connection_attachment_frame", attachment_frame)
    monkeypatch.setitem(vars(route_solver), "connection_attachment_frame", attachment_frame)
    routes, legs = route_solver._connection_branch_routes(
        object(),
        definition,
        {item.connection_id: item for item in definition.connections},
        {},
        {},
        {},
        definition.auto_transition_preset.span_fraction,
    )

    assert len(routes) == 1
    parent_origin = targets[root.attachment_id].origin
    assert routes[0].points == (
        targets[child.attachment_id].origin,
        parent_origin,
    )
    assert dot(routes[0].curves[-1].derivative(1.0), Vector3(0.0, 0.0, -1.0)) > 0.0
    assert legs[0].attachment_id == child.attachment_id
    assert legs[0].diameter_mm == definition.cable_groups[0].diameter_mm
