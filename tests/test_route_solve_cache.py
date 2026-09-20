"""
Regressions for geometry-validated route-solve reuse.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import UUID

import pytest

from cable_bundler.application import CableGroupControlStep, CableGroupRouteLeg
from cable_bundler.domain import (
    AutoTransitionPreset,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    JunctionDefinition,
    RefineGeometry,
)
from cable_bundler.domain.model import InterpolationSettings
from cable_bundler.routing import (
    CableRouteInput,
    GateFrame,
    RefineFrame,
    RoutePreview,
    TransitionLengths,
    Vector3,
)
from tests.fusion_ui_support import _PaletteLifecycleModule


def test_undersized_gate_warns_and_retains_route_crossings(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Continue product routing when cable envelopes exceed an aperture.
    """
    from cable_bundler.fusion.route_preview_parts import solver as route_solver

    del addin_module
    origin = Vector3(0.0, 0.0, 0.0)
    cables = tuple(
        CableRouteInput(
            UUID(int=index),
            f"Group {index}",
            origin,
            origin,
            3.0,
        )
        for index in range(1, 4)
    )
    gate = GateFrame(
        UUID(int=10),
        "Routing Gate 05",
        origin,
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
        2.98176,
    )
    notices: list[str] = []

    crossings = route_solver._place_control_crossings(cables, gate, 0.0, (), notices)

    assert len(crossings) == 3
    assert notices == [
        "Routing Gate 05 cannot fit 3 cables inside its 5.96352 mm usable diameter. "
        "Cable spacing is preserved, so routes may extend outside the aperture."
    ]


def test_reuses_solve_until_resolved_geometry_or_definition_changes(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Reuse Preview geometry for Generate while rejecting stale Fusion inputs.
    """
    from cable_bundler.fusion import route_preview
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

    monkeypatch.setattr(route_solver, "routing_frame", routing_frame)
    monkeypatch.setattr(route_solver, "_profile_frame", profile_frame)
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

    monkeypatch.setattr(
        "cable_bundler.fusion.route_preview_parts.solver.plan_cable_group_routes",
        lambda _definition: (leg,),
    )
    monkeypatch.setattr(route_solver, "routing_frame", routing_frame)
    monkeypatch.setattr(route_solver, "_profile_frame", profile_frame)
    monkeypatch.setattr(
        "cable_bundler.fusion.route_preview_parts.solver.fair_route",
        capture_fair_route,
    )
    monkeypatch.setattr(
        "cable_bundler.fusion.route_preview_parts.solver.separate_route_collisions",
        capture_collision_fairing,
    )
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
