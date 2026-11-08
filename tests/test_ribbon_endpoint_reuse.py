"""
Preserve exact endpoint frames and instance ownership while avoiding repeated surface work.
"""

from __future__ import annotations

import weakref
from dataclasses import asdict, replace

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route import geometry as material
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight


@pytest.mark.parametrize(
    "geometry",
    (
        Straight(4.2),
        CylindricalFold(0.8, 1.2, 0.3, 2.4, 1.0, 1.1),
        CylindricalFold(0.8, -2.1, -0.4, 2.4, 1.1, 1.0),
    ),
)
def test_endpoint_frame_is_reused_locally_without_changing_piece_identity(
    geometry: Straight | CylindricalFold, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Retain endpoint values, serialization and hash while replaced pieces own fresh frames.
    """
    original = PlacedPiece.surface
    calls: list[PlacedPiece] = []

    def surface(
        piece: PlacedPiece, u: float, q: float
    ) -> tuple[Vector3, Vector3, Vector3, Vector3]:
        """
        Count actual endpoint material evaluations without changing their arithmetic.
        """
        calls.append(piece)
        return original(piece, u, q)

    monkeypatch.setattr(PlacedPiece, "surface", surface)
    source = PlacedPiece(
        Pose(Vector3(2, -3, 4), Vector3(0, 1, 0), Vector3(0, 0, 1)), geometry, "source"
    )
    before, identity = asdict(source), hash(source)
    expected_point = original(source, 1, 0)[0]
    frame = source.end_pose()
    assert frame.origin == expected_point
    assert source.end_pose() is frame and len(calls) == 1
    assert asdict(source) == before and hash(source) == identity

    moved = replace(source, pose=replace(source.pose, origin=Vector3(5, -3, 4)))
    changed = moved.end_pose()
    assert changed.origin == frame.origin.translated(Vector3(1, 0, 0), 3)
    assert changed.tangent == frame.tangent and changed.width == frame.width
    assert moved.end_pose() is changed and source.end_pose() is frame
    assert calls == [source, moved]


def test_endpoint_reuse_does_not_retain_the_placed_piece() -> None:
    """
    A retained frame must not keep its former route piece alive through a cache.
    """
    piece = PlacedPiece(
        Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), Straight(2), "temporary"
    )
    frame = piece.end_pose()
    reference = weakref.ref(piece)
    del piece
    assert reference() is None and frame.origin == Vector3(2, 0, 0)


@pytest.mark.parametrize(
    "forward,across",
    (
        (Vector3(0, 1, 0), Vector3(0, 0, 1)),
        (Vector3(0.1, -0.7, 0.3), Vector3(-0.6, 0.2, 0.8)),
        (Vector3(1e-100, -1e100, 1), Vector3(-1e-100, 1e-100, -1e-100)),
    ),
)
def test_frame_reuses_its_normal_with_bit_exact_original_vector_arithmetic(
    forward: Vector3, across: Vector3, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Preserve cancellation, signed zero and large/small components without repeated cross products.
    """
    original_cross = material.cross
    calls: list[tuple[Vector3, Vector3]] = []

    def tracked_cross(a: Vector3, b: Vector3) -> Vector3:
        """
        Count independent frame-normal construction while preserving its exact value.
        """
        calls.append((a, b))
        return original_cross(a, b)

    monkeypatch.setitem(vars(material), "cross", tracked_cross)
    pose = Pose(Vector3(1, -2, 3), forward, across)
    before, identity = asdict(pose), hash(pose)
    normal = original_cross(forward, across)
    for x in (0.0, -0.0, 1e-100, -3.125):
        for y in (0.0, -1.0, 1e100):
            for z in (0.0, -0.0, 0.31):
                expected = (
                    Vector3(0, 0, 0)
                    .translated(forward, x)
                    .translated(across, y)
                    .translated(normal, z)
                )
                actual = pose.direction(Vector3(x, y, z))
                assert tuple(float(getattr(actual, a)).hex() for a in "xyz") == tuple(
                    float(getattr(expected, a)).hex() for a in "xyz"
                )
    assert calls == [(forward, across)]
    assert asdict(pose) == before and hash(pose) == identity
    changed = replace(pose, width=Vector3(1, 0, 0))
    assert changed.direction(Vector3(0, 0, 1)) == original_cross(forward, changed.width)
    assert calls == [(forward, across), (forward, changed.width)]
