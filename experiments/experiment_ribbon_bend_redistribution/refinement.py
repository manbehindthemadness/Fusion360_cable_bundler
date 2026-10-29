"""
Compare ordinary warm continuation against one explicit redistribution proposal.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery import box_fit, broad_chart
from experiments.experiment_ribbon_route_discovery.families import Seed
from experiments.experiment_ribbon_tangent_tightening.field import TangentTightening
from experiments.experiment_ribbon_tangent_tightening.refinement import tighten

from .allocation import propose

WARM = box_fit.FitWork(10, 3, 158)


def redistribute(
    case: EndpointCase,
    original: CompatiblePath,
    coordinates: tuple[float, ...],
    checkpoint: Callable[[], None],
    *,
    tightening: TangentTightening | None = None,
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Spend at most158fit transports after one five-coordinate allocation proposal.

    A missing proposal still receives ordinary continuation for a matched-work
    comparison. This is warm fitting;callers retain original solve costs and run
    unchanged independent endpoint,intrinsic,cubic and full-width contact checks.
    Explicit terminal tightening shares this same transport cap; it adds local
    freedoms and reduces fitting rounds rather than launching a second fit.
    """
    checkpoint()
    allocation = propose(original.field, coordinates)
    values = allocation.proposed if allocation is not None else coordinates
    if tightening is None:
        seed = Seed(0, values, 0.0, broad_chart.descriptor(case, original))
        path, metrics = box_fit.refine(case, seed, checkpoint, WARM)
    else:
        path, metrics = tighten(case, values, checkpoint, tightening=tightening)
    metrics["allocation"] = asdict(allocation) if allocation is not None else None
    return path, metrics
