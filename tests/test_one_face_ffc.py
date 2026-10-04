"""
Verify FFC sweep conditioning and UV image mapping independently of Fusion.
"""

from __future__ import annotations

from dataclasses import replace
from importlib import import_module

import pytest

from cable_bundler.domain import (
    CableColor,
    CableGroupType,
    HarnessDefinition,
    RibbonBodyType,
    RibbonGeometryType,
)
from cable_bundler.domain.ffc import FfcDimensions
from cable_bundler.routing import Vector3
from tests.fusion_ui_support import _PaletteLifecycleModule


@pytest.mark.parametrize(
    ("first_lead_z", "expected"),
    [
        (6.0, (*range(8), 10, 11)),
        (4.0, tuple(range(12))),
    ],
)
def test_ffc_sweep_conditions_only_a_reversing_destination_lead(
    addin_module: _PaletteLifecycleModule,
    first_lead_z: float,
    expected: tuple[int, ...],
) -> None:
    """
    Keep saved station order while removing sampled end-lead backtracking.
    """
    del addin_module
    module = import_module("cable_bundler.fusion.cable_solid_parts.one_face_ffc")
    solid = import_module("cable_bundler.fusion.solid_ribbon")
    z_values = (12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, first_lead_z, 3.0, 1.0, 0.0)
    stations = tuple(
        solid.SolidRibbonSection(
            (Vector3(0.0, 0.0, z),),
            Vector3(0.0, 0.0, -1.0),
            Vector3(1.0, 0.0, 0.0),
            0.6,
        )
        for z in z_values
    )
    plan = solid.SolidRibbonPlan(stations, (), ((), ()), ((), ()), ())
    assert module.sweep_station_indices(plan) == expected


def test_ffc_sweep_checks_numbered_contact_centers(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Reject a trace that no longer seats on its persistent contact target.
    """
    del addin_module
    module = import_module("cable_bundler.fusion.cable_solid_parts.one_face_ffc")
    solid = import_module("cable_bundler.fusion.solid_ribbon")
    start = Vector3(0.0, 0.0, 0.0)
    end = Vector3(0.0, 0.0, 10.0)
    stations = tuple(
        solid.SolidRibbonSection((center,), Vector3(0.0, 0.0, 1.0), Vector3(1.0, 0.0, 0.0), 0.6)
        for center in (start, end)
    )
    plan = solid.SolidRibbonPlan(
        stations,
        (),
        (("start-id",), ("end-id",)),
        ((), ()),
        (),
        ((start,), (end,)),
    )
    dimensions = FfcDimensions(1.0, 0.6, 0.4)
    module._validate_contact_centers(plan, dimensions)
    displaced = replace(plan, contact_centers=((start,), (Vector3(0.1, 0.0, 10.0),)))
    with pytest.raises(RuntimeError, match="end contact"):
        module._validate_contact_centers(displaced, dimensions)


def test_ffc_texture_colors_both_sides_by_the_same_line_identity(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Mirror three numbered trace bands while leaving their gaps in base color.
    """
    del addin_module
    texture = import_module("cable_bundler.fusion.cable_solid_parts.one_face_texture")
    red = CableColor("Red", 255, 0, 0)
    green = CableColor("Green", 0, 255, 0)
    blue = CableColor("Blue", 0, 0, 255)
    base = CableColor("Web", 30, 30, 30)
    samples = ((-6.0, -1.5), (-3.0, 1.5), (0.0, -1.5))
    row = texture._texture_row(samples, FfcDimensions(1.0, 0.6, 0.4), (red, green, blue), base)
    pixels = tuple(tuple(row[index : index + 3]) for index in range(0, len(row), 3))
    assert len(pixels) == texture.IMAGE_WIDTH
    for color in (red, green, blue, base):
        assert (color.red, color.green, color.blue) in pixels[: len(pixels) // 2]
        assert (color.red, color.green, color.blue) in pixels[len(pixels) // 2 :]
    png = texture._png_row(row)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")


def test_ffc_texture_rejects_unknown_uv_phase(addin_module: _PaletteLifecycleModule) -> None:
    """
    Avoid a silently shifted image when neither perimeter end maps to zero.
    """
    del addin_module
    texture = import_module("cable_bundler.fusion.cable_solid_parts.one_face_texture")
    color = CableColor("Trace", 255, 0, 0)
    with pytest.raises(ValueError, match="zero-based"):
        texture._texture_row(
            ((1.0, -0.5), (2.0, 0.5)),
            FfcDimensions(1.0, 0.6, 0.4),
            (color,),
            color,
        )


def test_ffc_uv_transport_rejects_lane_shift_but_allows_mesh_interpolation(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Compare corresponding perimeter samples within a pitch-relative tolerance.
    """
    del addin_module
    texture = import_module("cable_bundler.fusion.cable_solid_parts.one_face_texture")
    dimensions = FfcDimensions(2.5, 1.5, 1.0)
    start = ((-2.0, -1.25), (-1.0, 1.25), (0.0, -1.25))
    interpolated = ((-2.0, -1.25), (-1.0, 1.37), (0.0, -1.25))
    texture._verify_uv_transport(start, interpolated, dimensions)
    shifted = ((-2.0, -1.25), (-1.0, 2.25), (0.0, -1.25))
    with pytest.raises(RuntimeError, match="correspondence"):
        texture._verify_uv_transport(start, shifted, dimensions)


def test_ffc_uv_material_refresh_rebuilds_only_for_changed_colors(
    addin_module: _PaletteLifecycleModule,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve the textured face on no-op refresh and rebuild after color edits.
    """
    del addin_module
    module = import_module("cable_bundler.fusion.cable_solid_materials")
    group = replace(
        valid_harness.cable_groups[0],
        group_type=CableGroupType.RIBBON,
        ribbon_body_type=RibbonBodyType.SOLID,
        ribbon_geometry=RibbonGeometryType.FFC,
        ribbon_lines=1,
    )
    materials = valid_harness.cable_group_materials(group)
    metadata = {
        "ribbon_render_mode": "one_face_uv",
        "main_color": materials.main_color.hex_rgb,
        "ribbon_line_colors_hex": [materials.main_color.hex_rgb],
    }
    assert not module._ffc_uv_needs_rebuild(metadata, group, materials)
    colored = replace(group, ribbon_line_colors=(CableColor("Red", 255, 0, 0),))
    assert module._ffc_uv_needs_rebuild(metadata, colored, materials)
    assert not module._ffc_uv_needs_rebuild({}, colored, materials)
