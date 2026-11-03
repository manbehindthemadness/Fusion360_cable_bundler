"""
Verify conditioned native direction measurements retain strict angular rejection on tiny straights.
"""

from __future__ import annotations

import importlib
import math
from typing import Any

import pytest

from cable_bundler.routing.geometry import Vector3, difference, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import Straight
from tests.fusion_ui_support import _PaletteLifecycleModule


@pytest.fixture
def fidelity(addin_module: _PaletteLifecycleModule) -> Any:
    """
    Import the native audit against SDK stubs; chord sampling itself is host independent.
    """
    del addin_module
    return importlib.import_module("experiments.experiment_ribbon_locked_solver.fidelity_base")


def test_full_affine_chord_resolves_tiny_straight_under_native_coordinate_roundoff(
    fidelity: Any,
) -> None:
    """
    Recover an unchanged straight direction when the old microscopic stencil amplifies rounding.
    """
    origin, direction = Vector3(11, -10, -9), unit(Vector3(1, 2, 3))
    geometry = Straight(4.7080081245497744e-7)

    def native(u: float) -> Vector3:
        """
        Model an affine native surface evaluated with finite coordinate precision.
        """
        p = origin.translated(direction, geometry.material_length_mm * u)
        return Vector3(*(round(v, 14) for v in (p.x, p.y, p.z)))

    old = difference(native(0.50001), native(0.49999))
    chord, fractions = fidelity._guide_chord(geometry, 0.5, native)
    assert fidelity.angle(old, direction) > 0.001
    assert fidelity.angle(chord, direction) < 0.001
    assert fractions == (0, 1)


def test_full_chord_still_rejects_wrong_native_tangent(fidelity: Any) -> None:
    """
    Keep a real two-degree direction error above the original0.001degree gate.
    """
    geometry = Straight(4.7080081245497744e-7)
    angle = math.radians(2)
    bad = Vector3(math.cos(angle), math.sin(angle), 0)
    chord, _ = fidelity._guide_chord(
        geometry, 0.5, lambda u: Vector3(0, 0, 0).translated(bad, geometry.material_length_mm * u)
    )
    assert fidelity.angle(chord, Vector3(1, 0, 0)) == pytest.approx(2)


def test_curved_guide_keeps_original_centered_stencil(fidelity: Any) -> None:
    """
    Avoid substituting a long secant for the local tangent of a curved material guide.
    """
    fold = CylindricalFold(3, math.pi / 2, 0, 2, 2, 1)
    samples: list[float] = []

    def native(u: float) -> Vector3:
        """
        Return a genuine varying tangent and expose the requested native sample fractions.
        """
        samples.append(u)
        return Vector3(math.cos(u), math.sin(u), 0)

    chord, fractions = fidelity._guide_chord(fold, 0.3, native)
    assert fractions == (0.3 - 1e-5, 0.3 + 1e-5)
    assert set(samples) == set(fractions)
    assert fidelity.angle(chord, Vector3(-math.sin(0.3), math.cos(0.3), 0)) < 0.001
