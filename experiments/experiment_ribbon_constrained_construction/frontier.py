"""
Compare existing algebraic roots and declared separation arrangements by total material bounds.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import asdict, dataclass
from typing import Any, Callable

from .disjunction import Work
from .envelopes import Exclusion, satisfied
from .linear import Problem, Result, Row, minimize


@dataclass(frozen=True)
class Case:
    """
    Bind one algebraic bend root to its physical length scale and declared exclusions.
    """

    identifier: str
    problem: Problem
    exclusions: tuple[Exclusion, ...]
    unit_mm: float
    fixed_material_mm: float

    def __post_init__(self) -> None:
        """
        Require comparable physical length units without changing any root's geometry.
        """
        if (
            not self.identifier
            or any(
                type(v) not in (int, float) or not math.isfinite(v) or v < 0
                for v in (self.unit_mm, self.fixed_material_mm)
            )
            or self.unit_mm == 0
        ):
            raise ValueError(
                "Cases require an identity, positive unit and nonnegative fixed length"
            )


@dataclass(frozen=True)
class Choice:
    """
    Retain a root identity with its actual coordinates and total material length.
    """

    root: int
    values: tuple[float, ...]
    length_mm: float


@dataclass(frozen=True)
class Node:
    """
    Store one declared arrangement and an optional completed relaxation solution.
    """

    root: int
    rows: tuple[Row, ...]
    chosen: frozenset[int]
    solution: Result | None = None


class Frontier:
    """
    Share one finite work pool across roots before pursuing the cheapest unresolved region.

    Completed numerical LP optima provide ordering/pruning bounds within the
    supplied affine problem only. Partial LP costs never supply lower bounds.
    Mutable best/inspection state preserves completed evidence on external stops.
    Physical qualification and branch-representation completeness remain external.
    """

    def __init__(
        self,
        cases: tuple[Case, ...],
        work: Work,
        *,
        trace: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """
        Freeze at most eight existing roots and start one nonrenewable shared frontier.

        Optional tracing observes completed LPs and executed separation branches.
        Recorder failures propagate; callback time remains in caller wall/CPU use.
        """
        if not 1 <= len(cases) <= 8 or work.maximum_vertices <= 0 or work.maximum_nodes <= 0:
            raise ValueError("Use one to eight roots and positive shared work limits")
        self.cases = cases
        self.work = work
        self.trace = trace
        self.best: Choice | None = None
        self.inspection: Choice | None = None
        self.roots_relaxed: list[int] = []
        self.status = "unattempted"
        self._pending: list[tuple[float, int, Node]] = []
        self._serial = 0

    def _choice(self, root: int, result: Result) -> Choice | None:
        """
        Compare actual millimeters, including fold material constant within this root.
        """
        if result.values is None or result.cost is None:
            return None
        case = self.cases[root]
        return Choice(root, result.values, case.fixed_material_mm + case.unit_mm * result.cost)

    def _push(self, bound: float, node: Node) -> None:
        """
        Preserve stable declared order only when physical length bounds tie.
        """
        heapq.heappush(self._pending, (bound, self._serial, node))
        self._serial += 1

    def _solve(self, node: Node, checkpoint: Callable[[], None]) -> Result | None:
        """
        Debit each LP once, retaining feasible points even when enumeration is incomplete.
        """
        if (
            self.work.nodes >= self.work.maximum_nodes
            or self.work.vertices >= self.work.maximum_vertices
        ):
            self.status = "work_limit"
            return None
        case = self.cases[node.root]
        result = minimize(
            Problem(case.problem.cost, case.problem.equalities, node.rows),
            checkpoint,
            maximum_vertices=self.work.maximum_vertices - self.work.vertices,
        )
        self.work.nodes += 1
        self.work.vertices += result.vertices_checked
        choice = self._choice(node.root, result)
        self.work.events.append(
            {
                "node": self.work.nodes,
                "root": node.root,
                "root_identifier": case.identifier,
                "status": result.status,
                "vertices": result.vertices_checked,
                "values": result.values,
                "total_material_mm": choice.length_mm if choice else None,
                "chosen_exclusions": len(node.chosen),
            }
        )
        if choice is not None:
            if self.inspection is None or choice.length_mm < self.inspection.length_mm:
                self.inspection = choice
            if all(satisfied(group, choice.values) for group in case.exclusions) and (
                self.best is None or choice.length_mm < self.best.length_mm
            ):
                self.best = choice
        if result.status == "work_limit":
            self.status = "work_limit"
        if self.trace is not None:
            self.trace(
                {
                    **self.work.events[-1],
                    "stage": "allocation",
                    "rows": [asdict(row) for row in node.rows],
                    "unsatisfied_exclusions": [
                        group.name
                        for group in case.exclusions
                        if choice is not None and not satisfied(group, choice.values)
                    ],
                    "best_root": self.best.root if self.best else None,
                    "best_length_mm": self.best.length_mm if self.best else None,
                }
            )
        return result

    def run(self, checkpoint: Callable[[], None]) -> None:
        """
        Relax every root once, then explore the globally lowest outstanding length bound.

        Every child inherits its parent's completed relaxation bound until its
        own LP is solved. A raised child bound reenters the frontier before
        subdivision, allowing other roots/arrangements to compete. No guesses,
        collision-driven angle changes or additional roots enter this traversal.
        """
        if self.status != "unattempted":
            raise RuntimeError("A construction frontier cannot be replayed or renewed")
        self.status = "running"
        for root, case in enumerate(self.cases):
            checkpoint()
            node = Node(root, case.problem.clearance, frozenset())
            result = self._solve(node, checkpoint)
            if result is None or self.status == "work_limit":
                return
            self.roots_relaxed.append(root)
            choice = self._choice(root, result)
            if choice is not None:
                self._push(choice.length_mm, Node(root, node.rows, node.chosen, result))
        while self._pending:
            checkpoint()
            bound, _, node = heapq.heappop(self._pending)
            if self.best is not None and bound >= self.best.length_mm:
                continue
            case = self.cases[node.root]
            result = node.solution
            if result is None:
                result = self._solve(node, checkpoint)
                if result is None or self.status == "work_limit":
                    return
                choice = self._choice(node.root, result)
                if choice is not None:
                    self._push(
                        max(bound, choice.length_mm),
                        Node(node.root, node.rows, node.chosen, result),
                    )
                continue
            assert result.values is not None
            missing = next(
                (
                    i
                    for i, group in enumerate(case.exclusions)
                    if not satisfied(group, result.values)
                ),
                None,
            )
            if missing is None:
                continue
            if missing in node.chosen:
                raise ArithmeticError("Active arrangement lost its own constraints")
            if self.trace is not None:
                self.trace(
                    {
                        "stage": "separation_branch",
                        "root": node.root,
                        "exclusion": asdict(case.exclusions[missing]),
                        "parent_length_bound_mm": bound,
                    }
                )
            for alternative in case.exclusions[missing].alternatives:
                self._push(bound, Node(node.root, node.rows + alternative, node.chosen | {missing}))
        self.status = "supplied_constraints_satisfied" if self.best is not None else "unresolved"
