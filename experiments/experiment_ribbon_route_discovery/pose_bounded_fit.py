"""
Test width-clearance continuation inside an explicit relative endpoint-pose corridor.
"""

from __future__ import annotations

import math
from time import perf_counter
from typing import Any, Callable

from cable_bundler.routing.geometry import difference, magnitude
from experiments.experiment_ribbon_cap_transition.compatible_coordinates import (
    probe_coordinates,
    trial_coordinates,
)
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.director_constrained_step import constrained_step
from experiments.experiment_ribbon_cap_transition.director_shooting import (
    BANK_WIDTH,
    damped_step,
    endpoint_metrics,
    maximum_length_ratio,
    residual,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from .active_clearance import sample
from .families import Seed
from .solver import errors_for, integrate


def pose_limits(case: EndpointCase) -> tuple[float, ...]:
    """
    Limit modeled endpoint drift to1%thickness using dimensionless search bounds.

    Position residuals use target chord;frame-vector bounds use physical halfwidth.
    These are continuation trust bounds,not relaxed final closure tolerances.
    """
    chord = magnitude(difference(case.end, case.start))
    half = case.lines * case.diameter_mm / 2 + 0.1 * case.diameter_mm
    if not all(math.isfinite(v) and v > 0 for v in (chord, half, case.diameter_mm)):
        raise ValueError("Pose continuation requires positive finite geometry scales.")
    return (0.01 * case.diameter_mm / chord,) * 3 + (0.01 * case.diameter_mm / half,) * 6


def refine_bounded(
    case: EndpointCase, selected: Seed, checkpoint: Callable[[], None]
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Spend at most194transports on12coarse width steps and4fine closure steps.

    Start from this cold family's closed endpoint solution. A small pose corridor
    around its initial coarse replay enters each QP and actual trial check. Record
    that reference separately:coarse integration bias is not a moved target.
    Fine endpoint polishing accepts only contact-free trials. Return unresolved
    geometry unchanged on exhaustion;never snap endpoints or claim exact closure
    merely from the corridor. QP statuses retain bounded/dependent-set outcomes.
    """
    started = perf_counter()
    values = selected.coordinates
    maximum = maximum_length_ratio(case, BANK_WIDTH)
    limits = pose_limits(case)
    evaluations = audits = 0
    clearance_seconds = 0.0
    stages: list[dict[str, Any]] = []
    qp_steps: list[dict[str, Any]] = []

    def transport(parameters: tuple[float, ...], grid: int) -> CompatiblePath:
        """
        Count every derivative/trial/final transport under the shared work ceiling.
        """
        nonlocal evaluations
        if evaluations >= 194:
            raise RuntimeError("Pose-bounded continuation work cap.")
        evaluations += 1
        return integrate(case, parameters, grid, checkpoint)

    for grid, rounds in ((64, 12), (512, 4)):
        path = transport(values, grid)
        reference = residual(case, path)
        current = sample(case, path, checkpoint)
        audits += 1
        clearance_seconds += current.contacts["total_seconds"]
        actual = errors_for(case, path) + (current.deficits if grid == 64 else ())
        score = sum(v * v for v in actual)
        damping = 1e-3 if grid == 64 else 1e-8
        trials: list[dict[str, Any]] = []
        for round_index in range(rounds):
            pose = residual(case, path)
            offset = tuple(a - b for a, b in zip(pose, reference))
            if grid == 64 and (
                max(current.deficits) < 1e-9
                or any(abs(v) > bound for v, bound in zip(offset, limits))
            ):
                break
            if grid == 512 and (
                current.contacts["contact_detected"] or max(abs(v) for v in actual) < 1e-12
            ):
                break
            model = errors_for(case, path) + (current.model(path) if grid == 64 else ())
            columns = []
            slack_columns = []
            for index in range(10):
                _, parameters = probe_coordinates(values, index, maximum)
                probe = transport(parameters, grid)
                step = parameters[index] - values[index]
                observed = errors_for(case, probe) + (current.model(probe) if grid == 64 else ())
                columns.append(tuple((a - b) / step for a, b in zip(observed, model)))
                derivative = tuple((a - b) / step for a, b in zip(residual(case, probe), pose))
                slack_columns.append(tuple(v for d in derivative for v in (-d, d)))
            if grid == 64:
                slacks = tuple(
                    v for e, bound in zip(offset, limits) for v in (bound - e, bound + e)
                )
                quadratic = constrained_step(
                    columns,
                    model,
                    damping,
                    slack_columns,
                    slacks,
                    values,
                    (-4 * math.pi,) * 5 + (-3.0,) * 4 + (1.0,),
                    (4 * math.pi,) * 5 + (3.0,) * 4 + (maximum,),
                )
                delta = list(quadratic.values)
                qp_steps.append(
                    dict(grid=grid, iterations=quadratic.iterations, status=quadratic.status)
                )
            else:
                delta = damped_step(columns, model, damping)
            accepted = False
            for fraction in (1.0, 0.5):
                _, proposed = trial_coordinates(values, delta, fraction, maximum)
                candidate = transport(proposed, grid)
                clearance = sample(case, candidate, checkpoint)
                audits += 1
                clearance_seconds += clearance.contacts["total_seconds"]
                observed = errors_for(case, candidate) + (clearance.deficits if grid == 64 else ())
                after = sum(v * v for v in observed)
                pose_error = residual(case, candidate)
                allowed = (
                    all(
                        abs(v - origin) <= bound
                        for v, origin, bound in zip(pose_error, reference, limits)
                    )
                    if grid == 64
                    else not clearance.contacts["contact_detected"]
                )
                take = allowed and after < score
                trials.append(
                    dict(
                        round_index=round_index,
                        fraction=fraction,
                        proposed=proposed,
                        before=score,
                        after=after,
                        pose_residual=pose_error,
                        contact_pairs=clearance.contacts["contact_pairs"],
                        accepted=take,
                    )
                )
                if take:
                    values, path, current, actual, score = (
                        proposed,
                        candidate,
                        clearance,
                        observed,
                        after,
                    )
                    accepted = True
                    break
            damping = max(1e-12, damping / 3) if accepted else damping * 10
        stages.append(dict(grid=grid, pose_reference=reference, trials=trials))
    metrics: dict[str, Any] = endpoint_metrics(case, path)
    metrics.update(
        strict_endpoint_gate=max(metrics.values()) <= 1e-8,
        coordinates=values,
        seed_index=selected.index,
        evaluations=evaluations,
        contact_audits=audits,
        clearance_seconds=clearance_seconds,
        stages=stages,
        pose_window=limits,
        qp_steps=qp_steps,
        score=score,
        seconds=perf_counter() - started,
        work_policy=dict(coarse_rounds=12, fine_rounds=4, maximum_evaluations=194),
    )
    return path, metrics
