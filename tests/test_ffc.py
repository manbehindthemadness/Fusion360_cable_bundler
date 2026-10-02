"""
Verify persisted FFC settings and contact-pitch sizing rules.
"""

from __future__ import annotations

import json
from dataclasses import replace
from importlib import import_module
from types import SimpleNamespace
from typing import Any
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
from cable_bundler.domain.ffc import resolve_ffc_dimensions
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


def test_ffc_section_keeps_flat_traces_inside_overall_thickness(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Three flat bands and their recessed web form one closed contour.
    """
    builder = import_module("cable_bundler.fusion.cable_solid_parts.ribbon_builder")
    monkeypatch.setitem(vars(builder), "fusion_point", lambda point, _transform: point)
    edges: list[tuple[Vector3, Vector3]] = []
    sketch: Any = SimpleNamespace(
        modelToSketchSpace=lambda point: point,
        sketchCurves=SimpleNamespace(
            sketchLines=SimpleNamespace(
                addByTwoPoints=lambda left, right: edges.append((left, right)) or object()
            )
        ),
    )
    station = builder.SolidRibbonSection(
        (Vector3(-1, 0, 0), Vector3(0, 0, 0), Vector3(1, 0, 0)),
        Vector3(0, 0, 1),
        Vector3(1, 0, 0),
        0.6,
    )
    dimensions = resolve_ffc_dimensions(1.0, (None, None, None), 0.6, 0.4)
    builder._draw_ffc_section(sketch, station, Vector3(0, 1, 0), 0.2, dimensions, None)
    corners = [edge[0] for edge in edges]
    assert len(edges) == 28
    assert edges[-1][1] == edges[0][0]
    assert (min(point.x for point in corners), max(point.x for point in corners)) == (-1.5, 1.5)
    assert (min(point.y for point in corners), max(point.y for point in corners)) == (-0.1, 0.1)
    assert any(point.y == pytest.approx(0.09) for point in corners)
