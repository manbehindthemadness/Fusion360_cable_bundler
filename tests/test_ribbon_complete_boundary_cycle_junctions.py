"""
Compare source-core constrained cycle counting with independent complete-assignment enumeration.
"""

from dataclasses import replace
from fractions import Fraction
from itertools import product

import pytest

from experiments.experiment_ribbon_complete.boundary_cycle_candidates import BoundaryCycleCandidates
from experiments.experiment_ribbon_complete.boundary_cycle_junctions import BoundaryCycleJunctions
from experiments.experiment_ribbon_complete.boundary_traversal import (
    BoundaryTransitionBounds,
    BoundaryTraversalPolicy,
)
from experiments.experiment_ribbon_complete.flat_chart import MaterialCut
from experiments.experiment_ribbon_complete.material_polygon import MaterialPolygon, Pair
from experiments.experiment_ribbon_complete.native_boundary_distance import BoundarySide
from tests.test_ribbon_complete_native_boundary_distance import fixture
from tests.test_ribbon_complete_volume_injectivity import checkpoint


@pytest.mark.parametrize(
    "kind", ["complete", "wrapped", "reversed", "thin", "ambiguous", "zero_tip"]
)
def test_bounded_dp_matches_exhaustive_global_corner_feasibility(kind: str) -> None:
    """
    Geometry removes impossible corner paths, while two genuinely feasible assignments remain unresolved.
    """
    _, frame, graph = fixture()
    policy = BoundaryTraversalPolicy.COMPLETE
    if kind == "thin":
        frame = replace(
            frame, high=MaterialCut(Fraction(3, 625) + Fraction(1, 10**12), Fraction(-1, 125))
        )
        policy = BoundaryTraversalPolicy.FINITE_BRIDGES
    elif kind == "zero_tip":
        frame = replace(frame, high=MaterialCut(-graph.interval[0], Fraction(1)))
    polygon = MaterialPolygon(frame, graph)
    v0, v1, v2, v3 = polygon.vertices
    candidates = (tuple(BoundarySide),) * 4
    points: tuple[Pair, ...] = (v1, v2, v3, v0)
    if kind == "wrapped":
        candidates = tuple(
            (side,)
            for side in (
                BoundarySide.HIGH,
                BoundarySide.HIGH,
                BoundarySide.END1,
                BoundarySide.LOW,
                BoundarySide.END0,
                BoundarySide.HIGH,
            )
        )
        midpoint = ((v1[0] + v2[0]) / 2, (v1[1] + v2[1]) / 2)
        points = (midpoint, v2, v3, v0, v1, midpoint)
    elif kind == "reversed":
        candidates = tuple(
            (side,)
            for side in (BoundarySide.LOW, BoundarySide.END1, BoundarySide.HIGH, BoundarySide.END0)
        )
        points = (v3, v2, v1, v0)
    elif kind == "thin":
        candidates = (
            (BoundarySide.LOW, BoundarySide.HIGH, BoundarySide.END0),
            (BoundarySide.LOW, BoundarySide.HIGH),
            (BoundarySide.LOW, BoundarySide.HIGH),
        )
        points = (v1, v3, v0)
    elif kind == "ambiguous":
        candidates = (
            (BoundarySide.END0,),
            (BoundarySide.END0, BoundarySide.HIGH),
            (BoundarySide.HIGH,),
            (BoundarySide.END1,),
            (BoundarySide.LOW,),
        )
        points = (v1, v1, v2, v3, v0)
    elif kind == "zero_tip":
        candidates = tuple(
            (side,) for side in (BoundarySide.HIGH, BoundarySide.END1, BoundarySide.LOW)
        )
        points = (v2, v3, v0)
    valid = set()
    for assignment in product(*candidates):
        try:
            bound = BoundaryTransitionBounds(polygon, assignment, points, policy, checkpoint)
        except ValueError:
            continue
        if 2 * bound.corner_upper_mm < polygon.inradius_mm and bound.corner_upper_mm <= Fraction(
            1, 100
        ):
            valid.add(assignment)
    geometry = BoundaryCycleJunctions(polygon, points, checkpoint)
    proof = BoundaryCycleCandidates(polygon, candidates, checkpoint, policy, geometry)
    assert proof.assignment_count == min(2, len(valid))
    assert proof.unique_assignment == (next(iter(valid)) if len(valid) == 1 else None)
    assert len(valid) == (2 if kind == "ambiguous" else 1)
    if kind == "thin":
        assert (
            BoundaryCycleCandidates(polygon, candidates, checkpoint, policy).assignment_count == 2
        )


def test_source_core_boundary_is_strict_without_changing_the_dimensional_allowance() -> None:
    """
    The existing core condition remains strict at equality even when the dimensional error is below0.01mm.
    """
    _, frame, graph = fixture()
    polygon = MaterialPolygon(replace(frame, high=MaterialCut(Fraction(1, 1000))), graph)
    v0, v1, v2, v3 = polygon.vertices
    candidates = tuple(
        (side,)
        for side in (BoundarySide.END0, BoundarySide.HIGH, BoundarySide.END1, BoundarySide.LOW)
    )
    half = polygon.inradius_mm / 2
    for delta, count in ((half, 0), (half - Fraction(1, 10**12), 1)):
        points: tuple[Pair, ...] = ((v1[0] + delta, v1[1]), v2, v3, v0)
        proof = BoundaryCycleCandidates(
            polygon,
            candidates,
            checkpoint,
            junctions=BoundaryCycleJunctions(polygon, points, checkpoint),
        )
        assert proof.assignment_count == count and delta < Fraction(1, 100)


def test_foreign_or_missing_junctions_and_resource_expiry_cannot_prepare_queries() -> None:
    """
    Identical coordinates do not waive source object identity, complete incidence or the shared checkpoint.
    """
    _, frame, graph = fixture()
    polygon = MaterialPolygon(frame, graph)
    other = MaterialPolygon(frame, graph)
    candidates = (tuple(BoundarySide),) * 4
    for geometry in (
        BoundaryCycleJunctions(other, polygon.vertices, checkpoint),
        BoundaryCycleJunctions(polygon, polygon.vertices[:3], checkpoint),
    ):
        with pytest.raises(ValueError, match="SAME polygon"):
            BoundaryCycleCandidates(polygon, candidates, checkpoint, junctions=geometry)

    def stop() -> None:
        """
        Refuse further work under an expired caller allocation.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        BoundaryCycleCandidates(
            polygon,
            candidates,
            stop,
            junctions=BoundaryCycleJunctions(polygon, polygon.vertices, checkpoint),
        )
