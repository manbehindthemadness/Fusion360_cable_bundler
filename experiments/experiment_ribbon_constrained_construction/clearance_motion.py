"""
Keep current material-separation planes inside joint descent and nonlinear cap restoration.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_relaxation.steps import advance, step_limit
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps
from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import jacobian
from experiments.experiment_ribbon_terminal_hardware.model import Hardware

from .clearance_planes import Plane, select
from .waypoint_motion import constrained_reference, objective_system
from .waypoints import Objective


class ClearanceMotion:
    """
    Guide one local action with at most thirteen current full-material inequalities.

    Fixed axes preserve already-separated sides, not a global path topology.
    Unsupported and capacity-omitted relations remain independent audit duties.
    Nonsmooth projection extrema can invalidate a linear prediction; every
    restoration checks the actual bounds, and no physical certificate is implied.
    """

    def __init__(
        self,
        objective: Objective,
        hardware: Hardware,
        record: Callable[[dict[str, Any]], None],
        *,
        trace: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """
        Bind immutable hardware and record guidance selection without executing a route trial.
        """
        self.objective = objective
        self.hardware = hardware
        self.record = record
        self.planes: tuple[Plane, ...] = ()
        self.trace = trace

    def observe(
        self, status: str, values: tuple[float, ...], terms: tuple[float, ...], **details: Any
    ) -> None:
        """
        Publish optional already-evaluated equation evidence; never influence a joint decision.
        """
        if self.trace is None:
            return
        model = self.objective.model
        route = model.route(values)
        self.trace(
            {
                "status": status,
                "values": values,
                "route": snapshot(route) if route is not None else None,
                "cap_position_components_mm": [term * model.scale for term in terms[:3]],
                "cap_rotation_vector_radians": terms[3:6],
                "clearance_rows": [
                    {
                        "name": plane.name,
                        "minimum_mm": plane.minimum_mm,
                        "gap_mm": plane.minimum_mm - term * model.scale,
                        "violation_mm": max(0, term * model.scale),
                    }
                    for plane, term in zip(self.planes, terms[6:])
                ],
                **details,
            }
        )

    def constraints(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Keep the six ordered-frame equations before the current action's inequalities.
        """
        return self.objective.model.residual(values) + tuple(
            p.residual(values) for p in self.planes
        )

    def direction(
        self, values: tuple[float, ...], checkpoint: Callable[[], None]
    ) -> tuple[float, ...] | None:
        """
        Find a cap-compatible objective descent that also respects current separation planes.
        """
        selection = select(self.objective.model, self.hardware, values, checkpoint)
        self.planes = selection.planes
        self.record(
            {
                "status": "guidance_selected",
                "represented": selection.represented,
                "unsupported": selection.unsupported,
                "capacity_omitted": selection.capacity_omitted,
                "planes": [
                    {
                        "name": p.name,
                        "gap_mm": p.gap_mm(values),
                        "axis": [p.axis.x, p.axis.y, p.axis.z],
                    }
                    for p in self.planes
                ],
            }
        )
        if not self.planes:
            return None
        rows, terms, reference = objective_system(
            self.objective, values, self.constraints, checkpoint
        )
        delta = constrained_reference(self.objective, values, rows, terms, reference, checkpoint)
        if delta is None or math.fsum(a * b for a, b in zip(reference, delta)) <= 1e-14:
            self.record({"status": "joint_projection_declined"})
            return None
        return delta

    def restore(
        self,
        values: tuple[float, ...],
        checkpoint: Callable[[], None],
        maximum_steps: int,
        on_step: Callable[[], None],
    ) -> tuple[float, ...] | None:
        """
        Restore caps and the same planes with at most six corrections/four halvings each.

        The existing tighter ordered-cap precondition is required by downstream
        contact arithmetic. The1e-8mm bound-consistency guard only accommodates
        projection rounding; neither replaces the0.01mm physical policy.
        """
        if not self.planes or not 0 <= maximum_steps <= 6:
            raise ValueError("Use a selected action and its remaining bounded correction allowance")
        model = self.objective.model
        tolerance = 1e-8 / model.scale

        def merit(equations: tuple[float, ...]) -> float:
            """
            Measure equality error and positive inequality violation, never negative slack.
            """
            return max(*(abs(t) for t in equations[:6]), *(max(0.0, t) for t in equations[6:]))

        def eligible(coordinates: tuple[float, ...], equations: tuple[float, ...]) -> bool:
            """
            Require actual ordered caps and nonlinear support bounds before certification.
            """
            route = model.route(coordinates)
            return (
                route is not None
                and max(equations[6:]) <= tolerance
                and ordered_mating_caps(route.pieces, route.targets)
            )

        for correction in range(maximum_steps):
            checkpoint()
            terms = self.constraints(values)
            self.observe("correction_state", values, terms, correction=correction)
            if eligible(values, terms):
                return values
            on_step()
            rows = jacobian(model, values, self.constraints, len(terms), frozenset(), checkpoint)
            delta = constrained_reference(
                self.objective, values, rows, terms, [0.0] * len(values), checkpoint
            )
            if delta is None:
                self.observe("correction_projection_declined", values, terms, correction=correction)
                return None
            step = step_limit(model, values, delta, 1.0)
            for halving in range(4):
                checkpoint()
                trial = advance(model, values, delta, step)
                trial_terms = self.constraints(trial)
                self.observe(
                    "correction_trial",
                    trial,
                    trial_terms,
                    correction=correction,
                    halving=halving,
                    delta=delta,
                    step=step,
                )
                if eligible(trial, trial_terms) or merit(trial_terms) < merit(terms):
                    values = trial
                    break
                step /= 2
            else:
                self.observe("correction_no_descent", values, terms, correction=correction)
                return None
        final_terms = self.constraints(values)
        accepted = eligible(values, final_terms)
        self.observe(
            "restoration_completed" if accepted else "restoration_limit", values, final_terms
        )
        return values if accepted else None
