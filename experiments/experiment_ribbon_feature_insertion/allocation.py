"""
Fit shared guide steering sites over the complete nonnegative fixed-radius straight allocation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from cable_bundler.routing.geometry import Vector3, difference, dot
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_reduction.closure import AffineWorkspace
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece
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
    return _placed_sites(model.pieces(values), chain)


def _placed_sites(pieces: tuple[PlacedPiece, ...], chain: Chain) -> tuple[Vector3, ...]:
    """
    Reuse one immutable placement for material-route scoring and its shared steering sites.
    """
    folds = tuple(p for p in pieces if isinstance(p.geometry, CylindricalFold))
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
    *,
    maximum_straight_mm: float | None = None,
    feasible_values: tuple[float, ...] | None = None,
) -> Allocation | None:
    """
    Enumerate at most128straight active masks, minimizing shared-site error before material length.

    All fold radii remain at the declared floor. Three hard endpoint equations
    couple the complete chain; guide site positions are a quadratic preference.
    Unlike basic LP vertex ranking, each active mask solves its interior optimum.
    Positive sub-native-tolerance straights reject rather than changing targets or
    relaxing radii. A repeated sliver repair or native construction never runs here.
    An explicit guide-derived straight budget bounds the same active-mask
    solutions, including their active budget face; fold material stays separate.
    Masks are algebraic candidates, not physical certificates. Their fixed fold
    geometry and exact affine position equations determine ranking; full ordered
    cap/material checks run once on the selected allocation before it can return.
    Contact and hardware checks remain the caller's separate responsibility.
    If every guide optimum is inadmissible, an already measured native-cone
    closure can supply the feasible allocation. Recheck all original allocation
    contracts; guide preference never bypasses native size or physical checks.
    """
    model = Model(boundary, chain.topology)
    count = len(chain.topology.folds) + 1
    diameter = boundary.targets.diameter_mm
    columns, right = model.straight_equations()
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
    hard = [[columns[i][axis] for i in range(count)] for axis in range(3)]
    best: Allocation | None = None
    workspace = AffineWorkspace()
    for mask in range(1 << count):
        checkpoint()
        active = [i for i in range(count) if mask & (1 << i)]
        failures: list[str] = []
        candidate = least_squares(
            [[row[i] for i in active] for row in hard],
            list(right),
            [[row[i] for i in active] for row in objective],
            wanted,
            len(active),
            maximum_sum=maximum_straight_mm / diameter if maximum_straight_mm is not None else None,
            workspace=workspace,
            rejected=failures.append,
        )
        event: dict[str, Any] = {
            "stage": "feature_allocation",
            "roots": chain.roots,
            "mask": mask,
            "status": "position_unresolved",
        }
        if failures:
            event["linear_failure"] = failures[-1]
        if candidate is not None and min(candidate, default=0.0) < -1e-9:
            event.update(
                status="negative_straights_rejected", minimum_straight_diameters=min(candidate)
            )
        if candidate is not None and min(candidate, default=0.0) >= -1e-9:
            values = [0.0] * model.size
            for i, value in zip(active, candidate):
                values[2 * i] = max(0.0, value)
            if any(0 < value * diameter <= threshold_mm for value in values):
                event["status"] = "sub_tolerance_straight_rejected"
            elif (
                maximum_straight_mm is not None
                and math.fsum(values[::2]) * diameter > maximum_straight_mm + 1e-8 * diameter
            ):
                event["status"] = "straight_budget_residual_rejected"
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
                deltas = tuple(
                    difference(point, target.origin)
                    for point, target in zip(_placed_sites(route.pieces, chain), chain.targets)
                )
                score = math.fsum(dot(delta, delta) for delta in deltas) / len(deltas)
                event.update(
                    status="closed",
                    score_mm2=score,
                    length_mm=route.material_length_mm,
                    values=values,
                    contract_verification="pending_selection",
                )
                if best is None or (round(score, 12), route.material_length_mm) < (
                    round(best.score, 12),
                    best.route.material_length_mm,
                ):
                    best = Allocation(route, chain, tuple(values), score, 1 << count)
        record(event)
    if best is None and feasible_values is not None:
        return closure_allocation(
            boundary,
            chain,
            feasible_values,
            threshold_mm,
            checkpoint,
            record,
            maximum_straight_mm=maximum_straight_mm,
        )
    if best is not None:
        checkpoint()
        if cap_error(best.route) > 1e-7 or material_error(best.route) > 1e-10:
            raise ArithmeticError("Guide feature allocation lost cap/material closure")
        checkpoint()
        record(
            {
                "stage": "feature_allocation",
                "status": "selected_verified",
                "roots": chain.roots,
                "score_mm2": best.score,
                "length_mm": best.route.material_length_mm,
            }
        )
    return best


def closure_allocation(
    boundary: Boundary,
    chain: Chain,
    values: tuple[float, ...],
    threshold_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_straight_mm: float | None = None,
) -> Allocation | None:
    """
    Verify the same measured cone closure when optional guide fitting supplied no admissible optimum.

    No new root, angular correction, native build or physical certificate is
    attempted. Preserve zero radius growth, strict native straight sizes, original
    sum/affine residual gates and full ordered cap/material checks. Contact and
    hardware acceptance still belong to the ordinary construction caller.
    """
    checkpoint()
    model = Model(boundary, chain.topology)
    diameter = boundary.targets.diameter_mm
    if len(values) != model.size or any(not math.isfinite(value) for value in values):
        raise ValueError("Use complete finite closure coordinates")
    if any(value != 0.0 for value in values[1::2]) or any(
        value < 0 or 0 < value * diameter <= threshold_mm for value in values[::2]
    ):
        return None
    if (
        maximum_straight_mm is not None
        and math.fsum(values[::2]) * diameter > maximum_straight_mm + 1e-8 * diameter
    ):
        return None
    columns, right = model.straight_equations()
    if any(
        abs(
            math.fsum(column[axis] * value for column, value in zip(columns, values[::2]))
            - right[axis]
        )
        > 1e-8
        for axis in range(3)
    ):
        return None
    route = FoldRoute(boundary.targets, model.pieces(values), boundary.radius_mm)
    if cap_error(route) > 1e-7 or material_error(route) > 1e-10:
        return None
    deltas = tuple(
        difference(point, target.origin)
        for point, target in zip(_placed_sites(route.pieces, chain), chain.targets)
    )
    score = math.fsum(dot(delta, delta) for delta in deltas) / len(deltas)
    checkpoint()
    record(
        {
            "stage": "feature_allocation",
            "status": "native_cone_verified",
            "roots": chain.roots,
            "score_mm2": score,
            "length_mm": route.material_length_mm,
            "values": values,
        }
    )
    return Allocation(route, chain, values, score, 1 << (len(chain.topology.folds) + 1))
