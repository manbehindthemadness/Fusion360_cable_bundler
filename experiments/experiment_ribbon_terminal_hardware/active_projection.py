"""
Bound a dual active-set least-norm joint projection by sixteen algebraic working-set steps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Literal

from .projection_initialization import Initialization, InitializationEvidence, coordinate_seed
from .projection_system import CoordinateBounds as CoordinateBounds
from .projection_system import dot as _dot
from .projection_system import prepare


@dataclass
class UnfinishedProjection:
    """
    Retain a declined working-set vector and its reason without granting linear feasibility.
    """

    step: tuple[float, ...] | None = None
    stop_reason: Literal["working_set_limit", "raw_inequality"] | None = None


@dataclass
class ActiveFaces:
    """
    Observe coordinate faces selected by a completed, checked working set only.
    """

    lower: frozenset[int] = frozenset()
    upper: frozenset[int] = frozenset()


def _solve(rows: list[list[float]], right: list[float]) -> list[float] | None:
    """
    Solve one independent working-set Gram system, declining singular arithmetic.
    """
    n = len(right)
    matrix = [list(row) + [value] for row, value in zip(rows, right)]
    for k in range(n):
        pivot = max(range(k, n), key=lambda i: abs(matrix[i][k]))
        if abs(matrix[pivot][k]) <= 1e-12:
            return None
        matrix[k], matrix[pivot] = matrix[pivot], matrix[k]
        scale = matrix[k][k]
        matrix[k] = [v / scale for v in matrix[k]]
        for i in range(n):
            if i != k:
                factor = matrix[i][k]
                matrix[i] = [a - factor * b for a, b in zip(matrix[i], matrix[k])]
    return [row[-1] for row in matrix]


def _checked_step(
    base: list[float],
    motion: list[float],
    jacobian: list[list[float]],
    residual: tuple[float, ...],
    *,
    unfinished: UnfinishedProjection | None = None,
) -> tuple[float, ...] | None:
    """
    Apply the original unnormalized inequality gate to an already completed working set.
    """
    result = tuple(a + b for a, b in zip(base, motion))
    if any(r + _dot(row, result) > 1e-14 for row, r in zip(jacobian[6:], residual[6:])):
        if unfinished is not None:
            unfinished.step = result
            unfinished.stop_reason = "raw_inequality"
        return None
    return result


def active_step(
    model: CoordinateBounds,
    values: tuple[float, ...],
    jacobian: list[list[float]],
    residual: tuple[float, ...],
    checkpoint: Callable[[], None],
    *,
    unfinished: UnfinishedProjection | None = None,
    faces: ActiveFaces | None = None,
    initialization: Initialization = Initialization.EMPTY,
    initialization_evidence: InitializationEvidence | None = None,
) -> tuple[float, ...] | None:
    """
    Keep six cap equalities and every supplied inequality using at most sixteen dual updates.

    A final feasibility check also examines the completed sixteenth update.
    This grants no seventeenth working-set update or relaxed acceptance gate.
    An optional receipt retains only an already computed vector at exhaustion
    or completed working-set raw-inequality rejection, with distinct reasons.
    It stays empty on early inconsistency, singular arithmetic or cancellation;
    a receipt is never a certified return value and is cleared before each call.
    Normalize each inequality with a stopping tolerance no larger than either
    the original normalized 1e-14 gate or raw 1e-14 gate divided by its projected norm.
    Pending selection and final feasibility use that same per-row tolerance;
    the original raw return gate remains independent and unchanged.
    Optional face evidence identifies active coordinate inequalities without
    rounding or modifying the returned vector. Failure leaves that evidence empty.
    A pending constraint already satisfied after a dual release completes within
    the current update, retaining its accumulated multiplier. Do not divide its
    nonpositive remaining violation by a small direction norm and mistake the
    resulting negative primal step for infeasibility. Final gates stay unchanged.
    Explicit coordinate initialization replaces the first update with one checked
    dual-feasible seed of two to26initially violated coordinate faces. A declined
    seed consumes that update too. Subsequent ordinary updates may release faces;
    no extra solve, update allowance or acceptance tolerance is granted.
    Normal inner products are lazy and local to this projection's immutable
    normalized constraints. Ordered index pairs retain original dot arithmetic,
    including initialization; no factorization or vector is cached. Every dual
    update, checkpoint, moving-vector product and final gate remains unchanged.
    """
    if faces is not None:
        faces.lower = faces.upper = frozenset()
    if unfinished is not None:
        unfinished.step = None
        unfinished.stop_reason = None
    if initialization_evidence is not None:
        initialization_evidence.attempts = initialization_evidence.faces = 0
    if not isinstance(initialization, Initialization):
        raise ValueError("Use an explicit working-set initialization policy")
    prepared = prepare(model, values, jacobian, residual, checkpoint)
    if prepared is None:
        return None
    base, constraints, face_tags = prepared.base, prepared.constraints, prepared.face_tags

    @lru_cache(maxsize=None)
    def products(first: int, second: int) -> float:
        """
        Evaluate each ordered normal pair once, bounded by this call's finite constraint square.
        """
        return _dot(constraints[first][0], constraints[second][0])

    motion = [0.0] * len(values)
    active: list[int] = []
    multipliers: list[float] = []
    pending: int | None = None
    pending_multiplier = 0.0
    initial_faces = (
        [
            i
            for i, ((_, right, tolerance), tag) in enumerate(zip(constraints, face_tags))
            if tag is not None and -right > tolerance
        ]
        if initialization is Initialization.COORDINATE_FACES
        else []
    )

    def finish() -> tuple[float, ...] | None:
        """
        Retain active face identity only after the original raw physical-row check succeeds.
        """
        result = _checked_step(base, motion, jacobian, residual, unfinished=unfinished)
        if result is not None and faces is not None:
            lower: set[int] = set()
            upper: set[int] = set()
            for chosen_index in active:
                selected_face = face_tags[chosen_index]
                if selected_face is None:
                    continue
                coordinate, side = selected_face
                (lower if side == "lower" else upper).add(coordinate)
            faces.lower, faces.upper = frozenset(lower), frozenset(upper)
        return result

    for update in range(16):
        checkpoint()
        if update == 0 and 2 <= len(initial_faces) <= 26:
            if initialization_evidence is not None:
                initialization_evidence.attempts += 1
            seed = coordinate_seed(
                constraints, initial_faces, _solve, _dot, checkpoint, products=products
            )
            if seed is not None:
                active = initial_faces
                motion, multipliers = list(seed.motion), list(seed.multipliers)
                if initialization_evidence is not None:
                    initialization_evidence.faces = len(active)
            continue
        if pending is None:
            violations = [
                _dot(row, motion) - right - tolerance for row, right, tolerance in constraints
            ]
            pending = (
                max(range(len(violations)), key=lambda i: violations[i]) if violations else None
            )
            if pending is None or violations[pending] <= 0.0:
                return finish()
            pending_multiplier = 0.0
        assert pending is not None
        normal, right, tolerance = constraints[pending]
        violation = _dot(normal, motion) - right
        if violation <= tolerance:
            if pending_multiplier > 0.0:
                active.append(pending)
                multipliers.append(pending_multiplier)
            pending = None
            continue
        normals = [constraints[i][0] for i in active]
        if normals:
            coefficients = _solve(
                [[products(a, b) for b in active] for a in active],
                [products(a, pending) for a in active],
            )
            if coefficients is None:
                return None
        else:
            coefficients = []
        direction = [
            normal[i] - math.fsum(c * row[i] for c, row in zip(coefficients, normals))
            for i in range(len(values))
        ]
        norm2 = _dot(direction, direction)
        primal = violation / norm2 if norm2 > 1e-20 else math.inf
        candidates = [
            (lam / c, i) for i, (lam, c) in enumerate(zip(multipliers, coefficients)) if c > 1e-12
        ]
        dual, leaving = min(candidates, default=(math.inf, -1))
        step = min(primal, dual)
        if not math.isfinite(step) or step < -1e-12:
            return None
        step = max(0.0, step)
        motion = [v - step * d for v, d in zip(motion, direction)]
        multipliers = [max(0.0, lam - step * c) for lam, c in zip(multipliers, coefficients)]
        pending_multiplier += step
        if dual < primal:
            active.pop(leaving)
            multipliers.pop(leaving)
        else:
            active.append(pending)
            multipliers.append(pending_multiplier)
            pending = None
    checkpoint()
    if pending is None and all(
        _dot(row, motion) - right <= tolerance for row, right, tolerance in constraints
    ):
        return finish()
    if unfinished is not None:
        unfinished.step = tuple(a + b for a, b in zip(base, motion))
        unfinished.stop_reason = "working_set_limit"
    return None
