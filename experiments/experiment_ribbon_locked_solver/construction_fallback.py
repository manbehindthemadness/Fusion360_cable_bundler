"""
Retain an unchanged original construction when optional work loses terminal hardware eligibility.
"""

from __future__ import annotations

from experiments.experiment_ribbon_feature_insertion.solve import Result as Construction
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_terminal_hardware.gate import Gate


def retain_original(
    original: Construction, current: Construction, terminal: Gate
) -> tuple[FoldRoute, ContactResult] | None:
    """
    Return only the original route and its own strict certificate after shared hardware measurement.

    The caller tries existing optimization and recovery first. Never repeat a
    motion, smoothing pass, contact certificate or allocation here. A changed or
    incomplete baseline grants no evidence. This selection uses the actual
    unchanged route under the same terminal gate and caller resource checkpoints.
    """
    route, contact = original.route, original.contact
    if (
        route is None
        or current.route is None
        or route is current.route
        or original.status != "separated"
        or contact is None
        or contact.status != "separated"
    ):
        return None
    if route.targets != current.route.targets:
        raise ValueError("Retained constructions must share the same fixed targets")
    if not terminal.permits(route, "original_construction_fallback"):
        return None
    return route, contact
