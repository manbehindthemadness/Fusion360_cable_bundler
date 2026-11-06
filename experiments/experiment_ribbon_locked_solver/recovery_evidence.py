"""
Prepare recovery from confirmed straight material crossings while retaining original contact evidence.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from enum import Enum
from typing import Any, Callable

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_feature_insertion.separation import Region, regions
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.straight_witness import straight_witness


class EvidencePolicy(Enum):
    """
    Preserve historical depth-only preparation beside confirmed initial straight-sheet tracking.
    """

    DEPTH_ONLY = "depth_only"
    CONFIRMED_SHEETS = "confirmed_sheets"


def adjacent_straight_contact(
    route: FoldRoute,
    measurement: ContactResult,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    policy: EvidencePolicy = EvidencePolicy.DEPTH_ONLY,
) -> tuple[ContactResult, Region | None]:
    """
    Anchor recovery to a proven straight crossing and its moving material plane.

    Examine at most the fold's two immediate neighbors against the opposing
    straight, in material order. Both exact joined-profile inverse maps must
    confirm one shared interior point. A missed witness leaves the original
    undecided evidence unchanged; it never certifies clearance. The returned
    straight region identifies a moving material plane for the same strict gap
    constraint. These analytic checks and later prediction share the caller's
    existing recovery time allowance; no new roots or contact subdivisions.
    Confirmed-sheet policy also prepares existing straight penetration witnesses
    and replaces fold penetration with a confirmed attached-sheet crossing. That
    prevents prediction from ignoring a harder crossing already present in the
    same feature. Original measurements are immutable, and absence of a straight
    witness never implies separation. Historical callers retain depth-only scope.
    """
    if not isinstance(policy, EvidencePolicy):
        raise ValueError("Supply an explicit recovery evidence policy")
    if measurement.status == "unresolved" and measurement.limit == "depth":
        pair = measurement.unresolved_pieces
    elif (
        policy is EvidencePolicy.CONFIRMED_SHEETS
        and measurement.status == "penetration"
        and isinstance(measurement.witness, Penetration)
    ):
        pair = measurement.witness.pieces
    else:
        return measurement, None
    if (
        pair is None
        or len(pair) != 2
        or any(type(i) is not int or not 0 <= i < len(route.pieces) for i in pair)
        or pair[0] >= pair[1]
    ):
        return measurement, None
    if (
        policy is EvidencePolicy.CONFIRMED_SHEETS
        and measurement.status == "penetration"
        and all(isinstance(route.pieces[index].geometry, Straight) for index in pair)
    ):
        checkpoint()
        witness = straight_witness(route, *pair)
        if witness is None:
            return measurement, None
        record(
            {
                "stage": "recovery_contact_evidence",
                "status": "confirmed_straight_pair",
                "original_pair": pair,
                "witness": asdict(witness),
            }
        )
        return (
            replace(
                measurement, witness=witness, reason="Confirmed initial straight-sheet crossing."
            ),
            regions(route)[pair[0]],
        )
    for side, index in enumerate(pair):
        other = pair[1 - side]
        if not isinstance(route.pieces[index].geometry, CylindricalFold) or not isinstance(
            route.pieces[other].geometry, Straight
        ):
            continue
        for neighbor in (index - 1, index + 1):
            if not 0 <= neighbor < len(route.pieces) or neighbor == other:
                continue
            checkpoint()
            first, second = sorted((neighbor, other))
            witness = straight_witness(route, first, second)
            if witness is None:
                continue
            stronger = replace(
                measurement,
                status="penetration",
                witness=witness,
                unresolved_pieces=None,
                unresolved_regions=None,
                limit=None,
                reason="Confirmed attached-straight crossing replaces undecided fold evidence."
                if measurement.status == "unresolved"
                else "Confirmed attached-straight crossing supplements fold penetration evidence.",
            )
            record(
                {
                    "stage": "recovery_contact_evidence",
                    "status": "confirmed_attached_straight",
                    "original_pair": pair,
                    "original_status": measurement.status,
                    "witness": asdict(witness),
                }
            )
            return stronger, regions(route)[first]
    return measurement, None
