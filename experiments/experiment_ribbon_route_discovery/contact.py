"""
Measure sampled remote contact and positional closure without repairing geometry.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.edge_clearance import NearPair, Ruling, screen
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase


def audit(
    case: EndpointCase,
    path: CompatiblePath,
    checkpoint: Callable[[], None],
    *,
    pair_observer: Callable[[NearPair], None] | None = None,
) -> tuple[dict[str, Any], tuple[Ruling, ...]]:
    """
    Screen129full-width rulings using actual integrated center material progress.

    Use the historical2Ddistance horizon and3Dlocal-material exclusion,where D is
    ribbon thickness. Return all frozen samples and contact witnesses. No detected
    contact is not a continuous certificate. Keep position and frame outcomes
    separate;the unchanged1e-8frame gate is stricter than practical position closure.
    Forward optional eligible-pair observations without changing samples or filters.
    """
    started = perf_counter()
    half = path.field.half_width_mm
    samples: list[Ruling] = []
    arc = 0.0
    previous_speed = 0.0
    for i in range(129):
        if i % 32 == 0:
            checkpoint()
        u = i / 128
        speed = path.field.carrier(u).progress_mm
        if i:
            middle_speed = path.field.carrier((i - 0.5) / 128).progress_mm
            arc += (previous_speed + 4 * middle_speed + speed) / (6 * 128)
        previous_speed = speed
        eta = path.field.sample(u)[1]
        samples.append(
            Ruling(
                u,
                path.lane(u, half)[0],
                path.lane(u, -half)[0],
                Vector3(arc + half * eta, half, 0),
                Vector3(arc - half * eta, -half, 0),
            )
        )
    result = screen(tuple(samples), case.diameter_mm, checkpoint, pair_observer=pair_observer)
    gaps = tuple(
        magnitude(difference(path.lane(1, q)[0], case.end.translated(case.end_width, q)))
        for q in (-half, 0.0, half)
    )
    pose = path.pose(1)[0]
    tangent_error = magnitude(difference(Vector3(*pose[3:6]), case.end_tangent))
    width_error = magnitude(difference(Vector3(*pose[6:9]), case.end_width))
    result.update(
        maximum_gap_mm=max(gaps),
        position_threshold_mm=case.diameter_mm / 2,
        position_connected=max(gaps) <= case.diameter_mm / 2,
        tangent_vector_error=tangent_error,
        width_vector_error=width_error,
        strict_frame_gate=max(tangent_error, width_error) <= 1e-8,
        total_seconds=perf_counter() - started,
    )
    return result, tuple(samples)
