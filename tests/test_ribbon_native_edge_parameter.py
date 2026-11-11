"""
Keep sampled native edge witnesses inside actual trim ranges and existing shared query ceilings.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_locked_solver.edge_parameter import inspect
from tests.test_ribbon_native_correspondence import Point
from tests.test_ribbon_native_line_boundary import _edge, _shared_collection


def _arc() -> Any:
    """
    Supply an actual quarter-circle evaluator with independently computed native positions.
    """
    return SimpleNamespace(
        evaluator=SimpleNamespace(
            getParameterExtents=lambda: (True, 0.0, math.pi / 2),
            getParameterAtPoint=lambda point: (True, math.atan2(point.y, point.x)),
            getPointAtParameter=lambda value: (True, Point(math.cos(value), math.sin(value))),
        )
    )


@pytest.mark.parametrize("fraction", (0.0, 0.25, 0.5, 0.75, 1.0))
def test_curved_native_sample_requires_actual_parameter_range_and_three_dimensional_error(
    fraction: float,
) -> None:
    """
    Verify the native support itself, including true curved points away from the endpoint chord.
    """
    angle = fraction * math.pi / 2
    point = Point(math.cos(angle), math.sin(angle), 2e-8)
    measured = inspect(_arc(), point, 1e-6, lambda: None)
    assert measured is not None and measured.parameter == pytest.approx(angle)
    assert measured.error_mm == pytest.approx(2e-7)


@pytest.mark.parametrize("invalid", ("outside", "wrong_inverse", "warning", "failed", "nan"))
def test_inverse_success_or_infinite_support_cannot_approve_a_trimmed_edge(invalid: str) -> None:
    """
    Decline distant/out-of-trim, non-goal and malformed native projections without false clearance.
    """
    edge = _arc()
    point = Point(math.cos(0.8), math.sin(0.8))
    if invalid == "outside":
        point = Point(-1, 0)
    elif invalid == "wrong_inverse":
        edge.evaluator.getParameterAtPoint = lambda _point: (True, 0.1)
    elif invalid == "warning":
        point.z = 2e-7
    elif invalid == "failed":
        edge.evaluator.getPointAtParameter = lambda _value: (False, None)
    else:
        edge.evaluator.getParameterAtPoint = lambda _point: (True, math.nan)
    assert inspect(edge, point, 1e-6, lambda: None) is None


def test_near_trim_endpoint_is_a_valid_witness_but_cancellation_cannot_fall_back() -> None:
    """
    A clamped parameter names a real endpoint; caller interruption remains authoritative.
    """
    measured = inspect(_arc(), Point(1, -2e-8), 1e-6, lambda: None)
    assert measured is not None and measured.parameter == 0.0
    with pytest.raises(InterruptedError, match="source guard"):
        inspect(_arc(), Point(1, 0), 1e-6, Mock(side_effect=InterruptedError("source guard")))


def test_full_correspondence_retains_sample_ownership_and_uses_existing_raw_query_pool() -> None:
    """
    Native curve witnesses replace expensive distances without omitting any original face checks.
    """
    collection, edge, points = _shared_collection()
    edge.geometry.objectType = "adsk::core::NurbsCurve3D"
    edge.evaluator.getParameterAtPoint = lambda point: (True, 2.0 + point.x / 4 * 5)
    faces = Mock(wraps=collection.select)
    collection.select = faces
    collection.distance = Mock(side_effect=AssertionError("No minimum-distance call needed"))
    error = collection.edge_seam_error(0, 2, points)
    assert 0 <= error <= 1e-6 and faces.call_count == 18
    assert collection.distance_queries == 0 and collection.edge_queries == 9
    report = collection.output["face_correspondence"]["native_edge_subchains"][-1]
    assert report["samples"] == report["parameter_witness_samples"] == 9
    collection.queries = 30000
    collection.select = Mock(return_value=object())
    with pytest.raises(RuntimeError, match="shared native-query budget exhausted"):
        collection.edge_seam_error(0, 2, points)


def test_warning_only_native_witness_keeps_full_minimum_search_over_all_shared_edges() -> None:
    """
    Two non-goal supports still require all original distance comparisons and retain the true minimum.
    """
    collection, first, points = _shared_collection()
    first.evaluator = _edge(Point(0, 1 + 4e-7), Point(4, 1 + 4e-7)).evaluator
    first.evaluator.getParameterAtPoint = lambda point: (True, 2.0 + point.x / 4 * 5)
    second = _edge(Point(0, 1 + 3e-7), Point(4, 1 + 3e-7))
    second.tempId = 43
    second.evaluator.getParameterAtPoint = lambda point: (True, 2.0 + point.x / 4 * 5)
    collection.native[0].edges = collection.native[1].edges = [first, second]

    def distance(point: Point, edge: Any) -> float:
        """
        Independently measure actual finite horizontal native segments in the mocked API boundary.
        """
        ok, projected = edge.evaluator.getPointAtParameter(
            2.0 + min(4.0, max(0.0, point.x)) / 4 * 5
        )
        assert ok
        return point.distanceTo(projected) * 10

    collection.distance = Mock(side_effect=distance)
    error = collection.edge_seam_error(0, 2, points)
    assert error == pytest.approx(3e-6)
    assert collection.distance_queries == collection.edge_queries == 18
    assert (
        collection.output["face_correspondence"]["native_edge_subchains"][-1][
            "parameter_witness_samples"
        ]
        == 0
    )
