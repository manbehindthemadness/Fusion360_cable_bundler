"""
Distinguish source-side request readiness from ambiguous endpoints and whole-curve geometry coverage.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.boundary_endpoint_candidates import (
    BoundaryEndpointCandidates,
)
from experiments.experiment_ribbon_complete.flat_chart import MaterialCut
from experiments.experiment_ribbon_complete.native_boundary_distance import BoundarySide
from tests.test_ribbon_complete_native_boundary_distance import fixture
from tests.test_ribbon_complete_volume_injectivity import checkpoint


@pytest.mark.parametrize("side", list(BoundarySide))
def test_independent_physical_endpoints_can_uniquely_request_each_finite_side(
    side: BoundarySide,
) -> None:
    """
    Whole-side endpoints select one query orientation while retaining all other measured errors.
    """
    _, frame, graph = fixture()
    q0, q1 = graph.interval
    zero, two, b = Fraction(0), Fraction(2), Fraction(0.8)
    pairs = {
        BoundarySide.LOW: ((zero, q0, b), (zero, q1, b)),
        BoundarySide.HIGH: ((two, q0, b), (two, q1, b)),
        BoundarySide.END0: ((zero, q0, b), (two, q0, b)),
        BoundarySide.END1: ((zero, q1, b), (two, q1, b)),
    }
    proof = BoundaryEndpointCandidates(frame, graph, pairs[side], checkpoint)
    assert proof.unique_side is side and proof.eligible == (side,)
    assert proof.errors_mm[side.value] == Fraction(0)


def test_thin_source_strip_does_not_choose_the_smaller_of_two_acceptable_errors() -> None:
    """
    Exact coincidence with one cut does not justify guessing when both cuts satisfy the physical accuracy.
    """
    _, frame, graph = fixture()
    frame = replace(frame, high=MaterialCut(Fraction(1, 200)))
    points = tuple((Fraction(0), q, Fraction(0.8)) for q in graph.interval)
    proof = BoundaryEndpointCandidates(frame, graph, (points[0], points[1]), checkpoint)
    assert proof.eligible == (BoundarySide.LOW, BoundarySide.HIGH)
    assert proof.errors_mm[0] < proof.errors_mm[1]
    assert proof.unique_side is None


def test_corner_point_and_outside_points_do_not_establish_unique_edge_sides() -> None:
    """
    A point at a corner is ambiguous and a far-away pair has no finite source association.
    """
    _, frame, graph = fixture()
    corner = (Fraction(0), graph.interval[0], Fraction(0.8))
    assert (
        BoundaryEndpointCandidates(frame, graph, (corner, corner), checkpoint).unique_side is None
    )
    outside = (Fraction(10), Fraction(10), Fraction(10))
    assert BoundaryEndpointCandidates(frame, graph, (outside, outside), checkpoint).eligible == ()


def test_source_changes_recompute_request_evidence_and_resource_stop_is_observed() -> None:
    """
    A prior fit cannot transfer across changed original cuts or an exhausted allocation.
    """
    _, frame, graph = fixture()
    points = tuple((Fraction(2), q, Fraction(0.8)) for q in graph.interval)
    original = BoundaryEndpointCandidates(frame, graph, (points[0], points[1]), checkpoint)
    changed = replace(
        original, frame=replace(frame, high=MaterialCut(Fraction(3))), checkpoint=checkpoint
    )
    assert original.unique_side is BoundarySide.HIGH and changed.unique_side is None

    def stop() -> None:
        """
        Refuse further endpoint work after the shared allocation expires.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        BoundaryEndpointCandidates(frame, graph, (points[0], points[1]), stop)
