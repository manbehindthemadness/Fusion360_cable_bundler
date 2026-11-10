"""
Select one return turn from the occupied material interval rather than terminal or adjacency labels.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_feature_insertion.contact_recovery import Recovery
from experiments.experiment_ribbon_fold_route.contact import Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .feature_guidance import MaterialGuidance
from .gate import Gate
from .joint_contact import recover as recover_joints


def select_fold(route: FoldRoute, witness: Penetration) -> int | None:
    """
    Choose the largest accumulated lane turn between the two actual colliding material locations.

    Each endpoint uses its own occupied lane and bend fraction. Interior folds
    contribute their complete turn; flat runways contribute none. Accumulated
    tangent turning is bend angle times cosine of bank, independent of rigid
    placement, length scale and primitive adjacency. Ties keep material order.
    This is a deterministic correction choice, never a clearance or feasibility
    certificate. No alternative fold is tried after its correction fails.
    """
    first, last = witness.pieces
    if any(type(i) is not int for i in witness.pieces) or not 0 <= first < last < len(route.pieces):
        raise ValueError("A crossing must identify ordered existing material pieces")
    for coordinates in (witness.first, witness.second):
        u, q, _ = coordinates
        if (
            any(isinstance(v, bool) or not math.isfinite(v) for v in coordinates)
            or not 0 <= u <= 1
            or abs(q) > route.half_width_mm
        ):
            raise ValueError("Crossing coordinates must lie within the occupied material domain")
    selected, largest, ordinal = None, 0.0, 0
    for index, piece in enumerate(route.pieces):
        geometry = piece.geometry
        if not isinstance(geometry, CylindricalFold):
            continue
        if first <= index <= last:
            low, high = 0.0, 1.0
            if index in (first, last):
                u, q, _ = witness.first if index == first else witness.second
                entry, exit = geometry.bend_interval(q)
                fraction = min(1.0, max(0.0, (u - entry) / (exit - entry)))
                if index == first:
                    low = fraction
                else:
                    high = fraction
            turn = (high - low) * abs(geometry.angle_radians) * math.cos(geometry.bank_radians)
            if turn > largest:
                selected, largest = ordinal, turn
        ordinal += 1
    return selected


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
