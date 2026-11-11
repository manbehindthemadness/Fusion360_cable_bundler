"""
Require actual finite native-line geometry and complete source coverage for boundary certificates.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_locked_solver.correspondence import MaterialFaces
from experiments.experiment_ribbon_locked_solver.line_boundary import LINE_TYPE, certify
from tests.test_ribbon_native_correspondence import Point, _collection, _cover


def _edge(start: Point, end: Point, kind: str | None = LINE_TYPE) -> Any:
    """
    Supply an independently evaluated trimmed native segment with real test-double topology identity.
    """
    edge = SimpleNamespace(
        tempId=42,
        geometry=SimpleNamespace(objectType=kind),
        evaluator=SimpleNamespace(
            getParameterExtents=lambda: (True, 2.0, 7.0),
            getPointAtParameter=lambda value: (
                True,
                Point(
                    *(
                        a + (value - 2.0) / 5.0 * (b - a)
                        for a, b in zip((start.x, start.y, start.z), (end.x, end.y, end.z))
                    )
                ),
            ),
        ),
    )
    edge.createForAssemblyContext = lambda _occurrence: edge
    return edge


def _shared_collection() -> tuple[MaterialFaces, Any, tuple[Point, ...]]:
    """
    Establish sealed actual face families with one common finite line and nine source samples.
    """
    collection, faces = _collection()
    _cover(collection)
    collection.seal_surfaces()
    edge = _edge(Point(0, 1), Point(4, 1))
    faces[0].edges = faces[1].edges = [edge]
    points = tuple(Point(0.5 + 3 * i / 8, 1) for i in range(9))
    return collection, edge, points


@pytest.mark.parametrize("shift", (0.0, 1e3, 1e6))
def test_outward_control_hull_bound_covers_positive_rational_seam_and_all_samples(
    shift: float,
) -> None:
    """
    Bound a curved positive-weight source seam near one finite line in several world-coordinate ranges.
    """
    controls = (Point(shift, 2e-8), Point(shift + 1, 4e-8), Point(shift + 2, 2e-8))
    points = []
    for index in range(9):
        value = index / 8
        weights = ((1 - value) ** 2, 1.6 * value * (1 - value), value**2)
        denominator = sum(weights)
        points.append(
            Point(
                *(
                    sum(getattr(point, axis) * weight for point, weight in zip(controls, weights))
                    / denominator
                    for axis in "xyz"
                )
            )
        )
    edge = _edge(Point(shift, 0), Point(shift + 2, 0))
    measured = certify(edge, controls, tuple(points), 1e-6, lambda: None)
    assert measured is not None and measured.controls == 3 and measured.samples == 9
    actual = max(abs(point.y) * 10 for point in (*controls, *points))
    assert actual <= measured.maximum_error_mm <= 1e-6


def test_supporting_infinite_line_or_topology_vertices_cannot_replace_finite_edge_extents() -> None:
    """
    Reject collinear source data outside the actual trimmed line, even with misleading far vertices.
    """
    edge = _edge(Point(0, 0), Point(2, 0))
    edge.startVertex = SimpleNamespace(geometry=Point(-10, 0))
    edge.endVertex = SimpleNamespace(geometry=Point(10, 0))
    controls = (Point(-0.1, 0), Point(1.0, 0))
    assert certify(edge, controls, controls, 1e-6, lambda: None) is None


@pytest.mark.parametrize("kind", ("adsk::core::Arc3D", "adsk::core::NurbsCurve3D", None))
def test_unknown_or_curved_native_geometry_cannot_receive_a_convex_line_certificate(
    kind: str | None,
) -> None:
    """
    An actual native line type is mandatory even when a mocked evaluator would return collinear points.
    """
    edge = _edge(Point(0, 0), Point(2, 0), kind)
    checkpoint = Mock()
    assert certify(edge, (Point(0, 0),), (Point(1, 0),), 1e-6, checkpoint) is None
    checkpoint.assert_not_called()


@pytest.mark.parametrize("invalid", ("empty", "extents", "point", "nan", "warning"))
def test_missing_failed_or_non_goal_geometry_retains_the_original_distance_search(
    invalid: str,
) -> None:
    """
    Decline incomplete native data, warning-only bounds and nonfinite controls without granting clearance.
    """
    edge = _edge(Point(0, 0), Point(2, 0))
    controls = (Point(0.5, 0), Point(1.5, 0))
    if invalid == "empty":
        controls = ()
    elif invalid == "extents":
        edge.evaluator.getParameterExtents = lambda: (False, 0.0, 1.0)
    elif invalid == "point":
        edge.evaluator.getPointAtParameter = lambda _value: (False, None)
    elif invalid == "nan":
        controls = (Point(math.nan, 0),)
    else:
        controls = (Point(0.5, 2e-7), Point(1.5, 2e-7))
    assert certify(edge, controls, (Point(1, 0),), 1e-6, lambda: None) is None


def test_hard_cancellation_during_native_geometry_read_is_not_a_missed_certificate() -> None:
    """
    Preserve the original resource/source guard instead of invoking a second proof after cancellation.
    """
    with pytest.raises(InterruptedError, match="source guard"):
        certify(
            _edge(Point(0, 0), Point(2, 0)),
            (Point(1, 0),),
            (Point(1, 0),),
            1e-6,
            Mock(side_effect=InterruptedError("source guard")),
        )


@pytest.mark.parametrize("controls_present", (False, True))
def test_full_correspondence_keeps_all_sample_memberships_and_avoids_only_redundant_line_distances(
    controls_present: bool,
) -> None:
    """
    Use actual owned face families and a shared native edge; preserve all original nine sample checks.
    """
    collection, edge, points = _shared_collection()
    controls = (points[0], points[-1]) if controls_present else ()
    selected = Mock(wraps=collection.select)
    collection.select = selected
    distance = Mock(return_value=0.0)
    collection.distance = distance
    result = collection.edge_seam_error(0, 2, points, controls=controls)
    assert 0 <= result <= 1e-6
    assert selected.call_count == 18
    assert distance.call_count == collection.distance_queries == (0 if controls_present else 9)
    receipts = collection.output["face_correspondence"]["native_line_boundaries"]
    assert len(receipts) == int(controls_present)
    if receipts:
        assert receipts[0]["native_edge"] == edge.tempId and receipts[0]["samples"] == 9


def test_valid_line_hull_cannot_replace_native_face_ownership_or_expire_the_old_distance_cap() -> (
    None
):
    """
    Refuse missing face membership, and retain the unchanged cap for non-line native queries.
    """
    collection, edge, points = _shared_collection()
    collection.select = Mock(return_value=None)
    assert math.isinf(collection.edge_seam_error(0, 2, points, controls=(points[0], points[-1])))
    assert not collection.output["face_correspondence"]["native_line_boundaries"]
    edge.geometry.objectType = "adsk::core::Arc3D"
    collection.select = Mock(return_value=object())
    collection.distance_queries = 512
    with pytest.raises(RuntimeError, match="boundary-distance budget exhausted"):
        collection.edge_seam_error(0, 2, points, controls=(points[0], points[-1]))
