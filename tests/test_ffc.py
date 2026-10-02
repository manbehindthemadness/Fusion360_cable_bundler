"""
Verify persisted FFC settings and contact-pitch sizing rules.
"""

from __future__ import annotations

import json
from dataclasses import replace
from importlib import import_module
from types import SimpleNamespace
from uuid import UUID

import pytest

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
    RibbonGeometryType,
    dumps,
    loads,
)
from cable_bundler.domain.ffc import FfcDimensions, resolve_ffc_dimensions
from cable_bundler.routing import Vector3
from tests.fusion_ui_support import _PaletteLifecycleModule


def test_auto_trace_width_uses_narrowest_measured_contact_and_point_fallback() -> None:
    """
    Keep all traces within the narrowest first-end contact.
    """
    measured = resolve_ffc_dimensions(1.0, (0.75, 0.6, 0.9), None, None)
    assert (measured.trace_width_mm, measured.spacing_mm) == pytest.approx((0.6, 0.4))
    missing = resolve_ffc_dimensions(1.0, (None, 0.95), None, None)
    assert (missing.trace_width_mm, missing.spacing_mm) == pytest.approx((0.8, 0.2))
    capped = resolve_ffc_dimensions(1.0, (1.2, 1.1), None, None)
    assert (capped.trace_width_mm, capped.spacing_mm) == pytest.approx((0.98, 0.02))


def test_explicit_trace_values_must_fill_exact_pitch() -> None:
    """
    An explicit width or gap determines Auto; incompatible pairs fail.
    """
    width = resolve_ffc_dimensions(1.0, (None, None), 0.6, None)
    gap = resolve_ffc_dimensions(1.0, (None, None), None, 0.4)
    assert width == gap
    with pytest.raises(ValueError, match="sum to the contact pitch"):
        resolve_ffc_dimensions(1.0, (None, None), 0.6, 0.3)
    with pytest.raises(ValueError, match="sum to the contact pitch"):
        resolve_ffc_dimensions(1.0, (None, None), 1.1, None)


def test_ffc_requires_two_lines_and_solid_body(valid_harness: HarnessDefinition) -> None:
    """
    The model cannot represent a one-line or Split FFC.
    """
    original = valid_harness.cable_groups[0]
    with pytest.raises(ValueError, match="at least two"):
        replace(
            original,
            group_type=CableGroupType.RIBBON,
            ribbon_geometry=RibbonGeometryType.FFC,
            ribbon_body_type=RibbonBodyType.SOLID,
            ribbon_lines=1,
        )
    with pytest.raises(ValueError, match="Solid"):
        replace(
            original,
            group_type=CableGroupType.RIBBON,
            ribbon_geometry=RibbonGeometryType.FFC,
        )
    dormant = replace(
        original,
        group_type=CableGroupType.RIBBON,
        ribbon_geometry=RibbonGeometryType.FFC,
        ribbon_body_type=RibbonBodyType.SOLID,
        diameter_mm=0.1,
        conductor_diameter_mm=0.5,
    )
    with pytest.raises(ValueError, match="conductor diameter"):
        replace(dormant, ribbon_geometry=RibbonGeometryType.DISCRETE)


