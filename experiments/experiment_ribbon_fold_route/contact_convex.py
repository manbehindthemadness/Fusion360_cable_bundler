"""
Propose overlap points through bounded convex support queries, never infer clearance.
"""

from __future__ import annotations

import itertools
import math
from typing import Callable, Protocol

from cable_bundler.routing.geometry import Vector3

Triple = tuple[float, float, float]
Vertex = tuple[Triple, Triple, Triple]


def add(a: Triple, b: Triple) -> Triple:
    """
    Add immutable world-coordinate triples.
    """
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def subtract(a: Triple, b: Triple) -> Triple:
    """
    Subtract immutable world-coordinate triples.
    """
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def scaled(a: Triple, k: float) -> Triple:
    """
    Scale one world-coordinate triple.
    """
    return a[0] * k, a[1] * k, a[2] * k


def dot(a: Triple, b: Triple) -> float:
    """
    Compute an unnormalized world dot product.
    """
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def triple(vector: Vector3) -> Triple:
    """
    Retain an existing immutable geometry vector as a world triple.
    """
    return vector.x, vector.y, vector.z


class SupportShape(Protocol):
    """
    Supply a deterministic world origin and a convex-hull extremal point.
    """

    @property
    def origin(self) -> Triple:
        """
        Return the common affine material origin used for probe initialization.
        """
        ...

    def support(self, direction: Triple) -> Triple:
        """
        Return a world extremum, charging any constituent queries to the caller.
        """
        ...


def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float] | None:
    """
    Solve at most three affine simplex equations, declining numerically singular faces.
    """
    rows = [row[:] + [value] for row, value in zip(matrix, rhs)]
    for i in range(len(rows)):
        pivot = max(range(i, len(rows)), key=lambda candidate: abs(rows[candidate][i]))
        if abs(rows[pivot][i]) < 1e-18:
            return None
        rows[i], rows[pivot] = rows[pivot], rows[i]
        divisor = rows[i][i]
        rows[i] = [value / divisor for value in rows[i]]
        for j in range(len(rows)):
            if j != i:
                coefficient = rows[j][i]
                rows[j] = [a - coefficient * b for a, b in zip(rows[j], rows[i])]
    return [row[-1] for row in rows]


def _closest(simplex: list[Vertex]) -> tuple[list[Vertex], list[float], Triple]:
    """
    Retain the nearest convex simplex face and its nonnegative barycentric weights.
    """
    best = math.inf
    selected: tuple[list[Vertex], list[float], Triple] | None = None
    for count in range(1, len(simplex) + 1):
        for indices in itertools.combinations(range(len(simplex)), count):
            base = simplex[indices[0]][0]
            vectors = [subtract(simplex[index][0], base) for index in indices[1:]]
            weights = (
                _solve(
                    [[dot(a, b) for b in vectors] for a in vectors],
                    [-dot(v, base) for v in vectors],
                )
                if vectors
                else []
            )
            if weights is None:
                continue
            weights = [1 - sum(weights)] + weights
            if min(weights) < -1e-12:
                continue
            weights = [max(0.0, weight) for weight in weights]
            total = sum(weights)
            weights = [weight / total for weight in weights]
            coordinates = [
                sum(weight * simplex[i][0][k] for i, weight in zip(indices, weights))
                for k in range(3)
            ]
            value = coordinates[0], coordinates[1], coordinates[2]
            distance = dot(value, value)
            if distance < best:
                best = distance
                selected = [simplex[i] for i in indices], weights, value
    if selected is None:
        raise ArithmeticError("Convex witness simplex has no finite face")
    return selected


def overlap_point(
    first: SupportShape, second: SupportShape, checkpoint: Callable[[], None]
) -> Vector3 | None:
    """
    Propose one point with eight GJK steps; every miss and proposed point needs actual-volume checks.

    Convex hulls may contain empty profile valleys. Neither convergence nor a miss
    is a ribbon contact decision. The caller must verify both strict inverse maps.
    """
    simplex: list[Vertex] = []
    nearest = subtract(first.origin, second.origin)
    if dot(nearest, nearest) == 0:
        nearest = 1.0, 0.0, 0.0
    for _ in range(8):
        checkpoint()
        a, b = first.support(scaled(nearest, -1)), second.support(nearest)
        vertex = subtract(a, b)
        if simplex and dot(vertex, nearest) >= dot(nearest, nearest) - 1e-13:
            return None
        simplex.append((vertex, a, b))
        simplex, weights, nearest = _closest(simplex)
        if dot(nearest, nearest) < 1e-20:
            return Vector3(
                *(
                    sum(weight * (v[1][k] + v[2][k]) / 2 for v, weight in zip(simplex, weights))
                    for k in range(3)
                )
            )
    return None
