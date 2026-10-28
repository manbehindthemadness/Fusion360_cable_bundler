"""
Explore clear cold routes before endpoint closure, with bounded sampled step checks.

This is not continuous collision detection or a homotopy certificate. It remains
an isolated experiment and does not change the retained broad solver.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Iterator

from cable_bundler.routing.geometry import cross, difference, dot
from experiments.experiment_ribbon_cap_transition.compatible_coordinates import (
    probe_coordinates,
    trial_coordinates,
)
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.director_constrained_step import constrained_step
from experiments.experiment_ribbon_cap_transition.director_shooting import endpoint_metrics
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from . import broad_chart, contact
from .families import Seed, separation
from .solver import errors_for


@dataclass(frozen=True)
class ClearSeed:
    """
    Retain an initially clear route and a start-frame side label, not a topology proof.
    """

    seed: Seed
    side: float


def choose(rows: tuple[ClearSeed, ...]) -> tuple[ClearSeed, ...]:
    """
    Prefer two distinct clear routes on opposite start-normal sides, if available.

    Sign measures relative quarter/three-quarter center separation. It is used
    only at initialization; no persistent separating-plane restriction is added.
    """
    if not rows:
        return ()
    ordered = sorted(rows, key=lambda row: (row.seed.score, row.seed.index))
    first = ordered[0]
    distinct = [row for row in ordered[1:] if separation(first.seed, row.seed) >= 0.5]
    opposite = [row for row in distinct if row.side * first.side < 0]
    remaining = opposite or distinct
    return (first, remaining[0]) if remaining else (first,)


def screen(
    case: EndpointCase, checkpoint: Callable[[], None]
) -> tuple[tuple[ClearSeed, ...], dict[str, Any]]:
    """
    Screen the fixed110 cold seeds and audit each once at the same64 transport grid.
    """
    began = perf_counter()
    bank = broad_chart.screen(case, checkpoint)
    clear = []
    records = []
    normal = cross(case.start_tangent, case.start_width)
    for seed in bank:
        path = broad_chart.integrate(case, seed.coordinates, 64, checkpoint)
        measured, _ = contact.audit(case, path, checkpoint)
        side = dot(normal, difference(path.lane(0.25, 0)[0], path.lane(0.75, 0)[0])) / (
            2 * path.field.half_width_mm
        )
        records.append(
            dict(seed=seed.index, score=seed.score, side=side, contacts=measured["contact_pairs"])
        )
        if not measured["contact_detected"]:
            clear.append(ClearSeed(seed, side))
    selected = choose(tuple(clear))
    return selected, dict(
        seconds=perf_counter() - began,
        evaluations=220,
        clear=len(clear),
        selected=[row.seed.index for row in selected],
        records=records,
    )


def transition_parameters(
    before: tuple[float, ...], after: tuple[float, ...]
) -> tuple[tuple[float, ...], ...]:
    """
    Sample three interior coordinate interpolants without claiming continuous clearance.
    """
    if len(before) != 10 or len(after) != 10:
        raise ValueError("Transitions require ten original chart coordinates.")
    return tuple(
        tuple((1 - t) * a + t * b for a, b in zip(before, after)) for t in (0.25, 0.5, 0.75)
    )


def refine(
    case: EndpointCase, selected: ClearSeed, checkpoint: Callable[[], None]
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Fit endpoints for20coarse/8fine rounds, rejecting sampled colliding route updates.

    Every candidate and three interior coordinate interpolants must be clear.
    Finite-difference probes need not be clear; they are not accepted iterates.
    At most506 transports are needed;the inclusive hard cap is520. Three stalled
    rounds end each grid early. Original physical checks remain independently required.
    """
    began = perf_counter()
    values = selected.seed.coordinates
    lower, upper = broad_chart.bounds(case)
    maximum = broad_chart.carrier_maximum(case)
    evaluations = audits = 0
    trials: list[dict[str, Any]] = []

    def transport(parameters: tuple[float, ...], grid: int) -> CompatiblePath:
        """
        Charge every derivative and transition sample to the same transport budget.
        """
        nonlocal evaluations
        if evaluations >= 520:
            raise RuntimeError("Clear-initialization transport cap")
        evaluations += 1
        return broad_chart.integrate(case, parameters, grid, checkpoint)

    def clear(path: CompatiblePath) -> bool:
        """
        Use full-width sampled contact, with the unchanged thickness and exclusions.
        """
        nonlocal audits
        audits += 1
        measured, _ = contact.audit(case, path, checkpoint)
        return not measured["contact_detected"]

    for grid, rounds in ((64, 20), (512, 8)):
        path = transport(values, grid)
        if not clear(path):
            trials.append(dict(grid=grid, initial_replay_collision=True))
            if grid == 64:
                path = transport(values, 512)
            break
        errors = errors_for(case, path)
        score = sum(v * v for v in errors)
        damping, stalled = 1e-3 if grid == 64 else 1e-8, 0
        for outer in range(rounds):
            if (grid == 64 and max(abs(v) for v in errors) < 1e-6) or (
                grid == 512 and max(endpoint_metrics(case, path).values()) <= 1e-8
            ):
                break
            columns = []
            for index in range(10):
                _, parameters = probe_coordinates(values, index, maximum)
                observed = errors_for(case, transport(parameters, grid))
                step = parameters[index] - values[index]
                columns.append(tuple((a - b) / step for a, b in zip(observed, errors)))
            result = constrained_step(columns, errors, damping, [()] * 10, (), values, lower, upper)
            accepted = False
            for fraction in (1.0, 0.5):
                _, proposed = trial_coordinates(values, result.values, fraction, maximum)
                candidate = transport(proposed, grid)
                observed = errors_for(case, candidate)
                after = sum(v * v for v in observed)
                clear_step: bool | None = None
                if after < score:
                    clear_step = clear(candidate)
                    if clear_step:
                        for intermediate in transition_parameters(values, proposed):
                            if not clear(transport(intermediate, grid)):
                                clear_step = False
                                break
                take = after < score and clear_step is True
                trials.append(
                    dict(
                        grid=grid,
                        outer=outer,
                        fraction=fraction,
                        before=score,
                        after=after,
                        clear_step=clear_step,
                        accepted=take,
                        coordinates=proposed,
                    )
                )
                if take:
                    values, path, errors, score = proposed, candidate, observed, after
                    accepted = True
                    break
            damping = max(1e-12, damping / 3) if accepted else damping * 10
            stalled = 0 if accepted else stalled + 1
            if stalled >= 3:
                break
    metrics: dict[str, Any] = endpoint_metrics(case, path)
    metrics.update(
        coordinates=values,
        seed=selected.seed.index,
        side=selected.side,
        evaluations=evaluations,
        audits=audits,
        seconds=perf_counter() - began,
        score=sum(v * v for v in errors_for(case, path)),
        trials=trials,
    )
    return path, metrics


def candidates(
    case: EndpointCase, checkpoint: Callable[[], None]
) -> Iterator[tuple[CompatiblePath, dict[str, Any]]]:
    """
    Generate up to two cold candidates,retaining the full shared screening cost.
    """
    selected, screening = screen(case, checkpoint)
    for row in selected:
        path, metrics = refine(case, row, checkpoint)
        metrics["screening"] = screening
        yield path, metrics
