"""
Preserve exact physical placements while omitting unused immutable geometry/frame work.
"""

from __future__ import annotations

import math
from dataclasses import asdict, replace
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, dot, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_joint_route import allocation
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology
from tests.test_ribbon_feature_insertion import _targets


@pytest.mark.parametrize("scale", (1e-3, 1e3))
@pytest.mark.parametrize("bank", (-0.4, 0.0, 0.4))
@pytest.mark.parametrize("fold_count", (1, 8))
@pytest.mark.parametrize("growth", (0.0, 0.25))
def test_shared_fixed_folds_preserve_original_complete_placements(
    scale: float, bank: float, fold_count: int, growth: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Compare the original rebuilding boundary with actual shared signed/banked geometry.
    """
    boundary = Boundary(_targets(scale), 0.101 * scale)
    topology = Topology(
        "authored placement preparation",
        tuple(
            CylindricalFold(
                boundary.radius_mm, (-1) ** i * 1.2, bank, 2 * boundary.half_width_mm, scale, scale
            )
            for i in range(fold_count)
        ),
        None,
    )
    coordinates = tuple(0.2 if i % 2 == 0 else growth for i in range(2 * fold_count + 1))

    def rebuild(original: CylindricalFold, radius: float) -> CylindricalFold:
        """
        Retain the exact old dataclass replacement for every fold, including unchanged radii.
        """
        return replace(original, radius_mm=radius)

    with monkeypatch.context() as old:
        old.setattr(allocation, "_radius_geometry", rebuild)
        expected = Model(boundary, topology).pieces(coordinates)
    actual = Model(boundary, topology).pieces(coordinates)
    assert actual == expected
    assert [asdict(piece) for piece in actual] == [asdict(piece) for piece in expected]
    folds = [piece.geometry for piece in actual if isinstance(piece.geometry, CylindricalFold)]
    assert all(
        (current is original) == (growth == 0) for current, original in zip(folds, topology.folds)
    )


def test_radius_sharing_preserves_changed_validation_and_integer_representation() -> None:
    """
    Reuse never bypasses validation of a changed radius or changes an old integer into a retained field.
    """
    original = CylindricalFold(1.0, 1.2, 0, 4, 5, 5)
    assert allocation._radius_geometry(original, 1.0) is original
    changed = allocation._radius_geometry(original, 2.0)
    assert changed == replace(original, radius_mm=2.0) and changed is not original
    integer = replace(original, radius_mm=1)
    converted = allocation._radius_geometry(integer, 1.0)
    assert converted is not integer and type(converted.radius_mm) is float
    with pytest.raises(ValueError, match="Positive radius"):
        allocation._radius_geometry(original, 0.0)


@pytest.mark.parametrize("scale", (1e-6, 1.0, 1e6))
@pytest.mark.parametrize("bank", (-1.1, 0.0, 0.7))
@pytest.mark.parametrize("angle", (-math.pi, -1.2, 1e-7, 1.2, math.pi))
def test_endpoint_frame_matches_original_surface_bits_without_acceleration_transform(
    scale: float, bank: float, angle: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Retain every endpoint/frame bit, including normalization, across curved material domains.
    """
    geometry = CylindricalFold(scale, angle, bank, 4 * scale, 8 * scale, 8 * scale)
    piece = PlacedPiece(
        Pose(Vector3(10, -4, 7), Vector3(0, 1, 0), Vector3(0, 0, 1)), geometry, "frame control"
    )
    point, velocity, across, _ = piece.surface(1, 0)
    tangent = unit(velocity)
    expected = Pose(point, tangent, unit(across.translated(tangent, -dot(across, tangent))))
    original_direction = Pose.direction
    observed = Mock(wraps=original_direction)

    def direction(pose: Pose, local: Vector3) -> Vector3:
        """
        Observe real transforms while preserving their exact floating-point arithmetic.
        """
        return observed(pose, local)

    monkeypatch.setattr(Pose, "direction", direction)
    actual = piece.end_pose()
    assert observed.call_count == 3
    assert piece.end_pose() is actual and observed.call_count == 3
    for key in ("origin", "tangent", "width"):
        first, last = getattr(actual, key), getattr(expected, key)
        assert [float(getattr(first, a)).hex() for a in "xyz"] == [
            float(getattr(last, a)).hex() for a in "xyz"
        ]


def test_subclass_endpoint_keeps_overridden_material_surface_dispatch() -> None:
    """
    Preserve explicit subclass behavior instead of silently substituting the base material map.
    """
    calls = []

    class CustomPiece(PlacedPiece):
        """
        Supply an observable specialized material surface at the existing endpoint boundary.
        """

        def surface(self, u: float, q: float) -> tuple[Vector3, Vector3, Vector3, Vector3]:
            """
            Preserve physical derivatives while translating this custom diagnostic surface.
            """
            calls.append((u, q))
            point, velocity, across, acceleration = super().surface(u, q)
            return point.translated(Vector3(0, 0, 1), 2), velocity, across, acceleration

    pose = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    piece = CustomPiece(pose, Straight(3), "custom control")
    assert piece.end_pose().origin == Vector3(3, 0, 2)
    assert calls == [(1, 0)]
