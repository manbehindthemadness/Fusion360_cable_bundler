"""
Restore bounded return geometry without forcing all cap errors along one proportional ray.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from .active_projection import CoordinateBounds, UnfinishedProjection, active_step


@dataclass
class ProjectionEvidence:
    """
    Count exhausted algebra and bounded proposals separately from nonlinear updates or acceptance.
    """

    exhaustions: int = 0
    raw_gate_rejections: int = 0
    bounded_proposals: int = 0
    bound_clipped_proposals: int = 0
    halfspace_contracted_proposals: int = 0


@dataclass(frozen=True)
class _ResidualBounds:
    """
    Retain geometric bounds and add six normalized cap errors plus one physical-restoration fraction.
    """

    source: CoordinateBounds
    size: int
    scale: float

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Transform original geometry bounds exactly and retain normalized cap-error bounds.
        """
        if index < self.size:
            low, high = self.source.bounds(index)
            return self.scale * low, self.scale * high
        return (-1.0, 1.0) if index < self.size + 6 else (0.0, 1.0)


def redistributed_step(
    model: CoordinateBounds,
    values: tuple[float, ...],
    jacobian: list[list[float]],
    residual: tuple[float, ...],
    checkpoint: Callable[[], None],
    *,
    evidence: ProjectionEvidence | None = None,
) -> tuple[float, ...] | None:
    """
    Use the original projector once, allowing bounded redistribution of the six cap errors.

    Let M be the existing maximum cap/positive-inequality residual. Six numerical
    coordinates y in [-1,1] express J*d-M*y=-r for the cap equations. This permits
    cap-error components to change independently while bounding each by M.
    The original shared fraction still restores violated physical inequalities;
    already satisfied inequalities retain their strict linear gate. The same
    least-norm projector and sixteen working-set updates select one vector.
    Use z=M*d for geometry coordinates, so their quadratic regularization is
    M squared times the original motion cost. The motion penalty vanishes with
    the residual instead of overwhelming feasible weak-sensitivity corrections.
    Bounds and current values receive the same positive coordinate transform;
    rows are divided by M and returned geometric increments are divided by M.
    Numerical residual coordinates never become material geometry. Return only
    the original coordinates, requiring strict predicted maximum-merit descent;
    nonlinear descent and all final physical/cap certificates remain the caller's.
    Project each geometric vector onto the original coordinate box before step
    limiting: scaled dual feasibility tolerance must not permit outward geometry
    that freezes other useful coordinates. Interior increments remain unchanged.
    At working-set exhaustion or completed raw-inequality rejection, the already
    computed uncertified vector is eligible for this same operation. Report the
    two decline reasons independently. Offer it only through those same merit
    and physical-inequality gates: satisfied rows stay strict and existing
    violations cannot grow. No further projection, geometry evaluation or
    alternative vector is tried, and the unfinished linear system is not certified.
    If an initially satisfied physical row would cross its halfspace, intersect
    this same bounded correction ray with that row's original zero boundary.
    One scalar contraction preserves the convex coordinate box and every other
    satisfied row. Touching or already violated rows receive no new permission;
    all original raw physical and strict merit gates still run afterward. This
    uses only retained linear data, without another projection or nonlinear trial.
    """
    if (
        not 7 <= len(residual) <= 19
        or len(jacobian) != len(residual)
        or any(len(row) != len(values) for row in jacobian)
    ):
        raise ValueError("Use six caps and at most thirteen retained physical inequalities")
    before = max(abs(term) if i < 6 else max(0.0, term) for i, term in enumerate(residual))
    if before == 0.0:
        return None
    augmented = [
        [value / before for value in row]
        + [-before if index == cap else 0.0 for cap in range(6)]
        + [0.0 if index < 6 else -max(0.0, term)]
        for index, (row, term) in enumerate(zip(jacobian, residual))
    ]
    unfinished = UnfinishedProjection()
    solution = active_step(
        _ResidualBounds(model, len(values), before),
        tuple(value * before for value in values) + (0.0,) * 7,
        augmented,
        residual,
        checkpoint,
        unfinished=unfinished,
    )
    bounded_proposal = False
    if solution is None:
        if unfinished.step is None:
            return None
        if unfinished.stop_reason not in ("working_set_limit", "raw_inequality"):
            return None
        solution = unfinished.step
        bounded_proposal = True
        if evidence is not None:
            if unfinished.stop_reason == "working_set_limit":
                evidence.exhaustions += 1
            else:
                evidence.raw_gate_rejections += 1
    delta = tuple(value / before for value in solution[: len(values)])
    if not all(math.isfinite(value) for value in delta):
        return None
    bounded = []
    for index, (value, change) in enumerate(zip(values, delta)):
        low, high = model.bounds(index)
        target = value + change
        bounded.append(low - value if target < low else high - value if target > high else change)
    changed_bounds = tuple(bounded) != delta
    delta = tuple(bounded)
    predicted = tuple(
        term + math.fsum(a * b for a, b in zip(row, delta)) for row, term in zip(jacobian, residual)
    )
    fraction = 1.0
    for row, old, new in zip(jacobian[6:], residual[6:], predicted[6:]):
        if old < 0.0 and new > 1e-14:
            slope = math.fsum(a * b for a, b in zip(row, delta))
            fraction = min(fraction, math.nextafter(-old / slope, 0.0))
    if fraction < 1.0:
        delta = tuple(fraction * change for change in delta)
        predicted = tuple(
            term + math.fsum(a * b for a, b in zip(row, delta))
            for row, term in zip(jacobian, residual)
        )
    if any(new - max(0.0, old) > 1e-14 for old, new in zip(residual[6:], predicted[6:])):
        return None
    after = max(abs(term) if i < 6 else max(0.0, term) for i, term in enumerate(predicted))
    if not after < before:
        return None
    if bounded_proposal and evidence is not None:
        evidence.bounded_proposals += 1
    if changed_bounds and evidence is not None:
        evidence.bound_clipped_proposals += 1
    if fraction < 1.0 and evidence is not None:
        evidence.halfspace_contracted_proposals += 1
    return delta
