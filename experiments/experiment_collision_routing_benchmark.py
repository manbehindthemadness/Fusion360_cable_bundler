"""
Measure the interactive collision-validation target without requiring Fusion.
"""

from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter
from uuid import UUID

ADDIN_ROOT = Path(__file__).resolve().parent.parent
if str(ADDIN_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDIN_ROOT))

from wire_bundler.routing import (  # noqa: E402
    RoutePreview,
    Vector3,
    fair_route,
    route_collisions,
)

GROUP_COUNT = 50
GUIDE_COUNT = 20
TARGET_SECONDS = 1.0


def run_benchmark() -> tuple[float, int]:
    """
    Validate fifty distinct routes across twenty guide sections.

    Returns:
        Elapsed seconds and the number of reported conflicting route pairs.
    """
    routes = []
    group_ids = []
    for index in range(GROUP_COUNT):
        x = float(index % 10) * 2.0
        y = float(index // 10) * 2.0
        points = tuple(Vector3(x, y, float(guide) * 10.0) for guide in range(GUIDE_COUNT))
        normal = Vector3(0.0, 0.0, 1.0)
        route = RoutePreview(UUID(int=index + 1), f"Group {index + 1}", points)
        routes.append(fair_route(route, (normal,) * GUIDE_COUNT, minimum_bend_radius_mm=0.525))
        group_ids.append(UUID(int=1000 + index))
    started = perf_counter()
    collisions = route_collisions(
        tuple(routes),
        tuple(group_ids),
        (1.0,) * GROUP_COUNT,
    )
    return perf_counter() - started, len(collisions)


if __name__ == "__main__":
    elapsed, collision_count = run_benchmark()
    status = "PASS" if elapsed <= TARGET_SECONDS else "SLOW"
    print(
        f"{status}: {GROUP_COUNT} groups x {GUIDE_COUNT} guides in {elapsed:.3f}s; "
        f"{collision_count} collision pairs."
    )
