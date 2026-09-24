"""
Regressions for geometry-validated route-solve reuse.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.application import CableGroupControlStep, CableGroupRouteLeg
from cable_bundler.domain import (
    AttachmentTargetKind,
    AutoTransitionPreset,
    CableEndAttachment,
    CableGroupDefinition,
    CableVisualOverrides,
    Connection,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    JunctionDefinition,
    PathwayEndpoint,
    RefineGeometry,
    StandaloneEndDefinition,
)
from cable_bundler.domain.model import InterpolationSettings
from cable_bundler.routing import (
    GateFrame,
    RefineFrame,
    RoutePreview,
    TransitionLengths,
    Vector3,
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


def test_multiple_connections_create_divided_clockface_branches(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Divide branch diameters and keep their guide origins inside the parent envelope.
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
    )

    group = definition.cable_groups[0]
    assert len(routes) == 2
    assert tuple(leg.diameter_mm for leg in legs) == (
        0.4,
        group.diameter_mm / 2.0,
    )
    assert all(leg.is_connection_branch for leg in legs)
    assert tuple(leg.attachment_id for leg in legs) == (
        first.attachment_id,
        second.attachment_id,
    )
    assert routes[0].points[1] == refine_frame.origin
    origins = tuple(route.points[-1] for route in routes)
    first_branch_radius = (group.diameter_mm - 0.4) / 2.0
    second_branch_radius = (group.diameter_mm - group.diameter_mm / 2.0) / 2.0
    assert tuple(
        coordinate for point in origins for coordinate in (point.x, point.y, point.z)
    ) == pytest.approx((0.0, first_branch_radius, 0.0, 0.0, -second_branch_radius, 0.0))


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


def test_undersized_gate_warns_through_public_product_solver(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Continue public product routing when cable envelopes exceed an aperture.
    """
    from cable_bundler.fusion import route_preview
    from cable_bundler.fusion.route_preview_parts import frames as route_frames
    from cable_bundler.fusion.route_preview_parts import solver as route_solver

    del addin_module
    pathway_id = valid_harness.pathways[0].pathway_id
    start_ids = tuple(UUID(int=100 + index) for index in range(1, 4))
    end_ids = tuple(UUID(int=200 + index) for index in range(1, 4))
    group_ids = tuple(UUID(int=300 + index) for index in range(1, 4))
    connections = tuple(
        connection
        for index, (start_id, end_id) in enumerate(zip(start_ids, end_ids), start=1)
        for connection in (
            Connection(start_id, f"Start {index}", f"start-{index}"),
            Connection(end_id, f"End {index}", f"end-{index}"),
        )
    )
    definition = replace(
        valid_harness,
        connections=connections,
        standalone_ends=tuple(
            end
            for start_id, end_id in zip(start_ids, end_ids)
            for end in (
                StandaloneEndDefinition(start_id, pathway_id, PathwayEndpoint.START),
                StandaloneEndDefinition(end_id, pathway_id, PathwayEndpoint.END),
            )
        ),
        cable_groups=tuple(
            CableGroupDefinition(group_id, (start_id, end_id), diameter_mm=3.0)
            for group_id, start_id, end_id in zip(group_ids, start_ids, end_ids)
        ),
    )

    def routing_frame(
        _design: object,
        _control: ControlStructure,
        control_id: UUID,
    ) -> GateFrame:
        """
        Return the exact undersized gate from the reported product regression.
        """
        return GateFrame(
            control_id,
            "Routing Gate 05",
            Vector3(0.0, 0.0, 10.0),
            Vector3(1.0, 0.0, 0.0),
            Vector3(0.0, 1.0, 0.0),
            2.98176,
        )

    def profile_frame(_design: object, token: str) -> route_solver.ProfileFrame:
        """
        Resolve deterministic synthetic terminal frames around the gate.
        """
        z = 0.0 if token.startswith("start-") else 20.0
        return route_solver.ProfileFrame(
            Vector3(0.0, 0.0, z),
            Vector3(0.0, 0.0, 1.0),
            Vector3(1.0, 0.0, 0.0),
            Vector3(0.0, 1.0, 0.0),
        )

    monkeypatch.setitem(vars(route_solver), "routing_frame", routing_frame)
    monkeypatch.setattr(route_frames, "_profile_frame", profile_frame)
    monkeypatch.setattr(route_solver, "_route_solve_cache", None)
    notices: list[str] = []

    routes, legs = route_preview.solve_cable_group_centerlines(object(), definition, notices)

    assert len(routes) == 3
    assert len(legs) == 3
    assert notices[0] == (
        "Routing Gate 05 cannot fit 3 cables inside its 5.96352 mm usable diameter. "
        "Cable spacing is preserved, so routes may extend outside the aperture."
    )


