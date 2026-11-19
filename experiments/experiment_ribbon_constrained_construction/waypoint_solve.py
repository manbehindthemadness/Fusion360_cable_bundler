"""
Test bounded waypoint-directed motion on an already complete material hinge chain.

This is a local mobility prototype, not an initial route or hinge-count planner.
Only closed, objective-improving and independently certified proposals advance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_relaxation.steps import advance, step_limit
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps

from .waypoint_motion import CapMotion, Motion
from .waypoints import Objective


@dataclass
class Work:
    """
    Debit one fixed four-action, twenty-four-correction, eight-proposal allowance.
    """

    actions: int = 0
    newton: int = 0
    proposals: int = 0
    accepted: int = 0
    values: tuple[float, ...] | None = None
    status: str = "unattempted"

    def correction(self) -> None:
        """
        Debit a correction before its numerical work; never renew the pool.
        """
        if self.newton >= 24:
            raise RuntimeError("Waypoint correction accounting exceeded its fixed pool")
        self.newton += 1


def run(
    objective: Objective,
    work: Work,
    certify: Callable[[FoldRoute], bool],
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    motion: Motion | None = None,
    trace: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    """
    Move existing hinges toward soft waypoint regions while retaining a complete route.

    The caller must establish the initial route's physical eligibility. Each
    accepted proposal requires a fresh caller certificate. A false or unresolved
    certificate cannot advance state. Source/resource/cancellation errors propagate;
    mutable work preserves the last accepted coordinates on an external stop.
    Exact cap restoration uses the existing tighter mating precondition needed
    by the contact audit, not a new physical dimensional acceptance tolerance.
    """
    if work.status != "unattempted":
        raise RuntimeError("Waypoint work cannot be replayed or renewed")
    model = objective.model
    values = model.initial
    initial = model.route(values)
    if initial is None or not ordered_mating_caps(initial.pieces, initial.targets):
        raise ValueError("Waypoint motion requires a complete ordered-cap baseline")
    work.values, work.status = values, "running"
    controller = CapMotion(objective) if motion is None else motion

    for action in range(4):
        checkpoint()
        work.actions += 1
        score = objective.score(values)
        delta = controller.direction(values, checkpoint)
        if delta is None:
            work.status = "no_projected_descent"
            return
        step = step_limit(model, values, delta, 1.0)
        progressed = False
        for halving in range(2):
            checkpoint()
            if work.newton >= 24:
                work.status = "newton_limit"
                return
            work.proposals += 1
            proposed = advance(model, values, delta, step * 0.5**halving)
            if trace is not None:
                proposed_route = model.route(proposed)
                trace(
                    {
                        "status": "raw_proposal",
                        "action": action,
                        "halving": halving,
                        "values": proposed,
                        "route": snapshot(proposed_route) if proposed_route else None,
                    }
                )
            closed = controller.restore(
                proposed,
                checkpoint,
                min(6, 24 - work.newton),
                work.correction,
            )
            event: dict[str, Any] = {"action": action, "halving": halving}
            if closed is None:
                event["status"] = "closure_failed"
                record(event)
                if trace is not None:
                    trace(event)
                continue
            route = model.route(closed)
            if route is None:
                raise ArithmeticError("Closed hinge chain lost all material")
            trial_score = objective.score(closed)
            event.update(
                score=trial_score, length_mm=route.material_length_mm, route=snapshot(route)
            )
            if trace is not None:
                trace({**event, "status": "restored_proposal"})
            if trial_score >= score:
                event["status"] = "no_objective_gain"
                record(event)
                continue
            record({**event, "status": "closed_before_certification"})
            if not certify(route):
                event["status"] = "clearance_rejected_or_unresolved"
                record(event)
                continue
            event["status"] = "accepted"
            record(event)
            values = closed
            work.values = closed
            work.accepted += 1
            progressed = True
            break
        if not progressed:
            work.status = "no_accepted_step"
            return
    work.status = "action_limit"
