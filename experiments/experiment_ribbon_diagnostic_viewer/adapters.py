"""
Execute registered numerical procedures with their actual exposed settings.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from devtools.ribbon_analysis.contracts import RibbonPath
from experiments.experiment_ribbon_cap_transition import compatible_shooting, director_shooting
from experiments.experiment_ribbon_cap_transition.compatible_coordinates import seed_coordinates
from experiments.experiment_ribbon_cap_transition.compatible_strip import BendMapping
from experiments.experiment_ribbon_cap_transition.director_route_objective import ObjectiveScope
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery import (
    box_fit,
    broad_chart,
    broad_search,
    generalized,
    solver,
)
from experiments.experiment_ribbon_route_discovery.families import Seed, select


def execute(
    identifier: str, case: EndpointCase, settings: dict[str, Any], checkpoint: Callable[[], None]
) -> tuple[RibbonPath | None, dict[str, Any]]:
    """
    Dispatch explicit policies; return numerical outcomes without physical acceptance.

    All independent refinement comparisons start from the same generic endpoint
    seed. No interrupted probe is silently treated as a completed warm solution.
    """
    if identifier in ("generalized", "broad"):
        ledger = broad_search.SearchLedger()
        handoff = (
            generalized.solve(case, checkpoint, ledger) if identifier == "generalized" else None
        )
        if identifier == "broad":
            broad_search.solve(case, checkpoint, ledger)
        if handoff is not None:
            return handoff.path, handoff.metrics
        chosen = ledger.candidate
        if chosen is None and ledger.trials:
            chosen = min(ledger.trials, key=lambda trial: trial.rank)
        return (
            (chosen.path, chosen.metrics) if chosen is not None else (None, {"stage": ledger.stage})
        )
    if identifier == "compatible":
        path, metrics = compatible_shooting.solve(
            case,
            checkpoint,
            objective_scope=ObjectiveScope.ROUTING
            if settings["objective"] == "routing"
            else ObjectiveScope.LEGACY_SPHERE,
            bend_mapping=BendMapping.NEAR_LIMIT
            if settings["mapping"] == "near limit"
            else BendMapping.GLOBAL_SOFT,
        )
        metrics["trials"] = tuple(asdict(trial) for trial in metrics["trials"])
        return path, metrics
    if identifier == "director":
        policies = {
            name: getattr(director_shooting, name)
            for name in (
                "BASELINE",
                "ROTATION",
                "REGULAR",
                "CORKSCREW",
                "FREE",
                "BANK",
                "BANK_PERSISTENT",
                "BANK_WIDTH",
            )
        }
        return director_shooting.solve(case, checkpoint, policy=policies[settings["policy"]])
    if identifier == "discovery":
        bank, _, screening_seconds = solver.screen_seeds(case, checkpoint)
        seeds = select(bank, maximum=settings["families"])
        refiners = {
            "short": solver.refine,
            "full": solver.refine_full,
            "plane guided": solver.refine_guided,
            "distance guided": solver.refine_distance_guided,
        }
        results = [refiners[settings["variant"]](case, seed, checkpoint) for seed in seeds]
        if not results:
            return None, {"detail": "Seed screening returned no distinct family."}
        chosen = min(results, key=lambda result: result[1]["score"])
        metrics = dict(
            chosen[1],
            family_results=[result[1] for result in results],
            seed_screening_seconds=screening_seconds,
        )
        return chosen[0], metrics
    if identifier not in ("ordinary", "redistribution", "tightening", "combined"):
        raise ValueError("No registered adapter for this procedure.")
    return _refine(identifier, case, settings, checkpoint)


def _refine(
    identifier: str, case: EndpointCase, settings: dict[str, Any], checkpoint: Callable[[], None]
) -> tuple[RibbonPath, dict[str, Any]]:
    """
    Apply existing allocation/chart strategies inside the user-selected fit budget.
    """
    from experiments.experiment_ribbon_bend_redistribution.allocation import propose
    from experiments.experiment_ribbon_tangent_tightening.chart import TangentFitChart
    from experiments.experiment_ribbon_tangent_tightening.field import TangentTightening

    values = seed_coordinates(case, director_shooting.seed(case))
    original = broad_chart.integrate(case, values, 64, checkpoint)
    allocation = (
        propose(original.field, values) if identifier in ("redistribution", "combined") else None
    )
    if allocation is not None:
        values = allocation.proposed
    chart = None
    if identifier in ("tightening", "combined"):
        chart = TangentFitChart(
            TangentTightening(float(settings["start_window"]), float(settings["end_window"]))
        )
        values = chart.lift(values)
    work = box_fit.FitWork(settings["coarse"], settings["fine"], settings["transports"])
    path, metrics = box_fit.refine(case, Seed(0, values, 0.0, ()), checkpoint, work, chart=chart)
    metrics["initialization"] = "Generic endpoint-derived seed; no cached fitted coordinates."
    metrics["allocation"] = asdict(allocation) if allocation is not None else None
    metrics["work"] = asdict(work)
    return path, metrics
