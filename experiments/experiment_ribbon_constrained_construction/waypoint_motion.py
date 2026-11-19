"""
Share waypoint joint sensitivities and explicit cap-only or constrained motion strategies.
"""

from __future__ import annotations

import math
from typing import Callable, Protocol

from experiments.experiment_ribbon_bend_relocation.model import retract_active
from experiments.experiment_ribbon_fold_relaxation.closure_policy import ClosurePolicy
from experiments.experiment_ribbon_fold_relaxation.steps import projected
from experiments.experiment_ribbon_terminal_hardware.active_projection import active_step
from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import jacobian

from .waypoints import Objective


class Motion(Protocol):
    """
    Prepare one joint direction and retain its constraints during nonlinear closure.
    """

    def direction(
        self, values: tuple[float, ...], checkpoint: Callable[[], None]
    ) -> tuple[float, ...] | None:
        """
        Return one bounded-action direction or decline without another route trial.
        """
        ...

    def restore(
        self,
        values: tuple[float, ...],
        checkpoint: Callable[[], None],
        maximum_steps: int,
        on_step: Callable[[], None],
    ) -> tuple[float, ...] | None:
        """
        Restore the same action's hard equations within genuinely remaining work.
        """
        ...


def objective_system(
    objective: Objective,
    values: tuple[float, ...],
    constraints: Callable[[tuple[float, ...]], tuple[float, ...]],
    checkpoint: Callable[[], None],
) -> tuple[list[list[float]], tuple[float, ...], list[float]]:
    """
    Share cap, inequality and waypoint placements in one finite-difference system.
    """
    terms = constraints(values)

    def equations(coordinates: tuple[float, ...]) -> tuple[float, ...]:
        """
        Keep hard constraints before soft landmark and total-length observations.
        """
        return constraints(coordinates) + objective.observations(coordinates)

    rows = jacobian(
        objective.model, values, equations, len(equations(values)), frozenset(), checkpoint
    )
    errors = objective.errors(values)
    gradient = [
        math.fsum(row[i] * error for row, error in zip(rows[len(terms) :], errors))
        for i in range(len(values))
    ]
    return rows[: len(terms)], terms, [-g for g in gradient]


def constrained_reference(
    objective: Objective,
    values: tuple[float, ...],
    rows: list[list[float]],
    terms: tuple[float, ...],
    reference: list[float],
    checkpoint: Callable[[], None],
) -> tuple[float, ...] | None:
    """
    Translate the existing least-norm inequality kernel to a desired joint motion.

    For delta=reference+u, shifted residuals and coordinate origins describe
    exactly the original cap, clearance and coordinate constraints. No physical
    placement is evaluated at the possibly out-of-domain shifted origin.
    The existing sixteen-update projection and thirteen-inequality limits hold.
    """
    shifted = tuple(a + b for a, b in zip(values, reference))
    residual = tuple(
        term + math.fsum(a * b for a, b in zip(row, reference)) for term, row in zip(terms, rows)
    )
    motion = active_step(objective.model, shifted, rows, residual, checkpoint)
    return None if motion is None else tuple(a + b for a, b in zip(reference, motion))


class CapMotion:
    """
    Preserve the original cap-only waypoint experiment as an explicit strategy.
    """

    def __init__(self, objective: Objective) -> None:
        """
        Bind one unchanged objective without running geometry or allocating work.
        """
        self.objective = objective

    def direction(
        self, values: tuple[float, ...], checkpoint: Callable[[], None]
    ) -> tuple[float, ...] | None:
        """
        Project the original negative objective gradient onto cap and coordinate constraints.
        """
        rows, terms, reference = objective_system(
            self.objective, values, self.objective.model.residual, checkpoint
        )
        delta = projected(self.objective.model, values, rows, [-v for v in terms], reference)
        if delta is None or math.fsum(a * b for a, b in zip(reference, delta)) <= 1e-14:
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
        Retain the original bounded ordered-cap retraction and correction accounting.
        """
        return retract_active(
            self.objective.model,
            values,
            checkpoint,
            closure_policy=ClosurePolicy.ORDERED_CAPS,
            maximum_steps=maximum_steps,
            on_step=on_step,
        )
