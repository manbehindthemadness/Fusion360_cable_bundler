"""
Fit endpoints with refreshed width-aware models and actual-clearance trial scoring.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from experiments.experiment_ribbon_cap_transition.compatible_coordinates import (
    probe_coordinates,
    trial_coordinates,
)
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.director_shooting import (
    BANK_WIDTH,
    damped_step,
    endpoint_metrics,
    maximum_length_ratio,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from .active_clearance import sample
from .families import Seed
from .solver import errors_for, integrate


def refine_active(
    case: EndpointCase, selected: Seed, checkpoint: Callable[[], None]
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Use18coarse/3fine rounds and at most254transports for one cold route family.

    Probes use frozen current support directions;trials are scored using actual
    full-width distances,including newly appearing pairs. Accepted trials refresh
    the next local model. No plane is carried over solely because it once existed.
    Shared bounded proposal arithmetic matches the historical fits. This is a
    least-squares experiment inspired by SQP,not the papers'constrained QP solver,
    signed solid-penetration calculation or continuous collision-free line search.
    """
    started = perf_counter()
    maximum = maximum_length_ratio(case, BANK_WIDTH)
    values = selected.coordinates
    evaluations = contact_audits = 0
    clearance_seconds = 0.0
    stages: list[dict[str, Any]] = []

    def transport(parameters: tuple[float, ...], grid: int) -> CompatiblePath:
        """
        Count every fitting transport before evaluating it against the local model.
        """
        nonlocal evaluations
        if evaluations >= 254:
            raise RuntimeError("Active width fitting evaluation limit reached.")
        evaluations += 1
        return integrate(case, parameters, grid, checkpoint)

    for grid, rounds, tolerance in ((64, 18, 1e-6), (512, 3, 1e-12)):
        stage_started = perf_counter()
        path = transport(values, grid)
        current = sample(case, path, checkpoint)
        contact_audits += 1
        clearance_seconds += current.contacts["total_seconds"]
        actual = errors_for(case, path) + current.deficits
        score = sum(v * v for v in actual)
        history = [score]
        trials: list[dict[str, Any]] = []
        damping = 1e-3 if grid == 64 else 1e-8
        for round_index in range(rounds):
            if max(abs(v) for v in actual) < tolerance:
                break
            model = errors_for(case, path) + current.model(path)
            columns = []
            for index in range(10):
                _, parameters = probe_coordinates(values, index, maximum)
                probe = transport(parameters, grid)
                observed = errors_for(case, probe) + current.model(probe)
                step = parameters[index] - values[index]
                columns.append(tuple((a - b) / step for a, b in zip(observed, model)))
            delta = damped_step(columns, model, damping)
            accepted = False
            for fraction in (1.0, 0.5):
                requested, proposed = trial_coordinates(values, delta, fraction, maximum)
                candidate = transport(proposed, grid)
                observed_clearance = sample(case, candidate, checkpoint)
                contact_audits += 1
                clearance_seconds += observed_clearance.contacts["total_seconds"]
                observed = errors_for(case, candidate) + observed_clearance.deficits
                candidate_score = sum(v * v for v in observed)
                trials.append(
                    dict(
                        round_index=round_index,
                        fraction=fraction,
                        before=score,
                        after=candidate_score,
                        requested=requested,
                        proposed=proposed,
                        contact_pairs=observed_clearance.contacts["contact_pairs"],
                        ambiguous_pairs=observed_clearance.ambiguous_pairs,
                        accepted=candidate_score < score,
                    )
                )
                if candidate_score < score:
                    values, path, current, actual, score = (
                        proposed,
                        candidate,
                        observed_clearance,
                        observed,
                        candidate_score,
                    )
                    accepted = True
                    break
            history.append(score)
            damping = max(1e-12, damping / 3) if accepted else damping * 10
        stages.append(
            dict(grid=grid, history=history, trials=trials, seconds=perf_counter() - stage_started)
        )
    metrics: dict[str, Any] = endpoint_metrics(case, path)
    metrics.update(
        strict_endpoint_gate=max(metrics.values()) <= 1e-8,
        seed_index=selected.index,
        coordinates=values,
        evaluations=evaluations,
        contact_audits=contact_audits,
        clearance_seconds=clearance_seconds,
        stages=stages,
        score=score,
        seconds=perf_counter() - started,
        work_policy=dict(coarse_rounds=18, fine_rounds=3, maximum_evaluations=254),
    )
    return path, metrics
