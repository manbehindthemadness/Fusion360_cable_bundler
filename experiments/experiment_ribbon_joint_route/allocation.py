"""
Close position by jointly allocating nonnegative travel and material-fold radius growth.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from functools import cached_property, lru_cache
from itertools import combinations
from typing import Any, Callable

from cable_bundler.routing.geometry import difference
from experiments.experiment_ribbon_bend_reduction.closure import affine_projection
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import Piece

from .boundary import FoldBoundary
from .frames import Topology


@dataclass(frozen=True)
class Allocation:
    """
    Retain a fully closed first-pass candidate and its deterministic affine support.
    """

    topology: str
    support: tuple[int, ...]
    values: tuple[float, ...]
    route: FoldRoute


@dataclass(frozen=True)
class Model:
    """
    Place straight slots around every derived fold; radii grow above the declared bound.

    Coordinates alternate straight travel and radius growth, normalized by diameter.
    Fold angles/banks are derived from the endpoint/guide frames, not inherited from
    an old route. No straight is inserted for envelope separation. Joint closure
    determines all lengths before any contact check or native construction.
    """

    source: FoldBoundary
    topology: Topology

    @property
    def size(self) -> int:
        """
        Count one radius per fold and one more straight slot than folds.
        """
        return 2 * len(self.topology.folds) + 1

    def pieces(self, values: tuple[float, ...]) -> tuple[PlacedPiece, ...]:
        """
        Validate every request before reusing exact placements within this immutable model.

        Endpoint equations and guide-site columns often request the same basis
        vectors. At most64 coordinate tuples are retained per model; neither
        other topologies nor recursive model hashes participate in lookup.
        """
        if len(values) != self.size or any(not math.isfinite(v) or v < 0 for v in values):
            raise ValueError("Supply finite nonnegative joint allocation coordinates.")
        return self._placements(tuple(values))

    @cached_property
    def _placements(self) -> Callable[[tuple[float, ...]], tuple[PlacedPiece, ...]]:
        """
        Bind bounded placement reuse to this model's fixed targets and fold topology.
        """
        return lru_cache(maxsize=64)(self._place)

    def _place(self, values: tuple[float, ...]) -> tuple[PlacedPiece, ...]:
        """
        Recompose an already validated vector with the original ordered placement arithmetic.
        """
        target = self.source.targets
        pose = Pose(target.start, target.start_tangent, target.start_width)
        result = []
        for index in range(len(self.topology.folds) + 1):
            geometries: list[Piece] = []
            if values[2 * index] > 1e-10:
                geometries.append(Straight(values[2 * index] * target.diameter_mm))
            if index < len(self.topology.folds):
                original = self.topology.folds[index]
                geometries.append(
                    replace(
                        original,
                        radius_mm=original.radius_mm + values[2 * index + 1] * target.diameter_mm,
                    )
                )
            for geometry in geometries:
                piece = PlacedPiece(pose, geometry, f"Joint first-pass piece{len(result) + 1}")
                result.append(piece)
                pose = piece.end_pose()
        return tuple(result)

    def endpoint(self, values: tuple[float, ...]) -> Pose:
        """
        Evaluate the full affine placement, including a zero-fold/zero-travel origin.
        """
        pieces = self.pieces(values)
        target = self.source.targets
        return (
            pieces[-1].end_pose()
            if pieces
            else Pose(target.start, target.start_tangent, target.start_width)
        )

    def equations(
        self,
    ) -> tuple[tuple[tuple[float, float, float], ...], tuple[float, float, float]]:
        """
        Derive exact displacement columns independently of nonnegative length choices.
        """
        return self._equations(range(self.size))

    def straight_equations(
        self,
    ) -> tuple[tuple[tuple[float, float, float], ...], tuple[float, float, float]]:
        """
        Derive the identical straight columns without evaluating unused radius-growth coordinates.

        Fixed-radius allocation keeps every radius coordinate zero. Full joint
        allocation retains equations(), including all original radius columns.
        """
        return self._equations(range(0, self.size, 2))

    def _equations(
        self, indices: range
    ) -> tuple[tuple[tuple[float, float, float], ...], tuple[float, float, float]]:
        """
        Evaluate only the requested ordered basis vectors using the shared original affine placement.
        """
        zero = (0.0,) * self.size
        origin = self.endpoint(zero).origin
        diameter = self.source.targets.diameter_mm
        columns: list[tuple[float, float, float]] = []
        for index in indices:
            values = list(zero)
            values[index] = 1.0
            offset = difference(self.endpoint(tuple(values)).origin, origin)
            columns.append((offset.x / diameter, offset.y / diameter, offset.z / diameter))
        delta = difference(self.source.targets.end, origin)
        return tuple(columns), (delta.x / diameter, delta.y / diameter, delta.z / diameter)


def allocations(
    model: Model, checkpoint: Callable[[], None], record: Callable[[dict[str, Any]], None]
) -> tuple[Allocation, ...]:
    """
    Enumerate nonnegative basic position closures, with at most three positive values.

    Three affine position equations yield the finite LP vertices for any linear
    material cost. Degenerate supports are included. Comparing sampled guide RMS
    among these vertices does not find its nonlinear minimum over the whole polytope.
    Every consistent dependent-support projection is retained as a candidate, not
    mistaken for a physical certificate. Complete cap vectors are checked separately.
    """
    if model.size > 13:
        raise ValueError("Joint construction supports at most six derived folds.")
    columns, right = model.equations()
    output = []
    seen = set()
    for count in range(4):
        for support in combinations(range(model.size), count):
            checkpoint()
            rows = [[columns[i][axis] for i in support] for axis in range(3)]
            projected = affine_projection(rows, list(right), [0.0] * count)
            event: dict[str, Any] = {
                "stage": "linear_support",
                "topology": model.topology.identifier,
                "support": support,
            }
            if projected is None or min(projected, default=0) < -1e-9:
                event["status"] = "infeasible"
                record(event)
                continue
            values = [0.0] * model.size
            for index, value in zip(support, projected):
                values[index] = max(0.0, value)
            if any(
                abs(
                    math.fsum(column[axis] * value for column, value in zip(columns, values))
                    - right[axis]
                )
                > 1e-8
                for axis in range(3)
            ):
                event["status"] = "equation_residual_rejected"
                record(event)
                continue
            signature = tuple(round(v, 10) for v in values)
            if signature in seen:
                event["status"] = "duplicate"
                record(event)
                continue
            seen.add(signature)
            pieces = model.pieces(tuple(values))
            if not pieces:
                event["status"] = "empty"
                record(event)
                continue
            route = FoldRoute(model.source.targets, pieces, model.source.radius_mm)
            if cap_error(route) > 1e-7:
                event["status"] = "cap_residual_rejected"
                record(event)
                continue
            event.update(status="closed", values=values, route=snapshot(route))
            record(event)
            output.append(Allocation(model.topology.identifier, support, tuple(values), route))
    return tuple(output)
