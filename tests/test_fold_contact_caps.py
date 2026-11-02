"""
Challenge cap-plane separation across short straight bridges without exempting folded interiors.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, unit
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.contact_caps import straight_bridge_pairs
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import Piece, fold


def _chain(geometries: tuple[Piece, ...], turned: bool = False) -> FoldRoute:
    """
    Author an analytical material chain and derive its cap poses without archived geometry.
    """
    initial = Pose(
        Vector3(13, -7, 2),
        Vector3(0, 1, 0) if turned else Vector3(1, 0, 0),
        Vector3(0, 0, 1) if turned else Vector3(0, 1, 0),
    )
    pose = initial
    pieces = []
    for geometry in geometries:
        piece = PlacedPiece(pose, geometry, "cap bridge analytical")
        pieces.append(piece)
        pose = piece.end_pose()
    targets = Targets(
        "cap bridge analytical",
        initial.origin,
        pose.origin,
        initial.tangent,
        pose.tangent,
        initial.width,
        pose.width,
        3,
        0.75,
    )
    return FoldRoute(targets, tuple(pieces), 0.3765060244728916)


@pytest.mark.parametrize("turned", (False, True))
@pytest.mark.parametrize("bank", (0.0, 0.35))
def test_short_straight_bridge_certifies_only_separated_cap_neighborhoods(
    turned: bool, bank: float
) -> None:
    """
    Clear two gentle spatial folds across a tiny positive bridge without subdivision.
    """
    route = _chain(
        (fold(1, 2.4, 0.7, bank, 0), Straight(1e-4), fold(1.5, 2.4, 0.9, -bank, 0)), turned
    )
    assert straight_bridge_pairs(route) == {(0, 2)}
    result = inspect_contact(route, maximum_pairs=3)
    assert result.status == "separated" and result.pairs_checked == 3
    cap = route.pieces[0].end_pose()
    for index in (0, 2):
        for u in (0.0, 0.5, 1.0):
            for q in (-route.half_width_mm, 0.0, route.half_width_mm):
                point, velocity, across, _ = route.pieces[index].surface(u, q)
                for height in (-0.375, 0.0, 0.375):
                    physical = point.translated(unit(cross(velocity, across)), height)
                    position = dot(difference(physical, cap.origin), cap.tangent)
                    assert position <= 1e-10 if index == 0 else position >= 1e-4 - 1e-10


def test_straight_bridge_does_not_exempt_returning_fold_interiors() -> None:
    """
    A linked pair still cannot pass when its two half-turns return into occupied material.
    """
    returning = replace(fold(1, 2.4, math.pi, 0, 0), after_mm=0.01)
    route = _chain((fold(1, 2.4, math.pi, 0, 0), Straight(1e-4), returning))
    assert straight_bridge_pairs(route) == {(0, 2)}
    assert inspect_contact(route, maximum_pairs=1000).status != "separated"


def test_broken_folded_and_numerically_tiny_bridges_keep_the_existing_fallback() -> None:
    """
    Refuse a cap shortcut when continuity, straight-only topology or resolvable gap is absent.
    """
    a, b = fold(1, 2.4, 0.7, 0.3, 0), fold(1, 2.4, 0.9, -0.3, 0)
    tiny = _chain((a, Straight(1e-10), b))
    assert not straight_bridge_pairs(tiny)
    curved = _chain((a, fold(1, 2.4, 0.1, 0, 0), b))
    assert not straight_bridge_pairs(curved)
    original = _chain((a, Straight(1e-4), b))
    last = original.pieces[-1]
    broken = replace(
        original,
        pieces=original.pieces[:-1]
        + (
            replace(
                last,
                pose=replace(
                    last.pose, origin=last.pose.origin.translated(last.pose.tangent, -0.1)
                ),
            ),
        ),
    )
    assert not straight_bridge_pairs(broken)
