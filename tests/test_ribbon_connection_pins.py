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


def test_branch_guide_uses_numbered_line_end_face(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Root branches begin at the matching lobe, not the ribbon centerline.
    """
    from cable_bundler.application import CableGroupRouteLeg
    from cable_bundler.fusion.route_preview_parts import ribbon_branches
    from cable_bundler.fusion.route_preview_parts.frames import ProfileFrame
    from cable_bundler.routing import CubicBezier, RoutePreview, Vector3

    del addin_module
    base = valid_harness.connections[0]
    target = CableEndAttachment(
        AttachmentTargetKind.SKETCH_POINT,
        "target",
        "Target",
        attachment_id=UUID(int=91),
        pin_number="3",
    )
    definition = replace(
        valid_harness,
        connections=(replace(base, attachment=target), valid_harness.connections[1]),
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
        base.connection_id,
        definition.connections[1].connection_id,
        (),
        (),
    )
    lane_end = Vector3(0.0, 4.0, 0.0)
    shape = SimpleNamespace(
        start_fit=object(),
        end_fit=object(),
        lanes=((start, end), (start, end), (lane_end, end)),
    )
    profile = ProfileFrame(
        start, Vector3(1.0, 0.0, 0.0), Vector3(0.0, 1.0, 0.0), Vector3(0.0, 0.0, 1.0)
    )
    monkeypatch.setitem(
        vars(ribbon_branches), "ribbon_route_shape", lambda *_args: SimpleNamespace(shape=shape)
    )
    monkeypatch.setitem(
        vars(ribbon_branches), "connection_profile_frames", lambda *_args: (profile,)
    )

    guides = ribbon_branches.ribbon_branch_guides(object(), definition, (leg,), (route,))

    assert guides[group.cable_group_id, base.connection_id, target.attachment_id].origin == lane_end


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


def test_generated_ribbon_branch_records_line_and_attachment_identity(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Branch solids remain separate and retain their source line in metadata.
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
        diameter_mm=group.diameter_mm,
        is_connection_branch=True,
        attachment_id=target.attachment_id,
    )
    attribute = SimpleNamespace(value=json.dumps({"connection_branches": []}))
    component = SimpleNamespace(attributes=SimpleNamespace(itemByName=lambda *_args: attribute))
    body = SimpleNamespace(name="", appearance=None)
    monkeypatch.setitem(vars(ribbon_branches), "_build_route_sweep", lambda *_args: (body, 10.6))
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

    ribbon_branches.build_ribbon_connection_branches(
        component,
        group,
        0,
        ((leg, route),),
        object(),
        definition,
        object(),
        ribbon_branches.FINALIZED_OUTPUT_MODE,
    )

    branch = json.loads(attribute.value)["connection_branches"][0]
    assert branch["attachment_id"] == str(target.attachment_id)
    assert branch["ribbon_line_number"] == 2
    assert branch["insulation_body_count"] == 1
    assert body.name.startswith("Cable Group 1 Line 2")
