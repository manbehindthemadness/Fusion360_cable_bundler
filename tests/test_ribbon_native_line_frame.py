"""
Keep actual native line geometry and authored boundaries in the same assembly frame.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from tests.test_ribbon_native_correspondence import Point
from tests.test_ribbon_native_line_boundary import _edge, _shared_collection


class _MovedPoint(Point):
    """
    Model a native point transformed from the owned component into its assembly frame.
    """

    def copy(self) -> _MovedPoint:
        """
        Keep the authored sample independent of its transformed measurement copy.
        """
        return _MovedPoint(self.x, self.y, self.z)

    def transformBy(self, matrix: Any) -> bool:
        """
        Apply a declared translation without changing the source material point.
        """
        self.x += matrix[0]
        self.y += matrix[1]
        self.z += matrix[2]
        return True


@pytest.mark.parametrize("control_hull", (False, True))
def test_native_edge_certificate_uses_actual_proxy_frame_and_original_source_memberships(
    control_hull: bool,
) -> None:
    """
    Transform source copies once, use proxy endpoints, and still query original component-space faces.
    """
    collection, edge, source_points = _shared_collection()
    collection.occurrence.transform2 = (10.0, -2.0, 3.0)
    proxy = _edge(Point(10, -1, 3), Point(14, -1, 3))
    proxy.evaluator.getParameterAtPoint = lambda point: (True, 2 + (point.x - 10) / 4 * 5)
    edge.createForAssemblyContext = lambda _occurrence: proxy
    points = tuple(_MovedPoint(point.x, point.y, point.z) for point in source_points)
    collection.distance = Mock(
        side_effect=AssertionError("No distance fallback needed for certified line")
    )
    controls = (points[0], points[-1]) if control_hull else ()
    error = collection.edge_seam_error(0, 2, points, controls=controls)
    assert 0 <= error <= 1e-6
    assert all(point.y == 1 and point.z == 0 for point in points)
    assert collection.distance_queries == 0
    assert len(collection.output["face_correspondence"]["native_line_boundaries"]) == int(
        control_hull
    )
    assert collection.edge_queries == (0 if control_hull else 9)
