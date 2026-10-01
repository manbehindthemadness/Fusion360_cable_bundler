"""
Pin numbering and line-capacity contracts for discrete ribbon connections.
"""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

import pytest

from cable_bundler.domain import (
    AttachmentTargetKind,
    CableEndAttachment,
    CableEndShape,
    CableGroupType,
    CableVisualOverrides,
    HarnessDefinition,
    validate_harness,
)
from cable_bundler.domain.ribbon_connections import assign_ribbon_pins
from tests.fusion_ui_support import _PaletteLifecycleModule


def _root(number: int, pin: str | None = None) -> CableEndAttachment:
    """
    Make a stable top-level connection without a Fusion target.
    """
    return CableEndAttachment(None, attachment_id=UUID(int=number), pin_number=pin)


def test_assigns_nearest_free_lines_once_and_reserves_numbered_pins() -> None:
    """
    Solve the whole end assignment, without changing existing pins or placeholders.
    """
    roots = (_root(1, "2"), _root(2), _root(3), _root(4))
    centers = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0), (30.0, 0.0, 0.0))
    targets = {roots[1].attachment_id: (29.0, 0.0, 0.0), roots[2].attachment_id: (1.0, 0.0, 0.0)}

    assert assign_ribbon_pins(roots, centers, targets) == {
        roots[1].attachment_id: "4",
        roots[2].attachment_id: "1",
    }


@pytest.mark.parametrize("pins", [("1", "1"), ("1", "4")])
def test_rejects_conflicting_or_out_of_range_line_pins(pins: tuple[str, str]) -> None:
    """
    Explicit pins must be corrected rather than silently reassigned.
    """
    with pytest.raises(ValueError, match="distinct existing lines"):
        assign_ribbon_pins(
            (_root(1, pins[0]), _root(2, pins[1])),
            ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
            {},
        )


