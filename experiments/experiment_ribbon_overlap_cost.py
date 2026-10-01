"""
Measure the current ribbon overlap fitter with deterministic containment doubles.

Run explicitly with ``uv run pytest experiments/experiment_ribbon_overlap_cost.py -s``.
This does not load Fusion or modify a design. Its wall time measures Python work
only; the query count predicts how many native Fusion calls a live fit makes.
"""

from __future__ import annotations

import json
import math
from time import perf_counter
from types import SimpleNamespace
from uuid import UUID

import pytest

from tests.fusion_ui_support import addin_module as _fusion_addin_module  # noqa: F401


@pytest.mark.usefixtures("_fusion_addin_module")
@pytest.mark.parametrize("clearance_mm", [0.5, 0.35, 0.25])
def test_overlap_query_cost(
    monkeypatch: pytest.MonkeyPatch,
    clearance_mm: float,
) -> None:
    """
    Report query counts and Python-only timings for nineteen equivalent roots.
    """
    from cable_bundler.fusion.cable_solid_parts import ribbon_overlap
    from cable_bundler.fusion.ribbon_geometry import RibbonGuidePlane
    from cable_bundler.routing import CubicBezier, RoutePreview, Vector3

    monkeypatch.setitem(
        vars(ribbon_overlap.adsk.fusion),
        "PointContainment",
        SimpleNamespace(
            PointInsidePointContainment=0,
            PointOnPointContainment=1,
            PointOutsidePointContainment=2,
        ),
    )
    monkeypatch.setitem(vars(ribbon_overlap), "fusion_point", lambda point, _transform: point)
    outside, end = Vector3(-2.0, 0.0, 0.0), Vector3(0.0, 0.0, 0.0)
    route = RoutePreview(
        UUID(int=1), "Root", (outside, end), (CubicBezier(outside, outside, end, end),)
    )
    plane = RibbonGuidePlane(end, Vector3(1.0, 0.0, 0.0))

    class CircularRibbonBody:
        """
        Count the same containment boundary checks delegated to Fusion.
        """

        def __init__(self) -> None:
            """
            Start with no native-equivalent classification queries.
            """
            self.queries = 0

        def pointContainment(self, point: Vector3) -> int:
            """
            Model a constant circular clearance around the inward branch axis.
            """
            self.queries += 1
            return 0 if math.hypot(point.y, point.z) <= clearance_mm else 2

    body = CircularRibbonBody()
    started = perf_counter()
    fitted = tuple(
        ribbon_overlap.fitted_ribbon_overlap_diameter(body, route, plane, 0.9, object())
        for _ in range(19)
    )
    elapsed = perf_counter() - started
    assert all(value == fitted[0] for value in fitted)
    assert body.queries > 0
    print(
        json.dumps(
            {
                "clearance_mm": clearance_mm,
                "roots": len(fitted),
                "fitted_diameter_mm": fitted[0],
                "containment_queries": body.queries,
                "queries_per_root": body.queries // len(fitted),
                "python_only_seconds": round(elapsed, 4),
            },
            sort_keys=True,
        )
    )
