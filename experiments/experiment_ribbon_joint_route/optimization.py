"""
Optimize first-pass material length with jointly adjustable bend orientations and placement.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from itertools import accumulate
from time import perf_counter
from typing import Any, Callable

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_fold_relaxation.flexible import FlexibleModel
from experiments.experiment_ribbon_fold_relaxation.flexible_steps import (
    StepLimits,
    retract,
    step_limit,
)
from experiments.experiment_ribbon_fold_relaxation.steps import advance, projected
from experiments.experiment_ribbon_fold_route.contact import ContactResult, inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_spline_guide.guide import Guide

ITERATIONS = 16
HALVINGS = 6
CONTACT_PROPOSALS = 12
CONTACT_PAIRS = 1024
ROUTING_STEPS = StepLimits(0.25, math.pi / 4)


@dataclass(frozen=True)
class GuideProgress:
    """
    Compare ordered travel to the pre-path without imposing interior point landmarks.
    """

    reference: tuple[tuple[Vector3, Vector3 | None], ...]
    chord_mm: float

    @classmethod
    def capture(cls, route: FoldRoute, guide: Guide) -> GuideProgress:
        """
        Freeze sixty-five positions and directed tangents for this fixed boundary pair.
        """
        samples = (guide.arc_sample(i / 64) for i in range(65))
        reference = tuple((p, unit(t) if magnitude(t) > 1e-12 else None) for p, t in samples)
        return cls(reference, magnitude(difference(route.targets.end, route.targets.start)))

    def cost(self, route: FoldRoute) -> float:
        """
        Minimize normalized position/direction mismatch with monotone guide correspondence.

        Thirty-three material stations match nondecreasing reference indices,
        fixing both endpoints. Prefix minima bound work by33*65pairs. This
        sampled preference is not a continuous proximity or feasibility proof.
        """
        previous = [math.inf] * len(self.reference)
        for i in range(33):
            point, velocity = route.lane(i / 32, 0)
            tangent = unit(velocity)
            costs = [
                self._pair_cost(point, tangent, target, direction)
                for target, direction in self.reference
            ]
            previous = (
                [value + best for value, best in zip(costs, accumulate(previous, min))]
                if i
                else [costs[0]] + [math.inf] * (len(costs) - 1)
            )
        return previous[-1] / 33

    def _pair_cost(
        self, point: Vector3, tangent: Vector3, target: Vector3, direction: Vector3 | None
    ) -> float:
        """
        Measure one dimensionless spatial and directed-tangent mismatch.
        """
        offset = difference(point, target)
        alignment = max(0.0, 1 - dot(tangent, direction)) if direction is not None else 0.0
        return dot(offset, offset) / self.chord_mm**2 + alignment


@dataclass(frozen=True)
class Optimized:
    """
    Retain the last accepted first-pass route and bounded optimization work separately.
    """

    route: FoldRoute
    reason: str
    iterations: int
    accepted: int
    contacts: int
    elapsed_seconds: float
    initial_guide_cost: float
    guide_cost: float

    def summary(self) -> dict[str, Any]:
        """
        Serialize counters without copying the complete material route.
        """
        return {
            "reason": self.reason,
            "iterations": self.iterations,
            "accepted": self.accepted,
            "contact_proposals": self.contacts,
            "seconds": self.elapsed_seconds,
            "initial_guide_cost": self.initial_guide_cost,
            "guide_cost": self.guide_cost,
            "length_mm": self.route.material_length_mm,
        }


def optimize(
    source: FoldRoute,
    guide: Guide,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    baseline_contact: ContactResult | None = None,
) -> Optimized:
    """
    Shorten the rough construction before first-pass output or optional aesthetic smoothing.

    Bend angles/signs, banks, radii and runway are jointly variable. Fixed ordered
    target poses, material identity and the declared physical radius floor remain
    authoritative. There is no aesthetic curvature objective or old-peak gate.
    Every accepted update strictly shortens material, preserves the initial guide
    preference, and passes complete caps, local metric and full-profile contact.

    A supplied coarse certificate exceeding the optimization subdivision budget
    retains the valid route without spending that budget repeatedly. This is a
    conservative work limit, not a physical infeasibility finding.
    Optimization contact checks use a smaller subdivision budget; unresolved
    candidates never pass. Exhaustion retains the preceding validated route.
    External checkpoint errors propagate. The original coarse construction and
    final validation keep their existing contact policies.
    """
    started = perf_counter()
    if cap_error(source) > 1e-7:
        raise ValueError("First-pass optimization requires closed ordered caps")
    if baseline_contact is not None and baseline_contact.status != "separated":
        raise ValueError("The supplied coarse contact certificate must pass")
    progress = GuideProgress.capture(source, guide)
    initial_guide = progress.cost(source)
    checkpoint()
    if baseline_contact is not None and baseline_contact.pairs_checked > CONTACT_PAIRS:
        return Optimized(
            source,
            "baseline_contact_budget",
            0,
            0,
            0,
            perf_counter() - started,
            initial_guide,
            initial_guide,
        )
    model = FlexibleModel(source)
    current = source
    values: tuple[float, ...] = model.initial
    accepted = contacts = iterations = 0
    reason = "iteration_budget"
    for iteration in range(ITERATIONS):
        checkpoint()
        if contacts >= CONTACT_PROPOSALS:
            reason = "contact_proposal_budget"
            break
        iterations = iteration + 1
        gradient = model.length_gradient(values)
        scale = max(abs(g) for g in gradient)
        delta = projected(
            model, values, model.jacobian(values), [0.0] * 6, [-g / scale for g in gradient]
        )
        if delta is None or math.fsum(g * d for g, d in zip(gradient, delta)) >= -1e-10:
            reason = "no_projected_length_descent"
            break
        step = step_limit(model, values, delta, limits=ROUTING_STEPS)
        if not math.isfinite(step) or step <= 1e-12:
            reason = "step_floor"
            break
        moved = False
        for halving in range(HALVINGS):
            checkpoint()
            corrected = retract(
                model,
                advance(model, values, delta, step),
                current.material_length_mm / model.scale,
                checkpoint,
            )
            candidate = model.route(corrected) if corrected is not None else None
            event: dict[str, Any] = {
                "stage": "first_pass_optimization",
                "iteration": iteration,
                "halving": halving,
                "status": "closure_unresolved",
            }
            if candidate is not None and corrected is not None:
                event["length_mm"] = candidate.material_length_mm
                if cap_error(candidate) > 1e-7:
                    event["status"] = "ordered_caps_rejected"
                elif (
                    candidate.material_length_mm
                    >= current.material_length_mm - 1e-8 * source.targets.diameter_mm
                ):
                    event["status"] = "no_length_gain"
                elif progress.cost(candidate) > initial_guide + 1e-10:
                    event["status"] = "guide_progress_rejected"
                elif contacts >= CONTACT_PROPOSALS:
                    event["status"] = "contact_proposal_budget"
                else:
                    record({**event, "status": "contact_started"})
                    contact = inspect_contact(
                        candidate, maximum_pairs=CONTACT_PAIRS, checkpoint=checkpoint
                    )
                    contacts += 1
                    event.update(status=contact.status, contact=asdict(contact))
                    if contact.status == "separated":
                        if material_error(candidate) > 1e-10:
                            raise ArithmeticError(
                                "First-pass contraction lost material compatibility"
                            )
                        current, values = candidate, corrected
                        accepted += 1
                        moved = True
                        event.update(status="accepted", route=snapshot(candidate))
            record(event)
            if moved:
                break
            step /= 2
        if not moved:
            reason = (
                "contact_proposal_budget" if contacts >= CONTACT_PROPOSALS else "proposal_budget"
            )
            break
    return Optimized(
        current,
        reason,
        iterations,
        accepted,
        contacts,
        perf_counter() - started,
        initial_guide,
        progress.cost(current),
    )