def test_ribbon_validation_requires_numbered_targets_and_one_line_per_root(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Placeholders use capacity, while targeted roots need distinct valid pins.
    """
    base = valid_harness.connections[0]
    targeted = CableEndAttachment(
        AttachmentTargetKind.SKETCH_POINT,
        "target",
        "Target",
        attachment_id=UUID(int=1),
    )
    second = _root(2)
    connection = replace(base, attachment=targeted, additional_attachments=(second,))
    definition = replace(
        valid_harness,
        connections=(connection, valid_harness.connections[1]),
        standalone_ends=tuple(
            replace(end, shape=CableEndShape.OPEN) for end in valid_harness.standalone_ends
        ),
        cable_groups=(replace(valid_harness.cable_groups[0], group_type=CableGroupType.RIBBON),),
    )
    codes = {issue.code for issue in validate_harness(definition)}
    assert "ribbon_target_without_pin" in codes

    numbered = replace(targeted, pin_number="1")
    connection = replace(connection, attachment=numbered)
    assert (
        validate_harness(replace(definition, connections=(connection, definition.connections[1])))
        == ()
    )

    oversized = replace(second, visual_overrides=CableVisualOverrides(diameter_mm=0.5))
    invalid = replace(connection, additional_attachments=(oversized,))
    codes = {
        issue.code
        for issue in validate_harness(
            replace(definition, connections=(invalid, definition.connections[1]))
        )
    }
    assert "ribbon_root_diameter_override" in codes

    too_many = replace(
        connection,
        additional_attachments=(second, _root(3), _root(4)),
    )
    codes = {
        issue.code
        for issue in validate_harness(
            replace(definition, connections=(too_many, definition.connections[1]))
        )
    }
    assert "ribbon_connection_capacity_exceeded" in codes


@pytest.mark.parametrize("at_start", [True, False])
def test_branch_guide_uses_numbered_line_end_face_and_fitted_tangent(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
    at_start: bool,
) -> None:
    """
    Root branches meet the matching lobe with its actual terminal angle.
    """
    from cable_bundler.application import CableGroupRouteLeg
    from cable_bundler.fusion.route_preview_parts import ribbon_branches
    from cable_bundler.fusion.route_preview_parts.frames import ProfileFrame
    from cable_bundler.routing import CubicBezier, RibbonEndFit, RoutePreview, Vector3
    from cable_bundler.routing.geometry import difference, unit

    del addin_module
    base = valid_harness.connections[0 if at_start else 1]
    target = CableEndAttachment(
        AttachmentTargetKind.SKETCH_POINT,
        "target",
        "Target",
        attachment_id=UUID(int=91),
        pin_number="3",
    )
    definition = replace(
        valid_harness,
        connections=tuple(
            replace(connection, attachment=target)
            if connection.connection_id == base.connection_id
            else connection
            for connection in valid_harness.connections
        ),
        cable_groups=(replace(valid_harness.cable_groups[0], group_type=CableGroupType.RIBBON),),
    )
    start, end = Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0)
    route = RoutePreview(
        UUID(int=92), "Ribbon", (start, end), (CubicBezier(start, start, end, end),)
    )
    group = definition.cable_groups[0]
    leg = CableGroupRouteLeg(
        route.cable_id,
        group.cable_group_id,
        "Ribbon",
        definition.connections[0].connection_id,
        definition.connections[1].connection_id,
        (),
        (),
    )
    lane = (Vector3(0.0, 4.0, 0.0), Vector3(8.0, 5.0, 0.0), Vector3(10.0, 6.0, 0.0))
    half_diameter = group.diameter_mm / 2.0

    def fit(center: Vector3) -> RibbonEndFit:
        """
        Supply the exact line-three edge interval of a fitted guide.
        """
        return RibbonEndFit(
            (start, start, center),
            (Vector3(0.0, 0.0, 1.0),) * 3,
            (
                Vector3(center.x, center.y - 2.5 * group.diameter_mm, center.z),
                Vector3(center.x, center.y - 1.5 * group.diameter_mm, center.z),
                Vector3(center.x, center.y - half_diameter, center.z),
                Vector3(center.x, center.y + half_diameter, center.z),
            ),
            approach_normal=Vector3(1.0, 0.0, 0.0),
        )

    shape = SimpleNamespace(
        start_fit=fit(lane[0]), end_fit=fit(lane[-1]), lanes=((start, end), (start, end), lane)
    )
    profile = ProfileFrame(
        start, Vector3(0.0, 0.0, 1.0), Vector3(0.0, 1.0, 0.0), Vector3(1.0, 0.0, 0.0)
    )
    monkeypatch.setitem(
        vars(ribbon_branches), "ribbon_route_shape", lambda *_args: SimpleNamespace(shape=shape)
    )
    monkeypatch.setitem(
        vars(ribbon_branches), "connection_profile_frames", lambda *_args: (profile,)
    )

    guides = ribbon_branches.ribbon_branch_guides(object(), definition, (leg,), (route,))

    guide = guides[group.cable_group_id, base.connection_id, target.attachment_id]
    expected_center, inside = (lane[0], lane[1]) if at_start else (lane[-1], lane[-2])
    assert guide.origin == expected_center
    assert guide.normal == unit(difference(inside, expected_center))
    assert guide.ribbon_connection_diameter_mm == pytest.approx(0.9 * group.diameter_mm)
    assert guide.ribbon_terminal_tangent == ribbon_branches._terminal_lane_tangent(
        lane, at_start=at_start
    )
    assert guide.ribbon_terminal_tangent != guide.normal


def test_ribbon_terminal_tangent_uses_curvature_beyond_first_chord(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Capture the loft's initial turn rather than treating its first chord as tangent.
    """
    del addin_module
    from cable_bundler.fusion.route_preview_parts.ribbon_branches import _terminal_lane_tangent
    from cable_bundler.routing import Vector3
    from cable_bundler.routing.geometry import unit

    lane = (Vector3(0.0, 0.0, 0.0), Vector3(1.0, 0.0, 0.0), Vector3(1.0, 1.0, 0.0))

    assert _terminal_lane_tangent(lane, at_start=True) == unit(Vector3(1.5, -0.5, 0.0))


def test_fitted_ribbon_connection_diameter_uses_narrower_side(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    A fitted edge line cannot protrude beyond its asymmetric lobe.
    """
    del addin_module
    from cable_bundler.fusion.route_preview_parts.ribbon_branches import (
        _fitted_connection_diameter,
    )
    from cable_bundler.routing import Vector3

    diameter = _fitted_connection_diameter(
        Vector3(0.0, 0.0, 0.0),
        Vector3(-0.4, 0.0, 0.0),
        Vector3(0.6, 0.0, 0.0),
        1.0,
    )

    assert diameter == pytest.approx(0.72)


def test_ribbon_branch_terminal_tangent_changes_without_straightening_route(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Preserve the preceding curve and branch start while matching its lobe tangent.
    """
    del addin_module
    from cable_bundler.fusion.route_preview_parts.ribbon_branches import align_ribbon_branch_end
    from cable_bundler.routing import CubicBezier, RoutePreview, Vector3
    from cable_bundler.routing.geometry import dot, unit

    first = CubicBezier(
        Vector3(-20.0, 0.0, 0.0),
        Vector3(-17.0, 0.0, 0.0),
        Vector3(-13.0, 0.0, 0.0),
        Vector3(-10.0, 0.0, 0.0),
    )
    last = CubicBezier(
        first.end,
        Vector3(-7.0, 0.0, 0.0),
        Vector3(-3.0, 0.0, 0.0),
        Vector3(0.0, 0.0, 0.0),
    )
    route = RoutePreview(UUID(int=700), "Branch", (first.start, first.end, last.end), (first, last))
    tangent = Vector3(1.0, 0.25, 0.0)

    adjusted, aligned = align_ribbon_branch_end(route, tangent, 0.5)

    assert aligned
    assert adjusted.curves[0] == first
    assert adjusted.curves[-1].start == last.start
    assert adjusted.curves[-1].control_a == last.control_a
    assert adjusted.curves[-1].end == last.end
    assert adjusted.curves[-1].control_b != last.control_b
    assert dot(unit(adjusted.curves[-1].derivative(1.0)), unit(tangent)) == pytest.approx(1.0)


def test_ribbon_branch_keeps_original_when_end_bend_is_too_tight(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Do not replace a valid branch with an unsweepable cap correction.
    """
    del addin_module
    from cable_bundler.fusion.route_preview_parts.ribbon_branches import align_ribbon_branch_end
    from cable_bundler.routing import CubicBezier, RoutePreview, Vector3

    start = Vector3(-2.0, 0.0, 0.0)
    end = Vector3(0.0, 0.0, 0.0)
    curve = CubicBezier(start, Vector3(-1.5, 0.0, 0.0), Vector3(-0.5, 0.0, 0.0), end)
    route = RoutePreview(UUID(int=701), "Short branch", (start, end), (curve,))

    adjusted, aligned = align_ribbon_branch_end(route, Vector3(1.0, 1.0, 0.0), 2.0)

    assert not aligned
    assert adjusted is route


def test_ribbon_root_branch_keeps_fitted_tangent_when_parent_centerline_disagrees(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    A banked lobe's inward tangent wins over the ribbon centerline side test.
    """
    from cable_bundler.fusion.route_preview_parts import frames, solver
    from cable_bundler.fusion.route_preview_parts.frames import ProfileFrame
    from cable_bundler.routing import RoutePreview, Vector3, straight_route
    from cable_bundler.routing.geometry import dot, unit

    del addin_module
    target = CableEndAttachment(
        AttachmentTargetKind.SKETCH_POINT,
        "target",
        "Target",
        attachment_id=UUID(int=95),
        pin_number="1",
    )
    connection = replace(valid_harness.connections[0], attachment=target)
    group = replace(valid_harness.cable_groups[0], group_type=CableGroupType.RIBBON)
    definition = replace(
        valid_harness,
        connections=(connection, valid_harness.connections[1]),
        cable_groups=(group,),
    )
    guide = ProfileFrame(
        Vector3(0.0, 0.0, 0.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
        Vector3(0.0, 0.0, 1.0),
        ribbon_connection_diameter_mm=0.8,
        ribbon_terminal_tangent=Vector3(1.0, 0.1, 0.0),
    )
    contact = replace(guide, origin=Vector3(-10.0, 0.0, 0.0))
    monkeypatch.setitem(vars(solver), "connection_profile_frames", lambda *_args: (guide,))
    monkeypatch.setattr(frames, "connection_attachment_frame", lambda *_args: contact)
    tangents: list[tuple[Vector3, frozenset[int]]] = []

    def capture_fairing(
        route: RoutePreview, normals: tuple[Vector3, ...], *_args: object, **kwargs: object
    ) -> RoutePreview:
        """
        Record the terminal tangent passed to branch fairing.
        """
        fixed = kwargs["fixed_normal_indices"]
        assert isinstance(fixed, frozenset)
        tangents.append((normals[-1], fixed))
        return straight_route(route)

    monkeypatch.setitem(vars(solver), "fair_route", capture_fairing)
    routes, legs = solver._connection_branch_routes(
        object(),
        definition,
        {item.connection_id: item for item in definition.connections},
        {},
        {},
        {},
        definition.auto_transition_preset.span_fraction,
        {
            (group.cable_group_id, connection.connection_id): solver._BranchAnchor(
                guide.origin, Vector3(-1.0, 0.0, 0.0)
            )
        },
        ribbon_guides={
            (group.cable_group_id, connection.connection_id, target.attachment_id): guide
        },
    )

    assert len(routes) == 1
    assert tangents == [(guide.normal, frozenset({1}))]
    assert legs[0].diameter_mm == 0.8
    assert dot(
        unit(routes[0].curves[-1].derivative(1.0)), unit(guide.ribbon_terminal_tangent)
    ) == pytest.approx(1.0)


def test_target_numbering_is_persisted_and_not_recomputed(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Refit a newly connected root only once; later target movement preserves its pin.
    """
    from cable_bundler.fusion import ribbon_connections
    from cable_bundler.fusion.route_preview_parts.frames import ProfileFrame
    from cable_bundler.routing import Vector3

    del addin_module
    target = CableEndAttachment(
        AttachmentTargetKind.SKETCH_POINT,
        "target",
        "Target",
        attachment_id=UUID(int=101),
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(valid_harness.connections[0], attachment=target),
            valid_harness.connections[1],
        ),
        cable_groups=(replace(valid_harness.cable_groups[0], group_type=CableGroupType.RIBBON),),
    )
    profile = ProfileFrame(
        Vector3(0.0, 0.0, 0.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
        Vector3(0.0, 0.0, 1.0),
    )
    fit = SimpleNamespace(
        centers=(
            Vector3(0.0, 0.0, 0.0),
            Vector3(0.0, 2.0, 0.0),
            Vector3(0.0, 4.0, 0.0),
        )
    )
    monkeypatch.setitem(
        vars(ribbon_connections), "connection_profile_frames", lambda *_args: (profile,)
    )
    monkeypatch.setitem(vars(ribbon_connections), "_guide_fit", lambda *_args: (fit, object()))
    monkeypatch.setitem(
        vars(ribbon_connections),
        "connection_attachment_frame",
        lambda *_args: replace(profile, origin=Vector3(0.0, 3.9, 0.0)),
    )

    numbered = ribbon_connections.number_ribbon_connections(object(), definition)

    assert numbered.connections[0].attachment.pin_number == "3"
    monkeypatch.setitem(
        vars(ribbon_connections),
        "_guide_fit",
        lambda *_args: pytest.fail("A saved pin must not be refitted."),
    )
    assert ribbon_connections.number_ribbon_connections(object(), numbered) == numbered


@pytest.mark.parametrize("fitted_fraction", [1.0, 0.75])
def test_generated_ribbon_branch_records_line_and_attachment_identity(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
    fitted_fraction: float,
) -> None:
    """
    Use the surface-fitted diameter in the sweep, conductor, and metadata.
    """
    from cable_bundler.application import CableGroupRouteLeg
    from cable_bundler.fusion import cable_solids
    from cable_bundler.fusion.cable_solid_parts import ribbon_branches
    from cable_bundler.routing import CubicBezier, RoutePreview, Vector3

    del addin_module
    target = CableEndAttachment(
        AttachmentTargetKind.SKETCH_POINT,
        "target",
        "Target",
        attachment_id=UUID(int=111),
        pin_number="2",
    )
    group = replace(valid_harness.cable_groups[0], group_type=CableGroupType.RIBBON)
    definition = replace(
        valid_harness,
        connections=(
            replace(valid_harness.connections[0], attachment=target),
            valid_harness.connections[1],
        ),
        cable_groups=(group,),
    )
    start, end = Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0)
    route = RoutePreview(
        UUID(int=112), "Branch", (start, end), (CubicBezier(start, start, end, end),)
    )
    leg = CableGroupRouteLeg(
        route.cable_id,
        group.cable_group_id,
        "Branch",
        definition.connections[0].connection_id,
        None,
        (),
        (),
        diameter_mm=group.diameter_mm * 0.9,
        is_connection_branch=True,
        attachment_id=target.attachment_id,
    )
    attribute = SimpleNamespace(value=json.dumps({"connection_branches": []}))
    component = SimpleNamespace(attributes=SimpleNamespace(itemByName=lambda *_args: attribute))
    body = SimpleNamespace(name="", appearance=None)
    sweep_diameters: list[float] = []

    def capture_sweep(*args: object) -> tuple[SimpleNamespace, float]:
        """
        Record the physical diameter supplied to the Fusion sweep.
        """
        assert isinstance(args[2], float)
        sweep_diameters.append(args[2])
        return body, 10.6

    ribbon_body = object()
    end_plane = object()
    fit_calls: list[tuple[object, object]] = []

    def fit_overlap(
        actual_ribbon: object,
        _route: RoutePreview,
        plane: object,
        cap: float,
        _transform: object,
    ) -> float:
        """
        Supply the measured branch size while checking its owning ribbon.
        """
        fit_calls.append((actual_ribbon, plane))
        return cap * fitted_fraction

    monkeypatch.setitem(vars(ribbon_branches), "_build_route_sweep", capture_sweep)
    monkeypatch.setitem(vars(ribbon_branches), "fitted_ribbon_overlap_diameter", fit_overlap)
    monkeypatch.setitem(
        vars(ribbon_branches),
        "split_route_for_pullback",
        lambda route_to_split, _distance: SimpleNamespace(
            insulation=route_to_split, pullback=None, pullback_length_mm=0.0
        ),
    )
    monkeypatch.setitem(
        vars(ribbon_branches), "route_in_component_space", lambda route, _transform: route
    )
    monkeypatch.setitem(vars(ribbon_branches), "cable_appearance", lambda *_args: object())
    monkeypatch.setattr(cable_solids, "_attachment_weld_endpoint", lambda *_args: None)

    notices: list[str] = []
    ribbon_branches.build_ribbon_connection_branches(
        component,
        group,
        0,
        ((leg, route),),
        object(),
        definition,
        object(),
        ribbon_branches.FINALIZED_OUTPUT_MODE,
        ribbon_body,
        {definition.connections[0].connection_id: end_plane},
        notices,
    )

    branch = json.loads(attribute.value)["connection_branches"][0]
    assert branch["attachment_id"] == str(target.attachment_id)
    assert branch["ribbon_line_number"] == 2
    expected_diameter = group.diameter_mm * 0.9 * fitted_fraction
    assert branch["diameter_mm"] == pytest.approx(expected_diameter)
    assert branch["pullback_diameter_mm"] == pytest.approx(expected_diameter * 0.75)
    assert branch["insulation_body_count"] == 1
    assert body.name.startswith("Cable Group 1 Line 2")
    assert sweep_diameters == [pytest.approx(expected_diameter)]
    assert fit_calls == [(ribbon_body, end_plane)]
    assert bool(notices) is (fitted_fraction < 1.0)

    oversized = replace(
        target,
        visual_overrides=CableVisualOverrides(conductor_diameter_mm=group.diameter_mm * 0.95),
    )
    oversized_definition = replace(
        definition,
        connections=(
            replace(definition.connections[0], attachment=oversized),
            definition.connections[1],
        ),
    )
    monkeypatch.setitem(
        vars(ribbon_branches),
        "split_route_for_pullback",
        lambda route_to_split, _distance: SimpleNamespace(
            insulation=route_to_split,
            pullback=route_to_split,
            pullback_length_mm=1.0,
        ),
    )
    with pytest.raises(ValueError, match="wider than its fitted insulation"):
        ribbon_branches.build_ribbon_connection_branches(
            component,
            group,
            0,
            ((leg, route),),
            object(),
            oversized_definition,
            object(),
            ribbon_branches.FINALIZED_OUTPUT_MODE,
            ribbon_body,
            {definition.connections[0].connection_id: end_plane},
        )


@pytest.mark.parametrize("fit_limit_mm", [0.9, 0.62])
def test_ribbon_overlap_finds_largest_surface_fitting_diameter(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    fit_limit_mm: float,
) -> None:
    """
    A surface fit changes the final diameter while retaining the cap as its maximum.
    """
    del addin_module
    from cable_bundler.fusion.cable_solid_parts import ribbon_overlap
    from cable_bundler.routing import CubicBezier, RoutePreview, Vector3

    start, end = Vector3(0.0, 0.0, 0.0), Vector3(1.0, 0.0, 0.0)
    route = RoutePreview(
        UUID(int=113), "Root", (start, end), (CubicBezier(start, start, end, end),)
    )
    manager = object()
    monkeypatch.setitem(
        vars(ribbon_overlap.adsk.fusion),
        "TemporaryBRepManager",
        SimpleNamespace(get=lambda: manager),
    )
    probed: list[float] = []

    def escapes(
        actual_manager: object,
        _body: object,
        _route: RoutePreview,
        _plane: object,
        diameter_mm: float,
        _transform: object,
    ) -> bool:
        """
        Model a generated ribbon boundary with a known round clearance.
        """
        assert actual_manager is manager
        probed.append(diameter_mm)
        return diameter_mm > fit_limit_mm

    monkeypatch.setitem(vars(ribbon_overlap), "_overlap_escapes_ribbon", escapes)
    fitted = ribbon_overlap.fitted_ribbon_overlap_diameter(object(), route, object(), 0.9, object())

    assert fit_limit_mm - 0.005 <= fitted <= fit_limit_mm
    assert probed[0] == 0.9
    assert len(probed) == (1 if fit_limit_mm == 0.9 else 10)


def test_ribbon_overlap_rejects_an_end_without_circular_clearance(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Never generate an exposed root when even the minimum candidate protrudes.
    """
    del addin_module
    from cable_bundler.fusion.cable_solid_parts import ribbon_overlap
    from cable_bundler.routing import CubicBezier, RoutePreview, Vector3

    start, end = Vector3(0.0, 0.0, 0.0), Vector3(1.0, 0.0, 0.0)
    route = RoutePreview(
        UUID(int=114), "Root", (start, end), (CubicBezier(start, start, end, end),)
    )
    monkeypatch.setitem(
        vars(ribbon_overlap.adsk.fusion),
        "TemporaryBRepManager",
        SimpleNamespace(get=lambda: object()),
    )
    monkeypatch.setitem(vars(ribbon_overlap), "_overlap_escapes_ribbon", lambda *_args: True)

    with pytest.raises(ValueError, match="no usable circular connection overlap"):
        ribbon_overlap.fitted_ribbon_overlap_diameter(object(), route, object(), 0.9, object())


def test_ribbon_overlap_probes_exact_generated_tail(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The surface test uses the sweep's half-diameter extension and inward clip.
    """
    del addin_module
    from cable_bundler.fusion.cable_solid_parts import ribbon_overlap
    from cable_bundler.routing import CubicBezier, RoutePreview, Vector3

    start, end = Vector3(0.0, 0.0, 0.0), Vector3(2.0, 0.0, 0.0)
    route = RoutePreview(
        UUID(int=115), "Root", (start, end), (CubicBezier(start, start, end, end),)
    )
    cylinder = SimpleNamespace(isValid=True, volume=0.01)
    inside_box = object()
    ribbon_body = object()
    operations: list[tuple[object, object]] = []
    cylinder_args: list[tuple[Vector3, float, Vector3, float]] = []

    class FakeManager:
        """
        Record temporary construction and the two ordered Boolean operations.
        """

        def createCylinderOrCone(
            self, point_a: Vector3, radius_a: float, point_b: Vector3, radius_b: float
        ) -> SimpleNamespace:
            """
            Return one temporary overlap cylinder.
            """
            cylinder_args.append((point_a, radius_a, point_b, radius_b))
            return cylinder

        def booleanOperation(self, target: object, tool: object, operation: object) -> bool:
            """
            Simulate a tiny escaped remainder after the ribbon subtraction.
            """
            assert target is cylinder
            operations.append((tool, operation))
            if tool is ribbon_body:
                cylinder.volume = 0.002
            return True

    monkeypatch.setitem(
        vars(ribbon_overlap.adsk.fusion),
        "BooleanTypes",
        SimpleNamespace(IntersectionBooleanType="intersection", DifferenceBooleanType="difference"),
    )
    monkeypatch.setitem(vars(ribbon_overlap), "fusion_point", lambda point, _transform: point)
    monkeypatch.setitem(vars(ribbon_overlap), "_inside_end_box", lambda *_args: inside_box)

    escaped = ribbon_overlap._overlap_escapes_ribbon(
        FakeManager(), ribbon_body, route, object(), 0.8, object()
    )

    assert escaped
    assert cylinder_args == [(end, 0.04, Vector3(2.4, 0.0, 0.0), 0.04)]
    assert operations == [(inside_box, "intersection"), (ribbon_body, "difference")]


def test_ribbon_overlap_clip_follows_a_remote_guide_location(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A sketch origin far from its guide must not place the clip away from the branch.
    """
    del addin_module
    from cable_bundler.fusion.cable_solid_parts import ribbon_overlap
    from cable_bundler.fusion.ribbon_geometry import RibbonGuidePlane
    from cable_bundler.routing import Vector3

    captured_centers: list[Vector3] = []

    class FakeDirection:
        """
        Supply the normalization operation used by Fusion box directions.
        """

        def normalize(self) -> bool:
            """
            Accept a nonzero direction for this geometry placement test.
            """
            return True

    def create_box(center: Vector3, *_args: object) -> object:
        """
        Record the location of the inward clipping volume.
        """
        captured_centers.append(center)
        return object()

    monkeypatch.setitem(
        vars(ribbon_overlap.adsk.core),
        "Vector3D",
        SimpleNamespace(create=lambda *_args: FakeDirection()),
    )
    monkeypatch.setitem(
        vars(ribbon_overlap.adsk.core),
        "OrientedBoundingBox3D",
        SimpleNamespace(create=create_box),
    )
    monkeypatch.setitem(vars(ribbon_overlap), "fusion_point", lambda point, _transform: point)
    manager = SimpleNamespace(createBox=lambda _box: object())
    plane = RibbonGuidePlane(Vector3(0.0, 0.0, 0.0), Vector3(0.0, 0.0, 1.0))

    ribbon_overlap._inside_end_box(
        manager, plane, Vector3(100.0, 0.0, 0.0), Vector3(0.0, 0.0, 1.0), 0.8, object()
    )

    assert captured_centers == [Vector3(100.0, 0.0, 5.0)]
