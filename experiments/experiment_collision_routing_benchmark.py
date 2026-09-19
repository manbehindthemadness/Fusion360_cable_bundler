"""
Measure complete collision-routing workloads without requiring Fusion.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from uuid import UUID

ADDIN_ROOT = Path(__file__).resolve().parent.parent
if str(ADDIN_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDIN_ROOT))

from wire_bundler.routing import (  # noqa: E402
    RoutePreview,
    TransitionLengths,
    Vector3,
    fair_route,
    route_collisions,
    separate_route_collisions,
)
from wire_bundler.routing.conditioning import (  # noqa: E402
    CircularGuideConstraint,
    condition_control_points,
    condition_route_normals,
)

GUIDE_COUNT = 20


@dataclass(frozen=True)
class BenchmarkResult:
    """
    Store the independently useful timings for one routing scenario.
    """

    name: str
    fairing_seconds: float
    collision_seconds: float
    collision_pairs: int

    @property
    def total_seconds(self) -> float:
        """
        Return complete host-independent path-making time.
        """
        return self.fairing_seconds + self.collision_seconds


def run_benchmark() -> tuple[BenchmarkResult, ...]:
    """
    Measure clear high-volume routing at two scales and collision-heavy repair.
    """
    return _clear_routes_benchmark(50), _clear_routes_benchmark(200), _crowded_routes_benchmark()


def _clear_routes_benchmark(group_count: int) -> BenchmarkResult:
    """
    Condition, fair, and validate distinct routes across twenty guide sections.
    """
    raw_routes = []
    normals = []
    group_ids = []
    for index in range(group_count):
        x = float(index % 10) * 2.0
        y = float(index // 10) * 2.0
        points = tuple(Vector3(x, y, float(guide) * 10.0) for guide in range(GUIDE_COUNT))
        raw_routes.append(RoutePreview(UUID(int=index + 1), f"Group {index + 1}", points))
        normals.append((Vector3(0.0, 0.0, 1.0),) * GUIDE_COUNT)
        group_ids.append(UUID(int=1000 + index))
    control_ids = tuple(UUID(int=9000 + guide) for guide in range(GUIDE_COUNT))
    transitions = ((TransitionLengths(),) * GUIDE_COUNT,) * group_count
    route_control_ids = (control_ids,) * group_count
    started = perf_counter()
    conditioned_routes = condition_control_points(
        tuple(raw_routes),
        tuple(group_ids),
        (1.0,) * group_count,
        route_control_ids,
        transitions,
        {
            control_id: CircularGuideConstraint(
                Vector3(0.0, 0.0, float(guide) * 10.0),
                Vector3(0.0, 0.0, 1.0),
                Vector3(1.0, 0.0, 0.0),
                Vector3(0.0, 1.0, 0.0),
                1000.0,
            )
            for guide, control_id in enumerate(control_ids)
        },
        0.5,
    )
    routes = tuple(
        fair_route(
            route,
            condition_route_normals(
                route,
                route_normals,
                (TransitionLengths(),) * GUIDE_COUNT,
                frozenset(range(1, GUIDE_COUNT - 1)),
                frozenset(),
                0.5,
            ),
            minimum_bend_radius_mm=0.525,
            auto_transition_fraction=0.5,
        )
        for route, route_normals in zip(conditioned_routes, normals)
    )
    fairing_seconds = perf_counter() - started
    started = perf_counter()
    collisions = route_collisions(routes, tuple(group_ids), (1.0,) * group_count)
    collision_seconds = perf_counter() - started
    return BenchmarkResult(
        f"clear {group_count} routes x {GUIDE_COUNT} guides",
        fairing_seconds,
        collision_seconds,
        len(collisions),
    )


def _crowded_routes_benchmark() -> BenchmarkResult:
    """
    Fair and repair several independently owned routes crossing one region.
    """
    route_count = 4
    raw_routes = []
    normals = []
    for index in range(route_count):
        angle = math.pi * index / route_count
        direction = Vector3(math.cos(angle), math.sin(angle), 0.0)
        raw_routes.append(
            RoutePreview(
                UUID(int=2000 + index),
                f"Crowded {index + 1}",
                (
                    Vector3(-direction.x * 20.0, -direction.y * 20.0, 0.0),
                    Vector3(direction.x * 20.0, direction.y * 20.0, 0.0),
                ),
            )
        )
        normals.append((direction, direction))
    transitions = ((TransitionLengths(), TransitionLengths()),) * route_count
    started = perf_counter()
    routes = tuple(
        fair_route(route, route_normals, minimum_bend_radius_mm=1.05)
        for route, route_normals in zip(raw_routes, normals)
    )
    fairing_seconds = perf_counter() - started
    started = perf_counter()
    _separated, collisions = separate_route_collisions(
        routes,
        tuple(UUID(int=3000 + index) for index in range(route_count)),
        (2.0,) * route_count,
        tuple(normals),
        transitions,
        (1.05,) * route_count,
        0.0,
    )
    collision_seconds = perf_counter() - started
    return BenchmarkResult(
        f"crowded {route_count}-route repair",
        fairing_seconds,
        collision_seconds,
        len(collisions),
    )


if __name__ == "__main__":
    for result in run_benchmark():
        print(
            f"{result.name}: total={result.total_seconds:.3f}s "
            f"fairing={result.fairing_seconds:.3f}s "
            f"collision={result.collision_seconds:.3f}s "
            f"residual_pairs={result.collision_pairs}"
        )
