"""
Select optional local terminal bends within a fixed warm-fit transport budget.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery import box_fit
from experiments.experiment_ribbon_route_discovery.families import Seed

from .chart import TangentFitChart
from .field import TangentTightening


def tighten(
    case: EndpointCase,
    coordinates: tuple[float, ...],
    checkpoint: Callable[[], None],
    *,
    tightening: TangentTightening | None = None,
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Fit fixed poses with local end controls only when explicitly selected.

    None retains ordinary 10-coarse/3-fine warm continuation. Enabled ends add
    derivative probes, so reduce coarse rounds to fit the same inclusive 158
    transport cap, reserving three fine rounds and both grid evaluations.
    No contact/cubic/native acceptance is inferred; callers audit independently.
    """
    checkpoint()
    chart = TangentFitChart(tightening) if tightening is not None else None
    values = chart.lift(coordinates) if chart is not None else coordinates
    dimensions = len(values)
    coarse = (158 - 2) // (dimensions + 2) - 3
    work = box_fit.FitWork(coarse, 3, 158)
    seed = Seed(0, values, 0.0, ())
    path, metrics = box_fit.refine(case, seed, checkpoint, work, chart=chart)
    start, end = chart.amplitudes(metrics["coordinates"]) if chart is not None else (0.0, 0.0)
    metrics["tangent_tightening"] = {
        "policy": asdict(tightening) if tightening is not None else None,
        "start_turn": start,
        "end_turn": end,
        "dimensions": dimensions,
        "work": asdict(work),
    }
    return path, metrics
