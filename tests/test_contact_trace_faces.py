"""
Keep solid Discrete trace colors tied to both ordered contact banks.
"""

from __future__ import annotations

from dataclasses import replace
from importlib import import_module
from types import SimpleNamespace
from typing import Any

import pytest

from cable_bundler.domain import (
    CableGroupType,
    HarnessDefinition,
    RibbonBodyType,
    RibbonGeometryType,
)
from tests.fusion_ui_support import _PaletteLifecycleModule


def test_matches_only_full_width_trace_lands_at_both_contacts(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Reject a gap and preserve lane identity across a banked far contact.
    """
    del addin_module
    mapping = import_module("cable_bundler.fusion.cable_solid_parts.contact_trace_faces")
    centers = (-2.5, 0.0, 2.5)
    assert mapping._matching_lane((-0.75, 0.75), (-0.6, 0.6), centers, centers, 1.5, 1.2) == 1
    assert mapping._matching_lane((-0.5, 0.5), (-0.5, 0.5), centers, centers, 1.5, 1.2) is None
    with pytest.raises(RuntimeError, match="contact identity"):
        mapping._matching_lane((-0.75, 0.75), (1.9, 3.1), centers, centers, 1.5, 1.2)
    with pytest.raises(RuntimeError, match="changes width"):
        mapping._matching_lane((-0.75, 0.75), (-0.5, 0.5), centers, centers, 1.5, 1.2)


def test_requires_two_broad_faces_per_numbered_contact(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Map top and bottom only, never fill the spacing web with lane color.
    """
    del addin_module
    mapping = import_module("cable_bundler.fusion.cable_solid_parts.contact_trace_faces")
    start_origin = object()
    end_origin = object()
    frames = iter(
        (
            (start_origin, object(), object(), (-1.25, 1.25)),
            (end_origin, object(), object(), (-1.25, 1.25)),
        )
    )
    monkeypatch.setitem(vars(mapping), "_contact_frame", lambda *_args: next(frames))
    monkeypatch.setitem(
        vars(mapping),
        "_face_interval_mm",
        lambda face, origin, *_args: face.start if origin is start_origin else face.end,
    )
    faces = tuple(
        SimpleNamespace(start=interval, end=interval)
        for interval in (
            (-2.0, -0.5),
            (-2.0, -0.5),
            (-0.5, 0.5),
            (0.5, 2.0),
            (0.5, 2.0),
        )
    )
    side_faces = SimpleNamespace(count=len(faces), item=lambda index: faces[index])
    feature = SimpleNamespace(sideFaces=side_faces)
    station = SimpleNamespace(centers=(object(), object()), lobe_width_mm=1.5)
    plan = SimpleNamespace(sections=(station, station))
    selected = mapping.contact_trace_face_lanes(feature, plan, object())
    assert [lane for _face, lane in selected] == [0, 0, 1, 1]
    assert faces[2] not in [face for face, _lane in selected]


def test_rejects_missing_contact_land(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Report a split or missing face instead of silently shifting colors.
    """
    del addin_module
    mapping = import_module("cable_bundler.fusion.cable_solid_parts.contact_trace_faces")
    frame: tuple[Any, ...] = (object(), object(), object(), (0.0,))
    monkeypatch.setitem(vars(mapping), "_contact_frame", lambda *_args: frame)
    monkeypatch.setitem(vars(mapping), "_face_interval_mm", lambda *_args: (-0.75, 0.75))
    face = object()
    feature = SimpleNamespace(sideFaces=SimpleNamespace(count=1, item=lambda _index: face))
    station = SimpleNamespace(centers=(object(),), lobe_width_mm=1.5)
    plan = SimpleNamespace(sections=(station, station))
    with pytest.raises(RuntimeError, match="top/bottom"):
        mapping.contact_trace_face_lanes(feature, plan, object())


def test_material_refresh_rebuilds_only_legacy_solid_discrete(
    addin_module: _PaletteLifecycleModule,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Upgrade old gap-coloring output without repeatedly rebuilding new output.
    """
    del addin_module
    materials = import_module("cable_bundler.fusion.cable_solid_materials")
    group = replace(
        valid_harness.cable_groups[0],
        group_type=CableGroupType.RIBBON,
        ribbon_body_type=RibbonBodyType.SOLID,
        ribbon_geometry=RibbonGeometryType.DISCRETE,
    )
    assert materials._contact_trace_faces_need_rebuild({}, group)
    assert not materials._contact_trace_faces_need_rebuild({"ribbon_trace_face_revision": 1}, group)
    assert not materials._contact_trace_faces_need_rebuild(
        {}, replace(group, ribbon_body_type=RibbonBodyType.SPLIT)
    )
