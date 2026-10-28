"""
Test bounded local field adjustments on frozen closed but colliding routes.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.director_constrained_step import constrained_step
from experiments.experiment_ribbon_cap_transition.director_shooting import (
    endpoint_metrics,
    residual,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from . import active_clearance, local_chart
from .projected_clearance import distance_model


def refine(
    case: EndpointCase, base: tuple[float, ...], checkpoint: Callable[[], None]
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Try four projected local width steps then twelve fixed-target polish rounds.

    At most450transports,including all derivatives/rejected steps and final512
    replay. No persistent solver policy is changed. Independent analysis is required.
    """
    began = perf_counter()
    values = (0.0,) * 8 + (base[9],)
    lower, upper = local_chart.bounds(case)
    count = 0
    history: list[dict[str, Any]] = []

    def transport(coordinates: tuple[float, ...], grid: int) -> CompatiblePath:
        """
        Count every path evaluation and enforce the frozen inclusive budget.
        """
        nonlocal count
        checkpoint()
        if count >= 450:
            raise RuntimeError("Local field transport cap")
        count += 1
        return local_chart.integrate(case, base, coordinates, grid, checkpoint)

    def perturb(coordinates: tuple[float, ...], index: int) -> tuple[float, ...]:
        """
        Take an inward finite difference at a box boundary.
        """
        delta = 1e-5 if coordinates[index] + 1e-5 <= upper[index] else -1e-5
        return coordinates[:index] + (coordinates[index] + delta,) + coordinates[index + 1 :]

    def move(
        coordinates: tuple[float, ...], delta: tuple[float, ...], fraction: float
    ) -> tuple[float, ...]:
        """
        Keep roundoff inside the registered search box.
        """
        return tuple(
            max(lo, min(hi, x + fraction * d))
            for x, d, lo, hi in zip(coordinates, delta, lower, upper)
        )

    def project(
        coordinates: tuple[float, ...],
        path: CompatiblePath,
        reference: tuple[float, ...],
        grid: int,
        rounds: int,
    ) -> tuple[tuple[float, ...], CompatiblePath]:
        """
        Reduce nonlinear pose error with bounded Newton corrections.
        """
        for _ in range(rounds):
            errors = tuple(a - b for a, b in zip(residual(case, path), reference))
            if max(abs(v) for v in errors) <= (1e-7 if grid == 64 else 1e-13):
                break
            columns = []
            for index in range(9):
                probe_values = perturb(coordinates, index)
                probe = transport(probe_values, grid)
                step = probe_values[index] - coordinates[index]
                columns.append(
                    tuple(
                        (a - b - e) / step
                        for a, b, e in zip(residual(case, probe), reference, errors)
                    )
                )
            result = constrained_step(
                columns, errors, 1e-8, [()] * 9, (), coordinates, lower, upper
            )
            before = sum(v * v for v in errors)
            for fraction in (1.0, 0.5):
                proposed = move(coordinates, result.values, fraction)
                candidate = transport(proposed, grid)
                after = sum((a - b) ** 2 for a, b in zip(residual(case, candidate), reference))
                if after < before:
                    coordinates, path = proposed, candidate
                    break
        return coordinates, path

    path = transport(values, 64)
    reference = residual(case, path)
    snapshot = active_clearance.sample(case, path, checkpoint)
    score = sum(v * v for v in snapshot.deficits)
    for outer in range(4):
        if not snapshot.contacts["contact_detected"]:
            break
        model, pose = distance_model(snapshot, path), residual(case, path)
        columns, slacks = [], []
        for index in range(9):
            probe_values = perturb(values, index)
            probe = transport(probe_values, 64)
            step = probe_values[index] - values[index]
            columns.append(
                tuple((a - b) / step for a, b in zip(distance_model(snapshot, probe), model))
            )
            derivative = tuple((a - b) / step for a, b in zip(residual(case, probe), pose))
            slacks.append(tuple(v for d in derivative for v in (-d, d)))
        result = constrained_step(columns, model, 1e-3, slacks, (1e-7,) * 18, values, lower, upper)
        accepted = False
        for fraction in (1.0, 0.5):
            proposed = move(values, result.values, fraction)
            candidate = transport(proposed, 64)
            proposed, candidate = project(proposed, candidate, reference, 64, 3)
            error = max(abs(a - b) for a, b in zip(residual(case, candidate), reference))
            fresh = active_clearance.sample(case, candidate, checkpoint)
            after = sum(v * v for v in fresh.deficits)
            take = error <= 1e-7 and after < score
            history.append(
                dict(
                    outer=outer,
                    fraction=fraction,
                    before=score,
                    after=after,
                    pose_error=error,
                    accepted=take,
                    coordinates=proposed,
                    contacts=fresh.contacts["contact_pairs"],
                )
            )
            if take:
                values, path, snapshot, score = proposed, candidate, fresh, after
                accepted = True
                break
        if not accepted:
            break
    path = transport(values, 512)
    values, path = project(values, path, (0.0,) * 9, 512, 12)
    metrics: dict[str, Any] = endpoint_metrics(case, path)
    metrics.update(
        base=base,
        local_coordinates=values,
        evaluations=count,
        seconds=perf_counter() - began,
        trials=history,
    )
    return path, metrics
