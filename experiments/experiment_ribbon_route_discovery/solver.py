"""
Screen the historical bank once and refine up to three spatially distinct starts.

This experiment retains the compatible chart, near-limit mapping and sphere-free
endpoint objective. Historical family refinement and new contact guidance have
separate entry points and recorded work policies.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Protocol

from cable_bundler.routing.geometry import difference
from experiments.experiment_ribbon_cap_transition.compatible_coordinates import (
    probe_coordinates,
    seed_coordinates,
    trial_coordinates,
)
from experiments.experiment_ribbon_cap_transition.compatible_shooting import field_for
from experiments.experiment_ribbon_cap_transition.compatible_strip import (
    BendMapping,
    CompatiblePath,
    integrate_compatible,
)
from experiments.experiment_ribbon_cap_transition.director_route_objective import routing_penalties
from experiments.experiment_ribbon_cap_transition.director_seed_bank import candidates
from experiments.experiment_ribbon_cap_transition.director_shooting import (
    BANK_WIDTH,
    SeedMethod,
    damped_step,
    endpoint_metrics,
    maximum_length_ratio,
    residual,
    seed,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase, controls

from .families import Seed, select
from .guidance import ContactGuide, distance_from_witness


class FitObjective(Protocol):
    """
    Keep witness discovery separate from fixed-scope finite-difference evaluation.
    """

    def prepare(self, path: CompatiblePath) -> None:
        """
        Update guidance only outside a finite-difference linearization.
        """
        ...

    def evaluate(self, path: CompatiblePath) -> tuple[float, ...]:
        """
        Score the current path against a stable residual scope.
        """
        ...


@dataclass(frozen=True)
class EndpointObjective:
    """
    Preserve the original discovery objective without contact-driven adjustments.
    """

    case: EndpointCase

    def prepare(self, path: CompatiblePath) -> None:
        """
        Keep the historical objective scope fixed.
        """

    def evaluate(self, path: CompatiblePath) -> tuple[float, ...]:
        """
        Evaluate the unchanged dimensionless endpoint and local-rule residuals.
        """
        return errors_for(self.case, path)


@dataclass(frozen=True)
class GuidedObjective:
    """
    Couple endpoint fitting to the retained full-width separation hypotheses.
    """

    case: EndpointCase
    guide: ContactGuide

    def prepare(self, path: CompatiblePath) -> None:
        """
        Observe one candidate before rescoring trial and current with the same planes.
        """
        self.guide.observe(path)

    def evaluate(self, path: CompatiblePath) -> tuple[float, ...]:
        """
        Append fixed contact slots without rediscovering witnesses during probes.
        """
        return errors_for(self.case, path) + self.guide.residuals(path)


def integrate(
    case: EndpointCase,
    coordinates: tuple[float, ...],
    steps: int,
    checkpoint: Callable[[], None],
) -> CompatiblePath:
    """
    Integrate the same near-limit compatible chart from the prescribed start pose.
    """
    checkpoint()
    initial = tuple(
        value
        for vector in (case.start, case.start_tangent, case.start_width)
        for value in (vector.x, vector.y, vector.z)
    )
    return integrate_compatible(
        field_for(case, coordinates, bend_mapping=BendMapping.NEAR_LIMIT),
        steps,
        checkpoint,
        initial=initial,
    )


def errors_for(case: EndpointCase, path: CompatiblePath) -> tuple[float, ...]:
    """
    Preserve the sphere-independent endpoint and local material/bend objective.
    """
    return residual(case, path) + routing_penalties(case, path)


def screen_seeds(
    case: EndpointCase, checkpoint: Callable[[], None]
) -> tuple[tuple[Seed, ...], tuple[Seed, ...], float]:
    """
    Score all46 unchanged starts once, retaining17 full-width geometric samples.

    Return the complete bank, selected starts and screening seconds. No cached
    fitted solution or case identifier influences initialization or selection.
    """
    controls(case)
    started = perf_counter()
    half = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    seeds: list[Seed] = []
    for index, raw in enumerate(candidates() + (seed(case), seed(case, SeedMethod.CORKSCREW))):
        coordinates = seed_coordinates(case, raw)
        path = integrate(case, coordinates, 64, checkpoint)
        score = sum(v * v for v in errors_for(case, path))
        descriptor = tuple(
            value / (2 * half)
            for i in range(17)
            for offset in (-half, 0.0, half)
            for point in (difference(path.lane(i / 16, offset)[0], case.start),)
            for value in (point.x, point.y, point.z)
        )
        seeds.append(Seed(index, coordinates, score, descriptor))
    return tuple(seeds), select(tuple(seeds)), perf_counter() - started


def refine(
    case: EndpointCase, selected: Seed, checkpoint: Callable[[], None]
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Refine one retained family for five coarse and one fine round,at most74evaluations.

    Three families therefore cost at most222 fitting evaluations,below the254
    shared ceiling. Final512-grid evaluation is mandatory even if coarse closure
    looks sufficient. Full/half steps and raw bounds match the historical solver.
    Return failed fits unchanged; there is no restart, snapping or contact repair.
    """
    return _refine(case, selected, checkpoint, EndpointObjective(case), (5, 1, 74))


