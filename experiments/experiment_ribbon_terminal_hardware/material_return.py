"""
Select one return turn from the occupied material interval rather than terminal or adjacency labels.
"""

from __future__ import annotations

from typing import Any, Callable

from experiments.experiment_ribbon_feature_insertion.contact_recovery import Recovery
from experiments.experiment_ribbon_fold_route.contact import Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .feature_guidance import MaterialGuidance
from .gate import Gate
from .joint_contact import recover as recover_joints
from .material_return_selection import select_fold as select_fold


def recover(
    source: FoldRoute,
    witness: Penetration,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    remaining_pairs: int,
    maximum_cpu_seconds: float,
    maximum_seconds: float,
    maximum_updates: int,
) -> Recovery | None:
    """
    Jointly close one reflected return and its complete occupied material regions within original work.

    Parent length is a ceiling rather than a compulsory shortening target. Strict
    curved contacts use shared analytic whole-piece guidance. Unsupported
    evidence returns without motion. Every attempted correction still needs the full contact and
    hardware certificates. No failed action starts another reflected candidate.
    """
    selected = select_fold(source, witness)
    if selected is None:
        return None
    result = recover_joints(
        source,
        witness,
        terminal,
        checkpoint,
        record,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
        remaining_pairs=remaining_pairs,
        maximum_cpu_seconds=maximum_cpu_seconds,
        maximum_seconds=maximum_seconds,
        maximum_updates=maximum_updates,
        mode=MaterialGuidance(selected),
    )
    if result is None:
        record(
            {
                "stage": "material_return",
                "status": "unsupported_flat_guidance",
                "selected_fold": selected,
            }
        )
        return None
    record(
        {
            "stage": "material_return",
            "status": result.detail["status"],
            "selected_fold": selected,
            "pieces": witness.pieces,
            "detail": result.detail,
        }
    )
    return Recovery(
        result.route if result.contact is not None else None,
        result.contact,
        result.detail["contact_pairs"],
        result.detail["contacts"],
        result.detail["contact_seconds"],
        result.detail,
    )
