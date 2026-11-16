"""
Require unique physical endpoint evidence while preserving native provenance and unresolved short edges.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.exact_frame import Point
from experiments.experiment_ribbon_complete.native_boundary_distance import (
    BoundarySide,
    FiniteBoundaryTrace,
)
from experiments.experiment_ribbon_complete.native_trace_direction import (
    NativeEdgeEndpoints,
    NativeTraceDirection,
)
from tests.test_ribbon_complete_native_boundary_distance import bound, fixture
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def translated_points(points: tuple[Point, Point], offset: Fraction) -> tuple[Point, Point]:
    """
    Move both independently captured endpoint coordinates by the same exact world offset.
    """
    moved = [tuple(x + offset for x in p) for p in points]
    return moved[0], moved[1]


def example(length: Fraction = Fraction(2)) -> tuple[FiniteBoundaryTrace, NativeEdgeEndpoints]:
    """
    Pair a straight generator with independently specified physical endpoint coordinates.
    """
    native, frame, graph = fixture()
    finite = bound(
        native, frame, graph, BoundarySide.END0, ((Fraction(0), Fraction(0)), (length, Fraction(0)))
    )
    q, b = map(Fraction, graph.conic.arc.controls[0])
    endpoints = NativeEdgeEndpoints(
        native.revision,
        finite.trace.curve.edge_id,
        (10, 11),
        ((Fraction(0), q, b), (length, q, b)),
        (native.face_index,),
    )
    return finite, endpoints


@pytest.mark.parametrize("vertices,reverse", [((10, 11), False), ((11, 10), True)])
def test_physical_vertices_establish_unique_direction(
    vertices: tuple[int, int], reverse: bool
) -> None:
    """
    Directed vertex order determines whether original curve parameters must be traversed backward.
    """
    finite, native = example()
    proof = NativeTraceDirection(finite.trace, native, vertices, checkpoint)
    assert proof.reversed is reverse and proof.endpoint_upper_mm == Fraction(0)
    assert max(proof.assignment_errors_mm[int(not reverse)]) == Fraction(2)
    directed = proof.directed(finite)
    assert directed.finite is finite and directed.reversed is reverse
    assert (directed.start_vertex, directed.end_vertex) == vertices


@pytest.mark.parametrize(
    "field,value", [("revision", "other"), ("edge_id", 99), ("incident_faces", (99,))]
)
def test_other_native_ownership_cannot_inherit_an_endpoint_match(field: str, value: object) -> None:
    """
    Numerically identical endpoints do not waive revision, edge or incident-face identity.
    """
    finite, native = example()
    with pytest.raises(ValueError, match="SAME revision"):
        NativeTraceDirection(finite.trace, replace(native, **{field: value}), (10, 11), checkpoint)
    with pytest.raises(ValueError, match="SAME revision"):
        NativeTraceDirection(finite.trace, native, (10, 12), checkpoint)


def test_short_edge_remains_ambiguous_even_with_one_exact_assignment() -> None:
    """
    Smaller numerical error does not resolve discrete orientation when both assignments fit the accuracy.
    """
    finite, native = example(Fraction(1, 1000))
    proof = NativeTraceDirection(finite.trace, native, native.vertex_ids, checkpoint)
    assert proof.assignment_errors_mm[0] == (0, 0)
    assert proof.reversed is None and proof.endpoint_upper_mm is None
    with pytest.raises(ValueError, match="uniquely directed"):
        proof.directed(finite)


def test_unmatched_endpoints_and_foreign_trace_do_not_produce_a_direction() -> None:
    """
    Missing physical matches and a separately constructed finite trace cannot reuse an association.
    """
    finite, native = example()
    displaced = replace(native, points_mm=translated_points(native.points_mm, Fraction(1)))
    proof = NativeTraceDirection(finite.trace, displaced, native.vertex_ids, checkpoint)
    assert proof.reversed is None
    unique = NativeTraceDirection(finite.trace, native, native.vertex_ids, checkpoint)
    foreign, _ = example()
    with pytest.raises(ValueError, match="SAME finite trace"):
        unique.directed(foreign)


def test_shared_world_translation_and_resource_stop_preserve_the_contract() -> None:
    """
    World origin has no effect on assignment, and every evaluation observes the caller's stop gate.
    """
    finite, native = example()
    surface = finite.trace.surface
    moved_surface = replace(
        surface, rows=tuple(tuple(tuple(x + 100 for x in p) for p in row) for row in surface.rows)
    )
    moved_trace = replace(finite.trace, surface=moved_surface, checkpoint=checkpoint)
    moved_native = replace(native, points_mm=translated_points(native.points_mm, Fraction(100)))
    proof = NativeTraceDirection(moved_trace, moved_native, native.vertex_ids, checkpoint)
    assert proof.reversed is False and proof.endpoint_upper_mm == Fraction(0)

    def stop() -> None:
        """
        Refuse further endpoint association after allocation expiry.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        NativeTraceDirection(finite.trace, native, native.vertex_ids, stop)


@pytest.mark.parametrize(
    "field,value",
    [
        ("vertex_ids", (10, [])),
        ("points_mm", None),
        ("points_mm", (None, None)),
        ("incident_faces", (True,)),
    ],
)
def test_malformed_native_endpoint_records_are_rejected(field: str, value: object) -> None:
    """
    Malformed external coordinates and identifiers fail before hashing or nested arithmetic.
    """
    _, native = example()
    with pytest.raises(ValueError, match="Complete distinct"):
        replace(native, **{field: value})
