"""
Fit shared guide steering sites over the complete nonnegative fixed-radius straight allocation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from cable_bundler.routing.geometry import Vector3, difference, dot
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary

from .features import Chain
from .linear_fit import least_squares


@dataclass(frozen=True)
class Allocation:
    """
    Retain the guide-fit minimum and its exact fixed-radius material route.
    """

    route: FoldRoute
    chain: Chain
    values: tuple[float, ...]
    score: float
    masks: int


def sites(model: Model, chain: Chain, values: tuple[float, ...]) -> tuple[Vector3, ...]:
    """
    Locate shared orientation sites at the midpoint of each complete inter-feature flat interval.
    """
    folds = tuple(p for p in model.pieces(values) if isinstance(p.geometry, CylindricalFold))
    result = []
    for boundary in chain.group_ends:
        before, after = folds[boundary - 1], folds[boundary]
        high = before.geometry.bend_interval(0.0)[1]
        low = after.geometry.bend_interval(0.0)[0]
        a, b = before.surface(high, 0.0)[0], after.surface(low, 0.0)[0]
        result.append(Vector3((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2))
    return tuple(result)


def fit(
    boundary: Boundary,
    chain: Chain,
    threshold_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> Allocation | None:
    """
    Enumerate at most128straight active masks, minimizing shared-site error before material length.

    All fold radii remain at the declared floor. Three hard endpoint equations
    couple the complete chain; guide site positions are a quadratic preference.
    Unlike basic LP vertex ranking, each active mask solves its interior optimum.
    Positive sub-native-tolerance straights reject rather than changing targets or
    relaxing radii. A repeated sliver repair or native construction never runs here.
    """
    model = Model(boundary, chain.topology)
    count = len(chain.topology.folds) + 1
    diameter = boundary.targets.diameter_mm
    columns, right = model.equations()
    zero = (0.0,) * model.size
    base_sites = sites(model, chain, zero)
    site_columns = []
    for index in range(count):
        checkpoint()
        values = [0.0] * model.size
        values[2 * index] = 1.0
        site_columns.append(
            tuple(difference(b, a) for a, b in zip(base_sites, sites(model, chain, tuple(values))))
        )
    objective = [
        [getattr(site_columns[i][j], axis) / diameter for i in range(count)]
        for j in range(len(base_sites))
        for axis in "xyz"
    ]
    wanted = [
        getattr(difference(target.origin, origin), axis) / diameter
        for target, origin in zip(chain.targets, base_sites)
        for axis in "xyz"
    ]
    hard = [[columns[2 * i][axis] for i in range(count)] for axis in range(3)]
    best: Allocation | None = None
    for mask in range(1 << count):
        checkpoint()
        active = [i for i in range(count) if mask & (1 << i)]
        candidate = least_squares(
            [[row[i] for i in active] for row in hard],
            list(right),
            [[row[i] for i in active] for row in objective],
            wanted,
            len(active),
        )
        event: dict[str, Any] = {
            "stage": "feature_allocation",
            "roots": chain.roots,
            "mask": mask,
            "status": "position_unresolved",
        }
        if candidate is not None and min(candidate, default=0.0) >= -1e-9:
            values = [0.0] * model.size
            for i, value in zip(active, candidate):
                values[2 * i] = max(0.0, value)
            if any(0 < value * diameter <= threshold_mm for value in values):
                event["status"] = "sub_tolerance_straight_rejected"
            elif (
                max(
                    abs(math.fsum(row[i] * values[2 * i] for i in range(count)) - target)
                    for row, target in zip(hard, right)
                )
                > 1e-8
            ):
                event["status"] = "closure_residual_rejected"
            else:
                route = FoldRoute(boundary.targets, model.pieces(tuple(values)), boundary.radius_mm)
                if cap_error(route) > 1e-7 or material_error(route) > 1e-10:
                    raise ArithmeticError("Guide feature allocation lost cap/material closure")
                deltas = tuple(
                    difference(point, target.origin)
                    for point, target in zip(sites(model, chain, tuple(values)), chain.targets)
                )
                score = math.fsum(dot(delta, delta) for delta in deltas) / len(deltas)
                event.update(
                    status="closed",
                    score_mm2=score,
                    length_mm=route.material_length_mm,
                    values=values,
                )
                if best is None or (round(score, 12), route.material_length_mm) < (
                    round(best.score, 12),
                    best.route.material_length_mm,
                ):
                    best = Allocation(route, chain, tuple(values), score, 1 << count)
        record(event)
    return best
