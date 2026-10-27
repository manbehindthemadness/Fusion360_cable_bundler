"""
Explore fixed endpoints from the destination using the unchanged material chart.

Backward fits are initialization only. Reversed coordinates are transported and
polished from the original start; only original-target audits can accept them.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Iterator

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from . import box_fit, broad_chart
from .families import Seed, select


def reverse_case(case: EndpointCase) -> EndpointCase:
    """
    Exchange endpoints and negate travel tangents without swapping conductor order.
    """
    return replace(
        case,
        start=case.end,
        end=case.start,
        start_tangent=Vector3(0, 0, 0).translated(case.end_tangent, -1),
        end_tangent=Vector3(0, 0, 0).translated(case.start_tangent, -1),
        start_width=case.end_width,
        end_width=case.start_width,
    )


def reverse_coordinates(values: tuple[float, ...]) -> tuple[float, ...]:
    """
    Express k_rev(u)=-k(1-u), eta_rev(u)=-eta(1-u) in the same Fourier basis.

    The carrier and absolute ruling-gradient normalization are invariant. Width
    identity is retained; the travel tangent reverses. This is an involution,
    not an endpoint correction or a replacement for forward integration.
    """
    if len(values) != 10:
        raise ValueError("Reversal requires ten chart coordinates.")
    signs = (-1, -1, 1, 1, -1, -1, 1, 1, -1, 1)
    return tuple(sign * value for sign, value in zip(signs, values))


def candidates(
    case: EndpointCase, checkpoint: Callable[[], None]
) -> Iterator[tuple[CompatiblePath, dict[str, Any]]]:
    """
    Screen110 backward starts and fit at most two distinct families, then polish.

    At most1222 transports:110 screens plus two506 backward fits and two50
    forward polishes, with no width repair. Errors propagate to the caller's
    bounded ledger. Backward closure never counts as original-case acceptance.
    """
    backward = reverse_case(case)
    starts = select(broad_chart.screen(backward, checkpoint), maximum=2)
    for seed in starts:
        _, backward_metrics = box_fit.refine(backward, seed, checkpoint, box_fit.DEEP)
        forward_seed = Seed(
            seed.index,
            reverse_coordinates(backward_metrics["coordinates"]),
            backward_metrics["score"],
            (),
        )
        path, metrics = box_fit.refine(case, forward_seed, checkpoint, box_fit.POLISH)
        metrics.update(backward_fit=backward_metrics, backward_seed=seed.index)
        yield path, metrics