def test_ffc_fields_round_trip_and_schema_39_migrates_to_solid(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Retain explicit trace sizes and adopt prior deferred FFC settings.
    """
    group = replace(
        valid_harness.cable_groups[0],
        group_type=CableGroupType.RIBBON,
        ribbon_geometry=RibbonGeometryType.FFC,
        ribbon_body_type=RibbonBodyType.SOLID,
        trace_width_mm=0.6,
        trace_spacing_mm=0.4,
    )
    definition = replace(valid_harness, cable_groups=(group,))
    assert loads(dumps(definition)).cable_groups[0] == group
    legacy = json.loads(dumps(definition))
    legacy["schema_version"] = 39
    legacy_group = legacy["cable_groups"][0]
    legacy_group["ribbon_body_type"] = "split"
    del legacy_group["trace_width_mm"]
    del legacy_group["trace_spacing_mm"]
    migrated = loads(json.dumps(legacy)).cable_groups[0]
    assert migrated.ribbon_body_type is RibbonBodyType.SOLID
    assert migrated.trace_width_mm is None
    assert migrated.trace_spacing_mm is None


def test_ffc_contact_geometry_measures_first_end_outlines(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Trace Auto width follows contact outlines along the ordered bank axis.
    """
    module = import_module("cable_bundler.fusion.ffc_dimensions")
    roots = tuple(
        CableEndAttachment(
            AttachmentTargetKind.SKETCH_POINT,
            f"contact-{index}",
            f"Contact {index}",
            attachment_id=UUID(int=700 + index),
            pin_number=str(index),
        )
        for index in range(1, 4)
    )
    first = replace(
        valid_harness.connections[0], attachment=roots[0], additional_attachments=roots[1:]
    )
    contacts = tuple(
        InterfaceContact(UUID(int=800 + index), root.target_kind, root.entity_token)
        for index, root in enumerate(roots)
    )
    interface = InterfaceDefinition(
        UUID(int=900),
        "Contact bank",
        (InterfaceTarget(InterfaceTargetKind.OCCURRENCE, "interface"),),
        contacts,
    )
    group = replace(
        valid_harness.cable_groups[0],
        group_type=CableGroupType.RIBBON,
        ribbon_geometry=RibbonGeometryType.FFC,
        ribbon_body_type=RibbonBodyType.SOLID,
    )
    definition = replace(
        valid_harness,
        connections=(first, *valid_harness.connections[1:]),
        cable_groups=(group,),
        interfaces=(interface,),
    )
    monkeypatch.setitem(vars(module), "connection_profile_frames", lambda *_args: (object(),))
    monkeypatch.setitem(
        vars(module),
        "connection_attachment_frame",
        lambda _design, _connection, root, _guide, _cache: SimpleNamespace(
            origin=Vector3(float(int(root.pin_number) - 1), 0.0, 0.0)
        ),
    )
    monkeypatch.setitem(
        vars(module),
        "project_interface_contact",
        lambda _design, contact: {
            "loops": [
                [
                    [float(int(contact.entity_token[-1]) - 1) - 0.3, 0.0, 0.0],
                    [float(int(contact.entity_token[-1]) - 1) + 0.3, 0.0, 0.0],
                ]
            ]
        },
    )
    dimensions = module.ffc_dimensions(object(), definition, group)
    assert dimensions.pitch_mm == pytest.approx(1.0)
    assert dimensions.trace_width_mm == pytest.approx(0.6)
    assert dimensions.spacing_mm == pytest.approx(0.4)


@pytest.mark.parametrize("line_count", [1, 3])
@pytest.mark.parametrize(("trace_width", "spacing"), [(0.6, 0.4), (0.8, 0.2), (0.2, 0.8)])
def test_ffc_section_keeps_flat_traces_inside_overall_thickness(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    line_count: int,
    trace_width: float,
    spacing: float,
) -> None:
    """
    Keep flat per-trace lands separated from web faces by tiny V notches.
    """
    builder = import_module("cable_bundler.fusion.cable_solid_parts.ribbon_builder")
    monkeypatch.setitem(vars(builder), "fusion_point", lambda point, _transform: point)
    edges: list[tuple[Vector3, Vector3]] = []
    junctions: list[Vector3] = []
    sketch = SimpleNamespace(
        modelToSketchSpace=lambda point: point,
        sketchPoints=SimpleNamespace(add=lambda point: junctions.append(point) or point),
        sketchCurves=SimpleNamespace(
            sketchLines=SimpleNamespace(
                addByTwoPoints=lambda left, right: edges.append((left, right)) or object()
            ),
        ),
    )
    station = builder.SolidRibbonSection(
        tuple(Vector3(index - (line_count - 1) / 2, 0, 0) for index in range(line_count)),
        Vector3(0, 0, 1),
        Vector3(1, 0, 0),
        0.6,
    )
    dimensions = resolve_ffc_dimensions(1.0, (None,) * line_count, trace_width, spacing)
    builder._draw_ffc_section(sketch, station, Vector3(0, 1, 0), 0.2, dimensions, None)
    assert len(junctions) == 12 * line_count + 4
    assert len(edges) == len(junctions)
    assert all(left[1] is right[0] for left, right in zip(edges, (*edges[1:], edges[0])))
    top_lands = [
        right.x - left.x
        for left, right in edges
        if left.y == right.y == 0.1 and right.x - left.x == pytest.approx(trace_width)
    ]
    assert len(top_lands) == line_count
    notch_half_width = min(trace_width, spacing) * 0.03
    top_webs = [
        right.x - left.x
        for left, right in edges
        if left.y == right.y == 0.1
        and right.x - left.x == pytest.approx(spacing - 4.0 * notch_half_width)
    ]
    assert len(top_webs) == line_count - 1
    assert sum(left.y == right.y == -0.1 for left, right in edges) == 2 * line_count + 1
    assert sum(corner.y == pytest.approx(0.09) for corner in junctions) == 2 * line_count
    assert sum(corner.y == pytest.approx(-0.09) for corner in junctions) == 2 * line_count
    assert all(-0.1 <= corner.y <= 0.1 for corner in junctions)


def test_ffc_colors_only_the_top_and_bottom_of_each_trace(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Keep spacing webs, notch slopes, and outer edges in the ribbon base color.
    """
    del addin_module
    builder = import_module("cable_bundler.fusion.cable_solid_parts.ribbon_builder")
    solid = import_module("cable_bundler.fusion.solid_ribbon")
    station = solid.SolidRibbonSection(
        (Vector3(0.0, 0.0, 0.0), Vector3(1.0, 0.0, 0.0), Vector3(2.0, 0.0, 0.0)),
        Vector3(0.0, 0.0, 1.0),
        Vector3(1.0, 0.0, 0.0),
        0.6,
    )
    plan = solid.SolidRibbonPlan((station,), (), ((), ()), ((), ()), ())
    dimensions = resolve_ffc_dimensions(1.0, (None,) * 3, 0.6, 0.4)

    for lane in range(3):
        for height in (-0.1, 0.1):
            sample = Vector3(float(lane), height, 0.0)
            assert builder._ffc_trace_land_lane(sample, plan, dimensions, 0.2) == lane

    for sample in (
        Vector3(0.5, 0.1, 0.0),  # upper spacing web
        Vector3(1.5, -0.1, 0.0),  # lower spacing web
        Vector3(0.33, 0.09, 0.0),  # sloped notch outside the land
        Vector3(-0.5, 0.0, 0.0),  # outer edge
        Vector3(1.0, 0.0, 0.0),  # flat end cap
    ):
        assert builder._ffc_trace_land_lane(sample, plan, dimensions, 0.2) is None

    single_station = replace(station, centers=(station.centers[1],))
    single_plan = replace(plan, sections=(single_station,))
    assert builder._ffc_trace_land_lane(Vector3(1.0, 0.1, 0.0), single_plan, dimensions, 0.2) == 0
    assert (
        builder._ffc_trace_land_lane(Vector3(1.0, 0.0, 0.0), single_plan, dimensions, 0.2) is None
    )


def test_ffc_single_trace_joins_sparse_station_pairs(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reuse the Solid route stations when one full-lane Fusion loft is invalid.
    """
    del addin_module
    builder = import_module("cable_bundler.fusion.cable_solid_parts.ribbon_builder")
    solid = import_module("cable_bundler.fusion.solid_ribbon")
    stations = tuple(
        solid.SolidRibbonSection(
            (Vector3(float(index), 0.0, 0.0),),
            Vector3(0.0, 0.0, 1.0),
            Vector3(1.0, 0.0, 0.0),
            0.6,
        )
        for index in range(40)
    )
    plan = solid.SolidRibbonPlan(stations, (), ((), ()), ((), ()), ())
    new_body, join = object(), object()
    monkeypatch.setitem(
        vars(builder.adsk.fusion),
        "FeatureOperations",
        SimpleNamespace(NewBodyFeatureOperation=new_body, JoinFeatureOperation=join),
    )
    operations: list[object] = []
    profiles: list[list[int]] = []
    features: list[SimpleNamespace] = []

    def create_input(operation: object) -> SimpleNamespace:
        """
        Record the loft operation and its two source profiles.
        """
        operations.append(operation)
        section_profiles: list[int] = []
        profiles.append(section_profiles)
        return SimpleNamespace(loftSections=SimpleNamespace(add=section_profiles.append))

    def add_loft(_loft_input: object) -> SimpleNamespace:
        """
        Simulate a successful Join into the same solid body.
        """
        feature = SimpleNamespace()
        features.append(feature)
        return feature

    body = SimpleNamespace(isSolid=True, volume=1.0)
    component = SimpleNamespace(
        bRepBodies=SimpleNamespace(count=1, item=lambda _index: body),
        features=SimpleNamespace(
            loftFeatures=SimpleNamespace(createInput=create_input, add=add_loft)
        ),
    )

    def add_section(
        _component: object,
        station: solid.SolidRibbonSection,
        _thickness_mm: float,
        _transform: object,
        _ffc: FfcDimensions,
    ) -> tuple[SimpleNamespace, SimpleNamespace]:
        """
        Give each route station a stable sketch profile marker.
        """
        marker = int(station.centers[0].x)
        sketch = SimpleNamespace(profiles=SimpleNamespace(item=lambda _index: marker))
        return sketch, SimpleNamespace()

    monkeypatch.setitem(vars(builder), "_add_solid_section", add_section)
    dimensions = resolve_ffc_dimensions(1.0, (None,), 0.6, 0.4)
    assert builder._build_solid_loft(component, plan, 0.2, None, dimensions) is features[-1]
    assert operations == [new_body, join, join, join, join, join]
    assert profiles == [[0, 4], [4, 12], [12, 20], [20, 28], [28, 35], [35, 39]]
