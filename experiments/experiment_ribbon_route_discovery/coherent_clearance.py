"""
Test both crossing-region escape signs with the unchanged compatible ribbon chart.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from time import perf_counter
from typing import Any, Callable, Iterator

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.compatible_coordinates import (
    probe_coordinates,
    trial_coordinates,
)
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.director_constrained_step import constrained_step
from experiments.experiment_ribbon_cap_transition.director_shooting import residual
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from . import box_fit, broad_chart, coherent_contacts, contact
from .families import Seed

# noinspection PyProtectedMember
from .projected_clearance import _project


def candidates(
    case: EndpointCase, seed: Seed, checkpoint: Callable[[], None]
) -> Iterator[tuple[CompatiblePath, dict[str, Any]]]:
    """
    Spend at most607 transports on two three-step hypotheses and original-target polish.

    One shared64-grid replay plus two(253coarse+50fine) limits. Signed support
    decrease is not physical acceptance: the caller must audit every output for
    original endpoint closure, full-width contact, intrinsic rules and cubics.
    No persistent default solver behavior or contact acceptance is changed.
    """
    initial = broad_chart.integrate(case, seed.coordinates, 64, checkpoint)
    pairs = []
    contact.audit(case, initial, checkpoint, pair_observer=pairs.append)
    model = coherent_contacts.build(tuple(pairs), case.diameter_mm)
    for sign in (1, -1):
        yield _attempt(case, seed, model, sign, checkpoint)


def _attempt(
    case: EndpointCase,
    seed: Seed,
    model: coherent_contacts.CrossingModel,
    sign: int,
    checkpoint: Callable[[], None],
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Reduce one frozen crossing support objective while projecting back to its pose.
    """
    began = perf_counter()
    count = 0
    maximum = broad_chart.carrier_maximum(case)
    lower, upper = broad_chart.bounds(case)
    planes = tuple(
        replace(p, normal=Vector3(0, 0, 0).translated(p.normal, sign)) for p in model.planes
    )

    def transport(values: tuple[float, ...]) -> CompatiblePath:
        """
        Count every coarse derivative, trial and projection transport.
        """
        nonlocal count
        count += 1
        if count > 253:
            raise RuntimeError("Coherent patch transport cap")
        return broad_chart.integrate(case, values, 64, checkpoint)

    def objective(path: CompatiblePath) -> tuple[float, ...]:
        """
        Retain witness identities and oriented support directions throughout a fit.
        """
        return tuple(plane.violation(path) for plane in planes)

    values = seed.coordinates
    path = transport(values)
    reference = residual(case, path)
    history: list[dict[str, Any]] = []
    for outer in range(3):
        errors = objective(path)
        if not errors or max(errors) < 1e-9:
            break
        score = sum(value * value for value in errors)
        pose = residual(case, path)
        columns, slack = [], []
        for index in range(10):
            _, parameters = probe_coordinates(values, index, maximum)
            probe = transport(parameters)
            step = parameters[index] - values[index]
            columns.append(tuple((a - b) / step for a, b in zip(objective(probe), errors)))
            derivative = tuple((a - b) / step for a, b in zip(residual(case, probe), pose))
            slack.append(tuple(value for d in derivative for value in (-d, d)))
        delta = constrained_step(columns, errors, 1e-3, slack, (1e-7,) * 18, values, lower, upper)
        accepted = False
        for fraction in (1.0, 0.5):
            _, proposed = trial_coordinates(values, delta.values, fraction, maximum)
            candidate = transport(proposed)
            proposed, candidate = _project(case, proposed, candidate, reference, transport)
            pose_error = max(abs(a - b) for a, b in zip(residual(case, candidate), reference))
            after = sum(value * value for value in objective(candidate))
            take = pose_error <= 1e-7 and after < score
            history.append(
                dict(
                    outer=outer,
                    fraction=fraction,
                    before=score,
                    after=after,
                    pose_error=pose_error,
                    accepted=take,
                    coordinates=proposed,
                )
            )
            if take:
                values, path = proposed, candidate
                accepted = True
                break
        if not accepted:
            break
    path, metrics = box_fit.refine(
        case, Seed(seed.index, values, 0, ()), checkpoint, box_fit.POLISH
    )
    metrics.update(
        coherent_model=asdict(model),
        escape_sign=sign,
        projection_trials=history,
        projection_transports=count,
        evaluations=count + metrics["evaluations"],
        seconds=perf_counter() - began,
    )
    return path, metrics
