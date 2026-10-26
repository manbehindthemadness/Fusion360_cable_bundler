"""
Verify retained original routes preserve frozen geometry and user visibility.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from cable_bundler.routing.geometry import CubicBezier, Vector3
from devtools.ribbon_analysis.api import Candidate, Evidence, analyze
from devtools.ribbon_analysis.contracts import Targets


def _point(x: float, y: float, z: float) -> SimpleNamespace:
    """
    Supply explicit point coordinates at the native API boundary.
    """
    return SimpleNamespace(x=x, y=y, z=z)


class _Attributes:
    """
    Preserve native provenance stamps independently of sketch names.
    """

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], SimpleNamespace] = {}

    def add(self, group: str, name: str, value: str) -> None:
        self.values[group, name] = SimpleNamespace(value=value)

    # noinspection PyPep8Naming
    def itemByName(self, group: str, name: str) -> SimpleNamespace | None:
        return self.values.get((group, name))


class _Sketches(list[Any]):
    """
    Apply a nonidentity sketch coordinate system when native routes are authored.
    """

    def add(self, _plane: object) -> SimpleNamespace:
        def to_sketch(point: Any) -> SimpleNamespace:
            return _point(point.x - 5, point.y - 7, point.z - 11)

        def to_model(point: Any) -> SimpleNamespace:
            return _point(point.x + 5, point.y + 7, point.z + 11)

        sketch = SimpleNamespace(
            attributes=_Attributes(),
            isLightBulbOn=True,
            modelToSketchSpace=to_sketch,
            sketchToModelSpace=to_model,
            sketchCurves=SimpleNamespace(
                sketchFixedSplines=SimpleNamespace(
                    addByNurbsCurve=lambda curve: SimpleNamespace(geometry=curve)
                )
            ),
        )
        self.append(sketch)
        return sketch


def _nurbs(points: list[Any], degree: int, knots: list[float], closed: bool) -> Any:
    """
    Evaluate supplied controls as native cubics, without knowing any source target.
    """
    assert degree == 3 and not closed and knots[0] == 0 and knots[-1] == 1
    controls = tuple(Vector3(p.x, p.y, p.z) for p in points)
    curves = tuple(CubicBezier(*controls[i : i + 4]) for i in range(0, len(controls) - 1, 3))

    def at(parameter: float) -> tuple[bool, Any]:
        index = min(int(parameter * len(curves)), len(curves) - 1)
        position = curves[index].point(parameter * len(curves) - index)
        return True, _point(position.x, position.y, position.z)

    return SimpleNamespace(
        evaluator=SimpleNamespace(
            getParameterExtents=lambda: (True, 0.0, 1.0), getPointAtParameter=at
        )
    )


@pytest.fixture
def original_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    """
    Isolate Fusion imports while retaining the actual guide-authoring implementation.
    """
    core = ModuleType("adsk.core")
    core.Point3D = SimpleNamespace(create=_point)
    core.NurbsCurve3D = SimpleNamespace(createNonRational=_nurbs)
    host = ModuleType("adsk")
    host.core = core
    monkeypatch.setitem(sys.modules, "adsk", host)
    monkeypatch.setitem(sys.modules, "adsk.core", core)
    module = importlib.import_module("devtools.ribbon_analysis.original_guides")
    monkeypatch.setitem(vars(module), "adsk", host)
    return module


@dataclass(frozen=True)
class _Field:
    """
    Supply dimensions and a regular intrinsic field independently of Fusion.
    """

    lines: int = 3
    diameter_mm: float = 1.0
    half_width_mm: float = 1.6
    curvature: float = 0.0

    def sample(self, u: float) -> tuple[float, float, float]:
        """
        Return the straight-strip intrinsic field.
        """
        if not 0 <= u <= 1:
            raise ValueError("Normalized route fraction required.")
        return self.curvature, 0.0, 0.0


@dataclass(frozen=True)
class _Path:
    """
    Supply a spatial route with an independently misplaced target.
    """

    field: _Field = _Field()

    @staticmethod
    def lane(u: float, offset_mm: float) -> tuple[Vector3, Vector3]:
        """
        Retain the real unsolved endpoint instead of fitting it to the target.
        """
        return Vector3(12 * u, offset_mm, 2 * u), Vector3(12, 0, 2)


def _evidence() -> Evidence:
    """
    Freeze a spatial route that deliberately misses its endpoint target.
    """
    path = _Path()
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    targets = Targets("miss", Vector3(0, 0, 0), Vector3(99, 0, 0), x, x, y, y, 3, 1)
    return analyze(Candidate("failed-route", path, targets, "independent-test"), intervals=16)


def test_hidden_originals_preserve_failed_route_and_reuse_visibility(original_module: Any) -> None:
    """
    Preserve the unsolved endpoint through transforms and avoid duplicate sketches.
    """
    component = SimpleNamespace(sketches=_Sketches(), xYConstructionPlane=object())
    evidence = _evidence()
    checkpoints: list[bool] = []
    result = original_module.retain_guides(component, evidence, lambda: checkpoints.append(True))
    assert len(component.sketches) == 3 and len(checkpoints) == 3
    assert set(result["original_guides"]) == {-1, 0, -2}
    assert result["original_guide_maximum_error_mm"] < 1e-10
    assert all(not sketch.isLightBulbOn for sketch in component.sketches)
    first = component.sketches[0]
    first.isLightBulbOn = True
    reused = original_module.retain_guides(component, evidence)
    assert len(component.sketches) == 3
    assert reused["original_guides"][-1] is first and first.isLightBulbOn


def test_partial_native_failure_is_preserved_without_automatic_retry(
    original_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Keep incomplete native work and require review before another authoring attempt.
    """
    component = SimpleNamespace(sketches=_Sketches(), xYConstructionPlane=object())
    evidence = _evidence()
    monkeypatch.setitem(
        vars(original_module.adsk.core.NurbsCurve3D), "createNonRational", lambda *_: None
    )
    with pytest.raises(RuntimeError, match="NURBS creation failed"):
        original_module.retain_guides(component, evidence)
    assert len(component.sketches) == 1
    with pytest.raises(RuntimeError, match="Incomplete original"):
        original_module.retain_guides(component, evidence)
    assert len(component.sketches) == 1
