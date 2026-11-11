"""
Restore bounded return geometry without forcing all cap errors along one proportional ray.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from experiments.experiment_ribbon_bend_reduction.closure import affine_projection

from .active_projection import ActiveFaces, CoordinateBounds, UnfinishedProjection, active_step
from .projection_initialization import Initialization, InitializationEvidence


class GuidancePolicy(Enum):
    """
    Distinguish per-row improvement from maximum-merit restoration of already-invalid guidance.
    """

    NONWORSENING = "nonworsening"
    RESTORATION_MERIT = "restoration_merit"


def strict_descent(
    residual: tuple[float, ...],
    predicted: tuple[float, ...],
    guidance_policy: GuidancePolicy,
) -> bool:
    """
    Check the original predicted inequality limits and strict maximum-merit descent.

    Already satisfied or touching rows retain their original1e-14gate. Only
    explicit restoration permits positive guidance to trade below the original
    maximum merit; default nonworsening remains unchanged. Incomplete/nonfinite
    equations decline. This is a linear proposal gate, not physical acceptance.
    """
    if len(residual) < 6 or len(predicted) != len(residual):
        return False
    if any(not math.isfinite(term) for term in residual + predicted):
        return False
    before = max(abs(term) if i < 6 else max(0.0, term) for i, term in enumerate(residual))
    limits = tuple(
        before if guidance_policy is GuidancePolicy.RESTORATION_MERIT and old > 0 else max(0.0, old)
        for old in residual[6:]
    )
    if any(new - limit > 1e-14 for limit, new in zip(limits, predicted[6:])):
        return False
    after = max(abs(term) if i < 6 else max(0.0, term) for i, term in enumerate(predicted))
    return after < before


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
    cap_metric_calibrations: int = 0
    active_face_restorations: int = 0
    guidance_tradeoff_proposals: int = 0
    coordinate_seed_attempts: int = 0
    coordinate_seed_faces: int = 0


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


def _motion_scale(jacobian: list[list[float]], residual: tuple[float, ...], merit: float) -> float:
    """
    Calibrate regularization against one nominal cap correction without proposing geometry.

    Unit-scale or smaller corrections retain the original metric exactly.
    A larger unconstrained cap correction normalizes its motion cost, preventing
    weak endpoint sensitivity from making persistent cap error artificially cheap.
    The six-row estimate has no physical/bound feasibility authority. Inconsistent
    or unrepresentable scaling retains the original metric before the single
    constrained working-set solve; no alternate proposal is evaluated.
    """
    estimate = affine_projection(
        jacobian[:6], [-term for term in residual[:6]], [0.0] * len(jacobian[0])
    )
    if estimate is None:
        return merit
    norm = math.hypot(*estimate)
    if not math.isfinite(norm) or norm <= 1.0:
        return merit
    scale = merit / norm
    if scale == 0.0 or any(not math.isfinite(value / scale) for row in jacobian for value in row):
        return merit
    return scale


def redistributed_step(
    model: CoordinateBounds,
    values: tuple[float, ...],
    jacobian: list[list[float]],
    residual: tuple[float, ...],
    checkpoint: Callable[[], None],
    *,
    evidence: ProjectionEvidence | None = None,
    guidance_policy: GuidancePolicy = GuidancePolicy.NONWORSENING,
) -> tuple[float, ...] | None:
    """
    Use the original projector once, allowing bounded redistribution of the six cap errors.

    Let M be the existing maximum cap/positive-inequality residual. Six numerical
    coordinates y in [-1,1] express J*d-M*y=-r for the cap equations. This permits
    cap-error components to change independently while bounding each by M.
    By default the original shared fraction restores violated physical inequalities;
    already satisfied inequalities retain their strict linear gate. The same
    least-norm projector and sixteen working-set updates select one vector.
    Use z=S*d for geometry coordinates, with S=M/max(1,N) where N is the norm
    of one nominal unconstrained six-cap correction. This metric estimate adds
    no feasible candidate, derivative probe or working-set allowance. Its
    inconsistent/unrepresentable cases retain S=M. Unit-scale corrections retain
    the original M-squared motion cost exactly. The motion penalty vanishes with
    the residual instead of overwhelming feasible weak-sensitivity corrections.
    Bounds and current values receive the same positive coordinate transform;
    geometry columns and returned geometric increments use the same positive S.
    Numerical residual coordinates never become material geometry. Return only
    the original coordinates, requiring strict predicted maximum-merit descent;
    nonlinear descent and all final physical/cap certificates remain the caller's.
    Project each geometric vector onto the original coordinate box before step
    limiting: scaled dual feasibility tolerance must not permit outward geometry
    that freezes other useful coordinates. Interior increments remain unchanged.
    At working-set exhaustion or completed raw-inequality rejection, the already
    computed uncertified vector is eligible for this same operation. Report the
    two decline reasons independently. Offer it only through those same merit
    and policy-specific guidance gates: satisfied rows stay strict; default
    violations cannot grow. No further projection, geometry evaluation or
    alternative vector is tried, and the unfinished linear system is not certified.
    If an initially satisfied physical row would cross its halfspace, intersect
    this same bounded correction ray with that row's original zero boundary.
    One scalar contraction preserves the convex coordinate box and every other
    satisfied row. Touching rows receive no new permission; policy-specific
    guidance and strict maximum-merit gates still run afterward. This
    uses only retained linear data, without another projection or nonlinear trial.
    A completed working set also retains its selected coordinate-face identity.
    Restore those exact bounds after undoing numerical scaling, before the same
    ray contraction and predicted gates. Unfinished vectors have no such evidence;
    proximity alone never selects a face or removes positive material.
    Explicit restoration policy scales the existing shared fraction by M for
    already-positive guidance rows, allowing them to trade below the strictly
    decreasing maximum residual. Nonworsening remains the exact default. Both
    policies retain strict satisfied/touching-row gates, the same coordinates,
    working-set/trial limits, and every final physical acceptance requirement.
    Only explicit restoration opts into grouped coordinate-face initialization,
    charged as the first of those same sixteen working-set updates. Seed counters
    describe attempted/dual-feasible initializations, never accepted geometry.
    """
    if not isinstance(guidance_policy, GuidancePolicy):
        raise ValueError("Use an explicit guidance restoration policy")
    if (
        not 7 <= len(residual) <= 19
        or len(jacobian) != len(residual)
        or any(len(row) != len(values) for row in jacobian)
    ):
        raise ValueError("Use six caps and at most thirteen retained physical inequalities")
    before = max(abs(term) if i < 6 else max(0.0, term) for i, term in enumerate(residual))
    if before == 0.0:
        return None
    checkpoint()
    motion_scale = _motion_scale(jacobian, residual, before)
    if evidence is not None and motion_scale != before:
        evidence.cap_metric_calibrations += 1
    augmented = [
        [value / motion_scale for value in row]
        + [-before if index == cap else 0.0 for cap in range(6)]
        + [
            0.0
            if index < 6
            else -before
            if guidance_policy is GuidancePolicy.RESTORATION_MERIT and term > 0
            else -max(0.0, term)
        ]
        for index, (row, term) in enumerate(zip(jacobian, residual))
    ]
    unfinished = UnfinishedProjection()
    faces = ActiveFaces()
    initial = InitializationEvidence()
    solution = active_step(
        _ResidualBounds(model, len(values), motion_scale),
        tuple(value * motion_scale for value in values) + (0.0,) * 7,
        augmented,
        residual,
        checkpoint,
        unfinished=unfinished,
        faces=faces,
        initialization=(
            Initialization.COORDINATE_FACES
            if guidance_policy is GuidancePolicy.RESTORATION_MERIT
            else Initialization.EMPTY
        ),
        initialization_evidence=initial,
    )
    if evidence is not None:
        evidence.coordinate_seed_attempts += initial.attempts
        evidence.coordinate_seed_faces += initial.faces
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
    delta = tuple(value / motion_scale for value in solution[: len(values)])
    if not all(math.isfinite(value) for value in delta):
        return None
    bounded = []
    for index, (value, change) in enumerate(zip(values, delta)):
        low, high = model.bounds(index)
        target = value + change
        bounded.append(
            low - value
            if target < low or index in faces.lower
            else high - value
            if target > high or index in faces.upper
            else change
        )
    restored_faces = sum(
        change != old and (index in faces.lower or index in faces.upper)
        for index, (change, old) in enumerate(zip(bounded, delta))
    )
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
    if not strict_descent(residual, predicted, guidance_policy):
        return None
    if bounded_proposal and evidence is not None:
        evidence.bounded_proposals += 1
    if changed_bounds and evidence is not None:
        evidence.bound_clipped_proposals += 1
    if evidence is not None:
        evidence.active_face_restorations += restored_faces
        if any(old > 0 and new > old + 1e-14 for old, new in zip(residual[6:], predicted[6:])):
            evidence.guidance_tradeoff_proposals += 1
    if fraction < 1.0 and evidence is not None:
        evidence.halfspace_contracted_proposals += 1
    return delta