def refine_guided(
    case: EndpointCase, selected: Seed, checkpoint: Callable[[], None]
) -> tuple[CompatiblePath, dict[str, Any], ContactGuide]:
    """
    Test one contact-guided start with18coarse/3fine rounds and254integrations.

    Retain all separation hypotheses and observe each trial before deciding its
    acceptance. This is a sampled sequential guidance experiment,not IPC,an elastic
    equilibrium solve or a continuous collision-free-update guarantee.
    """
    guide = ContactGuide(case, checkpoint)
    path, metrics = _refine(case, selected, checkpoint, GuidedObjective(case, guide), (18, 3, 254))
    metrics.update(contact_observations=guide.observations, contact_planes=len(guide.constraints))
    return path, metrics, guide


def refine_full(
    case: EndpointCase, selected: Seed, checkpoint: Callable[[], None]
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Give one cold family the historical18coarse/3fine rounds,at most254evaluations.

    This changes allocation from the short discovery fit,not its objective or
    physical chart. A caller comparing families must budget their aggregate work
    and independently reject contact or other findings before choosing a route.
    """
    return _refine(case, selected, checkpoint, EndpointObjective(case), (18, 3, 254))


def refine_distance_guided(
    case: EndpointCase, selected: Seed, checkpoint: Callable[[], None]
) -> tuple[CompatiblePath, dict[str, Any], ContactGuide]:
    """
    Recompute pairwise clearance as rulings rotate,instead of retaining a plane side.

    Use the same18coarse/3fine rounds and254integration ceiling as plane guidance.
    """
    guide = ContactGuide(case, checkpoint, factory=distance_from_witness)
    path, metrics = _refine(case, selected, checkpoint, GuidedObjective(case, guide), (18, 3, 254))
    metrics.update(contact_observations=guide.observations, contact_pairs=len(guide.constraints))
    return path, metrics, guide


def _refine(
    case: EndpointCase,
    selected: Seed,
    checkpoint: Callable[[], None],
    objective: FitObjective,
    work: tuple[int, int, int],
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Share bounded least-squares steps while keeping witness scope consistent.

    A newly observed plane changes the objective scope. Rescore both current and
    proposed paths before comparing them;history values across scope changes are
    not a claim of monotone progress against one fixed objective.
    """
    coarse_rounds, fine_rounds, maximum_evaluations = work
    started = perf_counter()
    maximum = maximum_length_ratio(case, BANK_WIDTH)
    values = selected.coordinates
    evaluations = 0
    stages: list[dict[str, Any]] = []

    def observe(
        trial_values: tuple[float, ...], integration_grid: int
    ) -> tuple[CompatiblePath, tuple[float, ...]]:
        """
        Count each integration used for fitting before evaluating the fixed objective.
        """
        nonlocal evaluations
        if evaluations >= maximum_evaluations:
            raise RuntimeError("Route-family fitting evaluation limit reached.")
        evaluations += 1
        evaluated = integrate(case, trial_values, integration_grid, checkpoint)
        return evaluated, objective.evaluate(evaluated)

    for grid, rounds, tolerance in ((64, coarse_rounds, 1e-6), (512, fine_rounds, 1e-12)):
        began = perf_counter()
        path, errors = observe(values, grid)
        objective.prepare(path)
        errors = objective.evaluate(path)
        score = sum(v * v for v in errors)
        history = [score]
        trials: list[dict[str, Any]] = []
        damping = 1e-3 if grid == 64 else 1e-8
        for round_index in range(rounds):
            objective.prepare(path)
            errors = objective.evaluate(path)
            score = sum(v * v for v in errors)
            if max(abs(v) for v in errors) < tolerance:
                break
            columns = []
            for i in range(10):
                _, parameters = probe_coordinates(values, i, maximum)
                _, observed = observe(parameters, grid)
                step = parameters[i] - values[i]
                columns.append(tuple((a - b) / step for a, b in zip(observed, errors)))
            delta = damped_step(columns, errors, damping)
            accepted = False
            for fraction in (1.0, 0.5):
                requested, proposed = trial_coordinates(values, delta, fraction, maximum)
                candidate, observed = observe(proposed, grid)
                objective.prepare(candidate)
                errors = objective.evaluate(path)
                score = sum(v * v for v in errors)
                observed = objective.evaluate(candidate)
                candidate_score = sum(v * v for v in observed)
                trials.append(
                    dict(
                        round_index=round_index,
                        fraction=fraction,
                        before=score,
                        after=candidate_score,
                        requested=requested,
                        proposed=proposed,
                        accepted=candidate_score < score,
                    )
                )
                if candidate_score < score:
                    values, path, errors, score = proposed, candidate, observed, candidate_score
                    accepted = True
                    break
            history.append(score)
            damping = max(1e-12, damping / 3) if accepted else damping * 10
        stages.append(
            dict(grid=grid, history=history, trials=trials, seconds=perf_counter() - began)
        )
    metrics: dict[str, Any] = endpoint_metrics(case, path)
    metrics.update(
        strict_endpoint_gate=max(metrics.values()) <= 1e-8,
        seed_index=selected.index,
        coordinates=values,
        evaluations=evaluations,
        stages=stages,
        score=score,
        seconds=perf_counter() - started,
        work_policy=dict(
            coarse_rounds=coarse_rounds,
            fine_rounds=fine_rounds,
            maximum_evaluations=maximum_evaluations,
        ),
    )
    return path, metrics
