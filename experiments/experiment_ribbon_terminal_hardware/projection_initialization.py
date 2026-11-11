"""
Initialize a dual-feasible coordinate working set within one existing algebraic update.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Sequence


class Initialization(Enum):
    """
    Preserve empty initialization or explicitly group initially violated coordinate faces.
    """

    EMPTY = "empty"
    COORDINATE_FACES = "coordinate_faces"


@dataclass
class InitializationEvidence:
    """
    Observe attempted and committed initializations, without certifying the complete projection.
    """

    attempts: int = 0
    faces: int = 0


@dataclass(frozen=True)
class Seed:
    """
    Retain one checked dual-feasible state whose selected equalities remain active.
    """

    motion: tuple[float, ...]
    multipliers: tuple[float, ...]


def coordinate_seed(
    constraints: list[tuple[list[float], float, float]],
    selected: list[int],
    solve: Callable[[list[list[float]], list[float]], list[float] | None],
    dot: Callable[[Sequence[float], Sequence[float]], float],
    checkpoint: Callable[[], None],
    *,
    products: Callable[[int, int], float] | None = None,
) -> Seed | None:
    """
    Solve one selected Gram system, declining negative duals or inaccurate active equalities.

    Callers charge this as their first permitted working-set update, including
    a declined initialization. Each seed is bounded to26coordinate faces;
    larger clusters retain empty initialization. This state has
    no authority over unselected inequalities or final physical acceptance.
    An optional indexed product supplies the identical immutable normal inner
    products shared with this call's working set. Motion checks still use dot;
    no solution, factorization or feasibility decision is reused.
    """
    if not 2 <= len(selected) <= 26:
        raise ValueError("Initialize between two and26coordinate faces")
    normals = [constraints[index][0] for index in selected]
    gram = []
    for index, normal in zip(selected, normals):
        checkpoint()
        gram.append(
            [products(index, other) for other in selected]
            if products is not None
            else [dot(normal, other) for other in normals]
        )
    multipliers = solve(gram, [-constraints[index][1] for index in selected])
    if multipliers is None or any(not math.isfinite(v) or v < 0 for v in multipliers):
        return None
    checkpoint()
    motion = tuple(
        -math.fsum(value * normal[i] for value, normal in zip(multipliers, normals))
        for i in range(len(normals[0]))
    )
    if any(not math.isfinite(value) for value in motion):
        return None
    if any(
        abs(dot(constraints[index][0], motion) - constraints[index][1]) > constraints[index][2]
        for index in selected
    ):
        return None
    return Seed(motion, tuple(multipliers))
