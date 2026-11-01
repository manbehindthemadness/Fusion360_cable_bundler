"""
Derive endpoint-preserving descent for straight runs between immutable folds.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import Vector3


def shortening_direction(directions: tuple[Vector3, ...]) -> tuple[float, ...]:
    """
    Project negative length gradient into the endpoint displacement nullspace.

    Rows are world XYZ components of the unit straight directions. Twice-applied
    modified Gram-Schmidt handles dependent rows without a matrix dependency.
    The returned projected gradient gives steepest descent after normalization;
    zero means no free shortening direction for this fixed-fold representation.
    It does not account for nonnegative lengths or self-contact.
    """
    rows = [tuple(getattr(axis, coordinate) for axis in directions) for coordinate in "xyz"]
    basis: list[tuple[float, ...]] = []
    for row in rows:
        residual = list(row)
        for _ in range(2):
            for vector in basis:
                coefficient = math.fsum(a * b for a, b in zip(residual, vector))
                residual = [a - coefficient * b for a, b in zip(residual, vector)]
        norm = math.sqrt(math.fsum(value * value for value in residual))
        if norm > 1e-10:
            basis.append(tuple(value / norm for value in residual))
    result = [-1.0] * len(directions)
    for vector in basis:
        coefficient = -math.fsum(vector)
        result = [a - coefficient * b for a, b in zip(result, vector)]
    return tuple(result)
