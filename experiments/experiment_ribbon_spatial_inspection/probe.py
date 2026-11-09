"""
Apply one small closure-projected material-coordinate probe after a recorded prediction.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any, Callable

from cable_bundler.routing.geometry import difference
from experiments.experiment_ribbon_bend_relocation.model import (
    ClosurePolicy,
    MovableBends,
    retract_active,
)
from experiments.experiment_ribbon_contraction.runner import restore, snapshot
from experiments.experiment_ribbon_fold_relaxation.steps import advance, projected, step_limit

from .geometry import capture, physical, xyz
from .landmarks import identify, locate


def execute(
    baseline: dict[str, Any],
    prediction: dict[str, Any],
    checkpoint: Callable[[], None],
    record_proposal: Callable[[dict[str, Any]], None],
    analysis_checkpoint: Callable[[], None],
) -> dict[str, Any]:
    """
    Evaluate one requested direction with cap compensation; never search, retry or accept a repair.

    Retraction is the existing at-most-six-Newton/four-halving closure routine.
    Existing radii, target poses, material order and physical coordinate bounds
    remain fixed. Topology changes reject the probe rather than relabeling a point.
    Even a closed diagnostic result has no routing/native acceptance credit.
    """
    route = restore(baseline["route"])
    model = MovableBends(route)
    initial = model.initial
    index = prediction["coordinate"]
    coordinate = baseline["coordinates"][index]
    factor = model.scale if coordinate["unit"] == "mm" else 180 / math.pi
    direction = [0.0] * len(initial)
    direction[index] = prediction["delta"] / factor
    checkpoint()
    rows = model.jacobian(initial)
    delta = projected(model, initial, rows, [0.0] * len(rows), direction)
    if delta is None or max(abs(v) for v in delta) < 1e-12:
        return {
            "status": "blocked",
            "reason": "No nonzero closure-preserving direction for this request",
        }
    trial = advance(model, initial, delta, step_limit(model, initial, delta, 1.0))
    values = retract_active(model, trial, checkpoint, closure_policy=ClosurePolicy.ORDERED_CAPS)
    if values is None:
        return {"status": "blocked", "reason": "Bounded ordered-cap retraction did not close"}
    after = model.route(values)
    if after is None:
        return {"status": "blocked", "reason": "No material route remained after retraction"}
    record_proposal({"route": snapshot(after), "actual_coordinates": list(values)})
    station = baseline["sections"][prediction["section"]]
    identity = identify(route, station["piece"], station["u"])
    corresponding = locate(after, identity)
    if corresponding is None:
        return {
            "status": "blocked",
            "reason": "Ordered material feature disappeared; no landmark correspondence claimed",
        }
    before_point = physical(route.pieces[station["piece"]], station["u"], 0.0, 0.0)
    after_index, after_u = corresponding
    after_point = physical(after.pieces[after_index], after_u, 0.0, 0.0)
    displacement = xyz(difference(after_point, before_point))
    expected = prediction["expected_displacement_mm"]
    error = math.sqrt(sum((a - b) ** 2 for a, b in zip(displacement, expected)))
    for coordinate, before_value, after_value in zip(baseline["coordinates"], initial, values):
        factor = model.scale if coordinate["unit"] == "mm" else 180 / math.pi
        if abs(after_value - before_value) * factor > 4 * coordinate["maximum_delta"]:
            return {
                "status": "blocked",
                "reason": "Cap compensation exceeded the declared local motion bound; proposal retained",
            }
    packet = capture(after, analysis_checkpoint)
    return {
        "status": "measured",
        "after": packet,
        "actual_coordinates": list(values),
        "displacement_mm": displacement,
        "prediction_error_mm": error,
        "prediction_matched": error <= prediction["tolerance_mm"],
        "length_change_mm": after.material_length_mm - route.material_length_mm,
        "landmark": {
            "identity": asdict(identity),
            "after_piece": after_index,
            "after_u": after_u,
            "piece": station["piece"],
            "u": station["u"],
            "q_mm": 0.0,
            "b_mm": 0.0,
        },
        "scope": "One projected direction plus bounded cap compensation; measured prediction, not a solver repair or native validation.",
    }
