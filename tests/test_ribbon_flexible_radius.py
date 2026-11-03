"""
Preserve physical radius anchors through normalized material coordinates.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_fold_relaxation.flexible import FlexibleModel
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import Piece, fold


def _route(scale: float, radius_factor: float = 1.0) -> FoldRoute:
    """
    Author one fold at a nonbinary material length with a separately declared floor.
    """
    minimum = 0.3765060244728916 * scale
    geometry = fold(minimum * radius_factor, 0.75 * scale, 0.7, 0.2, 0.0)
    start = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    geometries: tuple[Piece, ...] = (
        Straight(5 * scale),
        geometry,
        Straight(19.71207274875796 * scale - 5 * scale - geometry.material_length_mm),
    )
    pieces: list[PlacedPiece] = []
    pose = start
    for index, item in enumerate(geometries):
        placed = PlacedPiece(pose, item, str(index))
        pieces.append(placed)
        pose = placed.end_pose()
    targets = Targets(
        "radius conversion control",
        start.origin,
        pose.origin,
        start.tangent,
        pose.tangent,
        start.width,
        pose.width,
        1,
        0.75 * scale,
    )
    return FoldRoute(targets, tuple(pieces), minimum)


def _radius(pieces: tuple[PlacedPiece, ...]) -> float:
    """
    Return the control's sole reconstructed physical fold radius.
    """
    return next(p.geometry.radius_mm for p in pieces if isinstance(p.geometry, CylindricalFold))


@pytest.mark.parametrize("scale", (0.125, 1.0, 8.0))
@pytest.mark.parametrize("radius_factor", (1.0, 2.0))
def test_unchanged_radius_survives_movable_bend_edits_exactly(
    scale: float, radius_factor: float
) -> None:
    """
    Keep fixed physical radii bit-for-bit while angles, banks and runways move.
    """
    source = _route(scale, radius_factor)
    model = MovableBends(source)
    values = list(model.initial)
    values[0] *= 0.5
    values[1] *= 0.8
    values[2] *= 0.9
    result = model.pieces(tuple(values))
    assert _radius(result) == _radius(source.pieces)
    remapped = FlexibleModel(FoldRoute(source.targets, result, source.radius_mm))
    assert _radius(remapped.pieces(remapped.initial)) == _radius(source.pieces)


@pytest.mark.parametrize("scale", (0.125, 1.0, 8.0))
def test_active_radius_floor_reconstructs_exact_physical_minimum(scale: float) -> None:
    """
    Preserve the declared minimum when radius relaxation reaches its normalized bound.
    """
    source = _route(scale, 2.0)
    model = FlexibleModel(source)
    values = list(model.initial)
    values[3] = model.bounds(3)[0]
    assert _radius(model.pieces(tuple(values))) == source.radius_mm
    values[3] = math.nextafter(values[3], -math.inf)
    with pytest.raises(ValueError, match="outside its declared bounds"):
        model.pieces(tuple(values))


def test_nonanchor_radius_keeps_ordinary_scaling() -> None:
    """
    Leave freely moved radius coordinates responsive to the optimizer.
    """
    model = FlexibleModel(_route(1.0))
    values = list(model.initial)
    values[3] *= 1.375
    assert _radius(model.pieces(tuple(values))) == values[3] * model.scale
