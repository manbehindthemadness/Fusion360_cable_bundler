"""
Replace uncertain fold evidence only with a proven crossing of its attached straight sheet.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any, Callable

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_feature_insertion.separation import Region, regions
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.straight_witness import straight_witness


def adjacent_straight_contact(
    route: FoldRoute,
    measurement: ContactResult,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> tuple[ContactResult, Region | None]:
    """
    Anchor validated depth recovery to a confirmed adjoining straight crossing when available.

    Examine at most the fold's two immediate neighbors against the opposing
    straight, in material order. Both exact joined-profile inverse maps must
    confirm one shared interior point. A missed witness leaves the original
    undecided evidence unchanged; it never certifies clearance. The returned
    straight region identifies a moving material plane for the same strict gap
    constraint. These analytic checks and later prediction share the caller's
    existing recovery time allowance; no new roots or contact subdivisions.
    """
    pair = measurement.unresolved_pieces
    if (
        measurement.status != "unresolved"
        or measurement.limit != "depth"
        or pair is None
        or len(pair) != 2
        or any(type(i) is not int or not 0 <= i < len(route.pieces) for i in pair)
    ):
        return measurement, None
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
                reason="Confirmed attached-straight crossing replaces undecided fold evidence.",
            )
            record(
                {
                    "stage": "recovery_contact_evidence",
                    "status": "confirmed_attached_straight",
                    "original_pair": pair,
                    "witness": asdict(witness),
                }
            )
            return stronger, regions(route)[first]
    return measurement, None
