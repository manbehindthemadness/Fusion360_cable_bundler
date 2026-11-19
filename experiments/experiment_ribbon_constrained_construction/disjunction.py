"""
Solve declared alternative clearance halfspaces with a finite shared active-set allowance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .envelopes import Exclusion, satisfied
from .linear import Problem, Row, minimize


@dataclass
class Work:
    """
    Debit every root and separation arrangement against the same finite construction work.
    """

    maximum_vertices: int = 4096
    maximum_nodes: int = 64
    vertices: int = 0
    nodes: int = 0
    events: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class Result:
    """
    Retain supplied-constraint feasibility separately from the unconstrained inspection point.
    """

    values: tuple[float, ...] | None
    inspection: tuple[float, ...] | None
    cost: float | None
    status: str


def allocate(
    problem: Problem, exclusions: tuple[Exclusion, ...], checkpoint: Callable[[], None], work: Work
) -> Result:
    """
    Branch on declared disjunctions, using length lower bounds rather than repairing geometry.

    All exclusions are supplied before the first solve. An LP relaxation selects
    an unfulfilled group, whose alternative support arrangements are then explored
    in their input-derived order. No contact witness creates a new constraint and
    no angle, target, radius or guide is altered. Limited or numerically unresolved
    nodes cannot establish infeasibility or global route optimality.
    """
    if (
        type(work.maximum_vertices) is not int
        or work.maximum_vertices <= 0
        or type(work.maximum_nodes) is not int
        or work.maximum_nodes <= 0
    ):
        raise ValueError("Use finite positive shared work bounds")
    pending: list[tuple[tuple[Row, ...], frozenset[int]]] = [(problem.clearance, frozenset())]
    best = None
    inspection = None
    best_cost = None
    while pending:
        checkpoint()
        if work.nodes >= work.maximum_nodes or work.vertices >= work.maximum_vertices:
            return Result(best, inspection, best_cost, "work_limit")
        rows, chosen = pending.pop()
        result = minimize(
            Problem(problem.cost, problem.equalities, rows),
            checkpoint,
            maximum_vertices=work.maximum_vertices - work.vertices,
        )
        work.nodes += 1
        work.vertices += result.vertices_checked
        work.events.append(
            {
                "node": work.nodes,
                "vertices": result.vertices_checked,
                "status": result.status,
                "chosen_exclusions": len(chosen),
                "values": result.values,
                "cost": result.cost,
            }
        )
        if result.values is not None and inspection is None:
            inspection = result.values
        if result.status == "work_limit":
            if (
                result.values is not None
                and all(satisfied(group, result.values) for group in exclusions)
                and (best_cost is None or result.cost < best_cost)
            ):
                best, best_cost = result.values, result.cost
            return Result(best, inspection, best_cost, "work_limit")
        if result.values is None or (best_cost is not None and result.cost >= best_cost):
            continue
        missing = next(
            (i for i, group in enumerate(exclusions) if not satisfied(group, result.values)), None
        )
        if missing is None:
            best, best_cost = result.values, result.cost
            continue
        if missing in chosen:
            raise ArithmeticError("Active separation arrangement lost its own rows")
        selected = chosen | {missing}
        for alternative in reversed(exclusions[missing].alternatives):
            pending.append((rows + alternative, selected))
    return Result(
        best,
        inspection,
        best_cost,
        "supplied_constraints_satisfied" if best is not None else "unresolved",
    )
