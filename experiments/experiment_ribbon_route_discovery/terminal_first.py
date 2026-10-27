"""
Solve from the terminal pose and reverse the retained material parameter exactly.
"""

from __future__ import annotations

from dataclasses import replace

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_ribbon_cap_transition.compatible_shooting import field_for
from experiments.experiment_ribbon_cap_transition.compatible_strip import (
    BendMapping,
    CompatiblePath,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase


def reverse_case(case: EndpointCase) -> EndpointCase:
    """
    Exchange fixed endpoint poses,reverse tangents and preserve width/conductor order.
    """
    return replace(
        case,
        start=case.end,
        end=case.start,
        start_tangent=Vector3(
            *(-v for v in (case.end_tangent.x, case.end_tangent.y, case.end_tangent.z))
        ),
        end_tangent=Vector3(
            *(-v for v in (case.start_tangent.x, case.start_tangent.y, case.start_tangent.z))
        ),
        start_width=case.end_width,
        end_width=case.start_width,
    )


def reverse_coordinates(values: tuple[float, ...]) -> tuple[float, ...]:
    """
    Transform k(u)=-k_rev(1-u),eta(u)=-eta_rev(1-u) in the same Fourier chart.
    """
    if len(values) != 10:
        raise ValueError("Terminal-first coordinates require the same ten-coordinate chart.")
    return tuple(sign * value for sign, value in zip((-1, -1, 1, 1, -1, -1, 1, 1, -1, 1), values))


def restore_order(
    case: EndpointCase, reversed_path: CompatiblePath, reversed_values: tuple[float, ...]
) -> CompatiblePath:
    """
    Reorient the exact retained cubic path,without translating or reintegrating it.

    A failed reverse solve may miss the original START. Preserve that failure and
    measure both endpoint poses;an exact original end cannot conceal a start miss.
    Positive conductor offsets remain the same physical width side throughout.
    """
    values = reverse_coordinates(reversed_values)
    field = field_for(case, values, bend_mapping=BendMapping.NEAR_LIMIT)
    states = tuple(
        state[:3] + tuple(-v for v in state[3:6]) + state[6:9]
        for state in reversed(reversed_path.states)
    )
    rates = tuple(
        tuple(-v for v in rate[:3]) + rate[3:6] + tuple(-v for v in rate[6:9])
        for rate in reversed(reversed_path.rates)
    )
    return CompatiblePath(field, states, rates)


def both_end_errors(case: EndpointCase, path: CompatiblePath) -> dict[str, float]:
    """
    Measure all A/center/B positions and both tangent/width frames against fixed inputs.
    """
    gaps = []
    frames = []
    half = path.field.half_width_mm
    for u, target, tangent, width in (
        (0.0, case.start, case.start_tangent, case.start_width),
        (1.0, case.end, case.end_tangent, case.end_width),
    ):
        gaps.extend(
            magnitude(difference(path.lane(u, q)[0], target.translated(width, q)))
            for q in (-half, 0.0, half)
        )
        state, _ = path.pose(u)
        frames.extend(
            (
                magnitude(difference(Vector3(*state[3:6]), tangent)),
                magnitude(difference(Vector3(*state[6:9]), width)),
            )
        )
    return {"maximum_gap_mm": max(gaps), "maximum_frame_error": max(frames)}
