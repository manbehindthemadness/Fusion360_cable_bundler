"""
Solve nonnegative straight closure after a prescribed fold-structure rewrite.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import Vector3


def _projection(
    rows: list[list[float]], right: list[float], reference: list[float]
) -> list[float] | None:
    """
    Project onto an affine equality set, rejecting inconsistent dependent rows.
    """
    basis: list[tuple[list[float], float]] = []
    for row, target in zip(rows, right):
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
                return None
        else:
            basis.append(([a / norm for a in residual], value / norm))
    result = list(reference)
    for vector, beta in basis:
        correction = beta - math.fsum(a * b for a, b in zip(vector, reference))
        result = [a + correction * b for a, b in zip(result, vector)]
    return result


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
        values = _projection(
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
