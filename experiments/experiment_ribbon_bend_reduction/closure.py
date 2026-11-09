"""
Solve nonnegative straight closure after a prescribed fold-structure rewrite.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Sequence

from cable_bundler.routing.geometry import Vector3

_Basis = list[tuple[Sequence[float], float]]
_FrozenBasis = tuple[tuple[tuple[float, ...], float], ...]


def _append_basis(basis: _Basis, row: Sequence[float], target: float) -> bool:
    """
    Extend one ordered affine basis with the original two-pass orthogonalization and rank gates.
    """
    residual = list(row)
    value = target
    for _ in range(2):
        for vector, beta in basis:
            coefficient = math.fsum(a * b for a, b in zip(residual, vector))
            residual = [a - coefficient * b for a, b in zip(residual, vector)]
            value -= coefficient * beta
    norm = math.sqrt(math.fsum(a * a for a in residual))
    if norm <= 1e-10:
        if abs(value) > 1e-8:
            return False
    else:
        basis.append(([a / norm for a in residual], value / norm))
    return True


def _project_basis(
    basis: Sequence[tuple[Sequence[float], float]], reference: list[float]
) -> list[float]:
    """
    Preserve the original ordered correction arithmetic for a prepared affine basis.
    """
    result = list(reference)
    for vector, beta in basis:
        correction = beta - math.fsum(a * b for a, b in zip(vector, reference))
        result = [a + correction * b for a, b in zip(result, vector)]
    return result


class AffineWorkspace:
    """
    Reuse at most64immutable ordered row-prefix bases within one active-set projection.

    Full coefficient rows and right sides identify each prefix exactly. Reference
    vectors do not affect the basis and are applied afresh. No global cache or
    additional candidate, arithmetic shortcut, tolerance or iteration is used.
    """

    def __init__(self) -> None:
        """
        Own bounded prefix reuse for one projection action, independently of other models.
        """
        self._basis = lru_cache(maxsize=64)(self._build)

    def _build(
        self, rows: tuple[tuple[float, ...], ...], right: tuple[float, ...]
    ) -> _FrozenBasis | None:
        """
        Extend an immutable common prefix using the same shared row operation as uncached projection.
        """
        if not rows:
            return ()
        previous = self._basis(rows[:-1], right[:-1])
        if previous is None:
            return None
        basis: _Basis = list(previous)
        if not _append_basis(basis, rows[-1], right[-1]):
            return None
        return tuple((tuple(vector), beta) for vector, beta in basis)

    def project(
        self, rows: list[list[float]], right: list[float], reference: list[float]
    ) -> list[float] | None:
        """
        Project against exact immutable matrix snapshots without exposing cached mutable vectors.
        """
        if len(rows) != len(right) or any(len(row) != len(reference) for row in rows):
            raise ValueError("Affine workspace requires matching rows, targets and reference size")
        basis = self._basis(tuple(tuple(row) for row in rows), tuple(right))
        return None if basis is None else _project_basis(basis, reference)


def affine_projection(
    rows: list[list[float]], right: list[float], reference: list[float]
) -> list[float] | None:
    """
    Project onto an affine equality set, rejecting inconsistent dependent rows.
    """
    basis: _Basis = []
    for row, target in zip(rows, right):
        if not _append_basis(basis, row, target):
            return None
    return _project_basis(basis, reference)


def close_lengths(
    directions: tuple[Vector3, ...], displacement: Vector3, reference: tuple[float, ...]
) -> tuple[float, ...] | None:
    """
    Find the unique least-change nonnegative closure by enumerating active sets.

    Minimize squared change from the supplied straight lengths subject to the
    three endpoint position equations. New connector slots have zero reference.
    Enumerate every zero/free mask, at most1024, in fixed order; this is a finite
    convex projection, not a route guess or length optimizer. No feasible mask
    means this fixed rewrite cannot close with nonnegative straight lengths.
    """
    if len(directions) != len(reference) or len(reference) > 10:
        raise ValueError("Use matching direction/reference counts, at most ten slots.")
    if any(not math.isfinite(value) or value < 0 for value in reference):
        raise ValueError("Reference lengths must be finite and nonnegative.")
    best: tuple[float, ...] | None = None
    best_cost = math.inf
    for mask in range(1 << len(reference)):
        active = [i for i in range(len(reference)) if mask & (1 << i)]
        rows = [[getattr(directions[i], axis) for i in active] for axis in "xyz"]
        values = affine_projection(
            rows, [getattr(displacement, axis) for axis in "xyz"], [reference[i] for i in active]
        )
        if values is None or min(values, default=0) < -1e-9:
            continue
        candidate = [0.0] * len(reference)
        for index, value in zip(active, values):
            candidate[index] = max(0.0, value)
        if any(
            abs(
                math.fsum(
                    getattr(axis, coordinate) * length
                    for axis, length in zip(directions, candidate)
                )
                - getattr(displacement, coordinate)
            )
            > 1e-8
            for coordinate in "xyz"
        ):
            continue
        cost = math.fsum((value - prior) ** 2 for value, prior in zip(candidate, reference))
        if cost < best_cost:
            best, best_cost = tuple(candidate), cost
    return best
