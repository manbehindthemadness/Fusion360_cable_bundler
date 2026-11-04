"""
Carry completed aesthetic contact evidence only for identical final material geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from devtools.ribbon_analysis.inspection.archive import canonical
from experiments.experiment_ribbon_aesthetic.solve import ContactSchedule
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .smoothing import smooth


@dataclass(frozen=True)
class Result:
    """
    Retain the exact final route and an optional already-completed separation certificate.
    """

    route: FoldRoute
    stages: dict[str, str]
    contact: ContactResult | None


def smooth_with_contact(
    first: FoldRoute,
    percent: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> Result:
    """
    Observe the unchanged smoothing sequence without repeating a completed certificate.

    Only an accepted, separated event with complete measurement metadata is eligible.
    Compare canonical snapshots of every target, primitive and material parameter,
    without rounding or geometric tolerance. Rejected or incomplete measurements
    cannot supply a certificate. Later geometry changes require the caller's normal
    audit. Events still reach the original recorder unchanged; errors propagate.
    """
    certified_geometry: str | None = None
    measurement: ContactResult | None = None

    def observe(event: dict[str, Any]) -> None:
        """
        Freeze separation evidence before forwarding the ordinary proposal event.
        """
        nonlocal certified_geometry, measurement
        contact, geometry = event.get("contact"), event.get("route")
        if (
            event.get("status") == "accepted"
            and isinstance(contact, dict)
            and contact.get("status") == "separated"
            and type(contact.get("pairs_checked")) is int
            and contact["pairs_checked"] >= 0
            and isinstance(contact.get("reason"), str)
            and all(
                key in contact and contact[key] is None
                for key in ("limit", "witness", "unresolved_pieces", "unresolved_regions")
            )
            and isinstance(geometry, dict)
        ):
            certified_geometry = canonical(geometry)
            measurement = ContactResult(
                "separated", contact["pairs_checked"], reason=contact["reason"]
            )
        record(event)

    final, stages = smooth(
        first, percent, checkpoint, observe, contact_schedule=ContactSchedule.FINAL_DESCENT
    )
    if certified_geometry is None or certified_geometry != canonical(snapshot(final)):
        measurement = None
    return Result(final, stages, measurement)
