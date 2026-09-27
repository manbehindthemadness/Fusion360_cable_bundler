"""
Focused Fusion-boundary tests for planar routing-gate profiles.
"""

from __future__ import annotations

import math
from importlib import import_module
from types import SimpleNamespace
from uuid import UUID

import pytest

from cable_bundler.domain import ControlKind, ControlStructure
from cable_bundler.routing.aperture import contains_disk
from tests.fusion_ui_support import _PaletteLifecycleModule


def _point(x: float, y: float, z: float = 0.0) -> SimpleNamespace:
    """
    Create one centimeter-scale Fusion point double.
    """
    return SimpleNamespace(x=x, y=y, z=z)


def _collection(items: tuple[object, ...]) -> SimpleNamespace:
    """
    Expose Fusion's count/item collection contract.
    """
    return SimpleNamespace(count=len(items), item=lambda index: items[index])


def _segment(start: tuple[float, float], end: tuple[float, float]) -> SimpleNamespace:
    """
    Sample one straight profile edge through the Fusion curve evaluator contract.
    """
    evaluator = SimpleNamespace(
        getParameterExtents=lambda: (True, 0.0, 1.0),
        getStrokes=lambda _start, _end, _tolerance: (
            True,
            (_point(*start), _point(*end)),
        ),
    )
    return SimpleNamespace(geometry=SimpleNamespace(evaluator=evaluator), sketchEntity=None)


def test_square_sketch_profile_resolves_to_a_bounded_gate(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Accept four coplanar straight profile edges as a real routing aperture.
    """
    frames = import_module("cable_bundler.fusion.route_preview_parts.frames")
    monkeypatch.setitem(
        vars(frames.adsk.fusion),
        "Profile",
        SimpleNamespace(cast=lambda entity: entity),
    )
    monkeypatch.setitem(
        vars(frames.adsk.fusion),
        "SketchCircle",
        SimpleNamespace(cast=lambda _entity: None),
    )
    corners = ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5))
    curves = tuple(_segment(corners[index], corners[(index + 1) % 4]) for index in (0, 2, 1, 3))
    sketch = SimpleNamespace(
        sketchToModelSpace=lambda point: point,
        xDirection=_point(1.0, 0.0),
        yDirection=_point(0.0, 1.0),
    )
    profile = SimpleNamespace(
        isValid=True,
        parentSketch=sketch,
        profileLoops=_collection((SimpleNamespace(profileCurves=_collection(curves)),)),
        areaProperties=lambda: SimpleNamespace(centroid=_point(0.0, 0.0)),
    )
    design = SimpleNamespace(findEntityByToken=lambda _token: (profile,))
    control = ControlStructure(UUID(int=1), "Routing Gate 02", ControlKind.ROUTING_GATE, "gate")

    gate = frames.routing_frame(design, control, control.control_id)

    assert gate.usable_radius_mm is None
    assert len(gate.boundary_loops_mm) == 1
    assert contains_disk((0.0, 0.0), 4.0, gate.boundary_loops_mm)
    assert not contains_disk((4.5, 0.0), 1.0, gate.boundary_loops_mm)


def test_circular_sketch_profile_keeps_exact_radius(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve the existing exact-circle fast path and millimeter conversion.
    """
    frames = import_module("cable_bundler.fusion.route_preview_parts.frames")
    monkeypatch.setitem(
        vars(frames.adsk.fusion),
        "Profile",
        SimpleNamespace(cast=lambda entity: entity),
    )
    circle = SimpleNamespace(geometry=SimpleNamespace(center=_point(0.2, 0.3), radius=0.5))
    monkeypatch.setitem(
        vars(frames.adsk.fusion),
        "SketchCircle",
        SimpleNamespace(cast=lambda _entity: circle),
    )
    sketch = SimpleNamespace(
        sketchToModelSpace=lambda point: point,
        xDirection=_point(1.0, 0.0),
        yDirection=_point(0.0, 1.0),
    )
    profile = SimpleNamespace(
        isValid=True,
        parentSketch=sketch,
        profileLoops=_collection(
            (SimpleNamespace(profileCurves=_collection((SimpleNamespace(sketchEntity=circle),))),)
        ),
    )
    design = SimpleNamespace(findEntityByToken=lambda _token: (profile,))
    control = ControlStructure(UUID(int=2), "Routing Gate 01", ControlKind.ROUTING_GATE, "gate")

    gate = frames.routing_frame(design, control, control.control_id)

    assert gate.usable_radius_mm == 5.0
    assert gate.origin.x == 2.0
    assert gate.origin.y == 3.0
    assert gate.boundary_loops_mm == ()


def test_curved_non_circular_profile_uses_sampled_outline(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Accept a closed smooth profile even when it has only one non-circle curve.
    """
    frames = import_module("cable_bundler.fusion.route_preview_parts.frames")
    monkeypatch.setitem(
        vars(frames.adsk.fusion),
        "Profile",
        SimpleNamespace(cast=lambda entity: entity),
    )
    monkeypatch.setitem(
        vars(frames.adsk.fusion),
        "SketchCircle",
        SimpleNamespace(cast=lambda _entity: None),
    )
    samples = tuple(
        _point(0.6 * math.cos(index * math.tau / 64), 0.3 * math.sin(index * math.tau / 64))
        for index in range(65)
    )
    evaluator = SimpleNamespace(
        getParameterExtents=lambda: (True, 0.0, 1.0),
        getStrokes=lambda _start, _end, _tolerance: (True, samples),
    )
    curve = SimpleNamespace(geometry=SimpleNamespace(evaluator=evaluator), sketchEntity=None)
    sketch = SimpleNamespace(
        sketchToModelSpace=lambda point: point,
        xDirection=_point(1.0, 0.0),
        yDirection=_point(0.0, 1.0),
    )
    profile = SimpleNamespace(
        isValid=True,
        parentSketch=sketch,
        profileLoops=_collection((SimpleNamespace(profileCurves=_collection((curve,))),)),
        areaProperties=lambda: SimpleNamespace(centroid=_point(0.0, 0.0)),
    )
    design = SimpleNamespace(findEntityByToken=lambda _token: (profile,))
    control = ControlStructure(UUID(int=3), "Oval Gate", ControlKind.ROUTING_GATE, "oval")

    gate = frames.routing_frame(design, control, control.control_id)

    assert gate.usable_radius_mm is None
    assert contains_disk((0.0, 0.0), 2.0, gate.boundary_loops_mm)
    assert not contains_disk((0.0, 2.5), 1.0, gate.boundary_loops_mm)
