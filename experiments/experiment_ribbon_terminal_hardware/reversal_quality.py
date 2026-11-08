"""
Predict whether the initial bounded reflection should yield to existing length-constrained joints.
"""

from __future__ import annotations

from typing import Callable

from .active_projection import active_step
from .reversal_model import ReversalModel


def decline_initial_length(
    model: ReversalModel, maximum_length_mm: float, checkpoint: Callable[[], None]
) -> bool:
    """
    Decline only when bounded cap motion exists but its length-constrained projection does not.

    Both projections use the same initial Jacobian, coordinate bounds and sixteen
    algebraic working-set steps. A declined projection is a local strategy signal,
    not proof that nonlinear closure is impossible. No proposed coordinate is
    applied, no update is consumed, and the caller charges preparation to its
    original CPU/wall allowance. Cap-infeasible predictions preserve the existing
    reflection and radius-restoration sequence.
    """
    values = model.initial
    residual = model.residual(values)
    matrix = model.jacobian(values)
    cap_motion = active_step(
        model, values, matrix + [[0.0] * len(values)], residual + (0.0,), checkpoint
    )
    if cap_motion is None:
        return False
    gradient = model.full.length_gradient(model.expanded(values))
    length_row = [gradient[i] for i in model.indices]
    reflected = model.route(values)
    assert reflected is not None
    excess = (reflected.material_length_mm - maximum_length_mm) / model.scale
    length_motion = active_step(
        model, values, matrix + [length_row], residual + (excess,), checkpoint
    )
    return length_motion is None