def test_reuses_solve_until_resolved_geometry_or_definition_changes(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Reuse Preview geometry for Generate while rejecting stale Fusion inputs.
    """
    from cable_bundler.fusion import route_preview
    from cable_bundler.fusion.route_preview_parts import frames as route_frames
    from cable_bundler.fusion.route_preview_parts import solver as route_solver

    del addin_module
    design = object()
    gate_z = [10.0]

    def routing_frame(_design: object, control: ControlStructure, control_id: UUID) -> RefineFrame:
        """
        Return the current synthetic control geometry.
        """
        return RefineFrame(
            control_id,
            control.name,
            Vector3(0.0, 0.0, gate_z[0]),
            Vector3(1.0, 0.0, 0.0),
            Vector3(0.0, 1.0, 0.0),
        )

    def profile_frame(_design: object, token: str) -> Any:
        """
        Return distinct synthetic start and end profile frames.
        """
        z = 0.0 if token == "fusion-start-token" else 20.0
        return route_solver.ProfileFrame(
            Vector3(0.0, 0.0, z),
            Vector3(0.0, 0.0, 1.0),
            Vector3(1.0, 0.0, 0.0),
            Vector3(0.0, 1.0, 0.0),
        )

    monkeypatch.setitem(vars(route_solver), "routing_frame", routing_frame)
    monkeypatch.setattr(route_frames, "_profile_frame", profile_frame)
    monkeypatch.setattr(route_solver, "_route_solve_cache", None)

    first = route_preview.solve_cable_group_centerlines(design, valid_harness)
    second = route_preview.solve_cable_group_centerlines(design, valid_harness)

    assert second == first
    assert second[0] is first[0]
    assert second[1] is first[1]

    gate_z[0] = 11.0
    moved = route_preview.solve_cable_group_centerlines(design, valid_harness)
    renamed = route_preview.solve_cable_group_centerlines(
        design,
        replace(valid_harness, name="Renamed Harness"),
    )
    relaxed = route_preview.solve_cable_group_centerlines(
        design,
        replace(
            valid_harness,
            auto_transition_preset=AutoTransitionPreset.LOOSE,
        ),
    )

    assert moved != first
    assert renamed == moved
    assert moved[0] is not first[0]
    assert renamed[0] is not moved[0]
    assert relaxed != renamed
    assert relaxed[0] is not renamed[0]


def test_end_and_junction_interpolation_reaches_every_fairing_stage(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve ordered end settings, reversed junction settings, and the global preset.
    """
    from cable_bundler.fusion import route_preview
    from cable_bundler.fusion.route_preview_parts import frames as route_frames
    from cable_bundler.fusion.route_preview_parts import solver as route_solver

    del addin_module
    start = replace(
        valid_harness.connections[0],
        additional_entity_tokens=("start-guide",),
        interpolation=InterpolationSettings(1.0, 2.0),
        member_interpolations=(InterpolationSettings(3.0, 4.0), None),
    )
    end = replace(
        valid_harness.connections[1],
        additional_entity_tokens=("end-guide",),
        interpolation=InterpolationSettings(5.0, 6.0),
        member_interpolations=(None, InterpolationSettings(7.0, 8.0)),
    )
    junction_control = replace(
        valid_harness.controls[0],
        interpolation=InterpolationSettings(9.0, 10.0),
    )
    start_refine = replace(
        junction_control,
        control_id=UUID(int=682),
        name="Start End Refine",
        kind=ControlKind.REFINE,
        entity_token="",
        interpolation=InterpolationSettings(11.0, 12.0),
        refine_geometry=RefineGeometry(
            (0.0, 0.0, 20.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            1.0,
        ),
    )
    end_refine = replace(
        junction_control,
        control_id=UUID(int=683),
        name="End End Refine",
        kind=ControlKind.REFINE,
        entity_token="",
        interpolation=InterpolationSettings(13.0, 14.0),
        refine_geometry=RefineGeometry(
            (0.0, 0.0, 40.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            1.0,
        ),
    )
    definition = replace(
        valid_harness,
        connections=(start, end),
        controls=(junction_control, start_refine, end_refine),
        junctions=(JunctionDefinition(UUID(int=681), "Junction", junction_control.control_id),),
        standalone_ends=(
            replace(
                valid_harness.standalone_ends[0], ordered_control_ids=(start_refine.control_id,)
            ),
            replace(valid_harness.standalone_ends[1], ordered_control_ids=(end_refine.control_id,)),
        ),
        auto_transition_preset=AutoTransitionPreset.RELAXED,
    )
    leg = CableGroupRouteLeg(
        UUID("68000000-0000-0000-0000-000000000001"),
        definition.cable_groups[0].cable_group_id,
        "Interpolation Leg",
        start.connection_id,
        end.connection_id,
        (CableGroupControlStep(junction_control.control_id, reversed=True),),
        (definition.pathways[0].pathway_id,),
    )
    profile_z = {
        start.entity_token: 0.0,
        "start-guide": 10.0,
        "end-guide": 50.0,
        end.entity_token: 60.0,
    }
    fairing_calls: list[tuple[tuple[TransitionLengths, ...], float]] = []
    collision_calls: list[tuple[tuple[tuple[TransitionLengths, ...], ...], float]] = []

    def routing_frame(
        _design: object,
        control: ControlStructure,
        control_id: UUID,
    ) -> RefineFrame:
        """
        Return one synthetic pathway or end-owned routing control.
        """
        z = {
            start_refine.control_id: 20.0,
            junction_control.control_id: 30.0,
            end_refine.control_id: 40.0,
        }[control_id]
        return RefineFrame(
            control_id,
            control.name,
            Vector3(0.0, 0.0, z),
            Vector3(1.0, 0.0, 0.0),
            Vector3(0.0, 1.0, 0.0),
        )

    def profile_frame(_design: object, token: str) -> Any:
        """
        Return an ordered synthetic end-profile frame.
        """
        return route_solver.ProfileFrame(
            Vector3(0.0, 0.0, profile_z[token]),
            Vector3(0.0, 0.0, 1.0),
            Vector3(1.0, 0.0, 0.0),
            Vector3(0.0, 1.0, 0.0),
        )

    def capture_fair_route(
        route: RoutePreview,
        _normals: tuple[Vector3, ...],
        transitions: tuple[TransitionLengths, ...],
        **options: Any,
    ) -> RoutePreview:
        """
        Record the complete transition sequence passed to initial fairing.
        """
        fairing_calls.append((transitions, options["auto_transition_fraction"]))
        return route

    def capture_collision_fairing(
        route_items: tuple[RoutePreview, ...],
        _group_ids: tuple[UUID, ...],
        _diameters_mm: tuple[float, ...],
        _normals: tuple[tuple[Vector3, ...], ...],
        transitions: tuple[tuple[TransitionLengths, ...], ...],
        _minimum_bend_radii_mm: tuple[float, ...],
        _clearance_mm: float,
        **options: Any,
    ) -> tuple[tuple[RoutePreview, ...], tuple[object, ...]]:
        """
        Record transition and preset inputs retained for collision repair.
        """
        collision_calls.append((transitions, options["auto_transition_fraction"]))
        return route_items, ()

    solver_namespace = vars(route_solver)
    monkeypatch.setitem(solver_namespace, "plan_cable_group_routes", lambda _definition: (leg,))
    monkeypatch.setitem(vars(route_solver), "routing_frame", routing_frame)
    monkeypatch.setattr(route_frames, "_profile_frame", profile_frame)
    monkeypatch.setitem(solver_namespace, "fair_route", capture_fair_route)
    monkeypatch.setitem(solver_namespace, "separate_route_collisions", capture_collision_fairing)
    monkeypatch.setattr(route_solver, "_route_solve_cache", None)

    routes, legs = route_preview.solve_cable_group_centerlines(object(), definition)

    expected_transitions = (
        TransitionLengths(3.0, 4.0),
        TransitionLengths(1.0, 2.0),
        TransitionLengths(11.0, 12.0),
        TransitionLengths(10.0, 9.0),
        TransitionLengths(14.0, 13.0),
        TransitionLengths(8.0, 7.0),
        TransitionLengths(6.0, 5.0),
    )
    assert legs == (leg,)
    assert tuple(point.z for point in routes[0].points) == (
        0.0,
        10.0,
        20.0,
        30.0,
        40.0,
        50.0,
        60.0,
    )
    assert fairing_calls == [(expected_transitions, AutoTransitionPreset.RELAXED.span_fraction)]
    assert collision_calls == [
        ((expected_transitions,), AutoTransitionPreset.RELAXED.span_fraction)
    ]
