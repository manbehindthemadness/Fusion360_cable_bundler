"""
Choose correction or event refinement from current material ownership, without renewing work.
"""

from __future__ import annotations

from enum import Enum

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .adaptive_event_window import Edit, EventId
from .check import Report
from .deviation_sequence import HARDWARE_PREPARATION_DECLINES


class Correction(Enum):
    """
    Keep the one original fixed-correction entry available or irreversibly consumed.
    """

    READY = "ready"
    SPENT = "spent"


class Action(Enum):
    """
    Describe the next bounded action and why correction takes priority over another rewrite.
    """

    REFINE = "refine"
    CORRECT_MODULE = "correct_owned_module"
    CORRECT_EXHAUSTED = "correct_exhausted_roots"
    CORRECT_DECLINED = "correct_declined_allocation"
    STOP = "stop"


def choose(
    current: FoldRoute,
    evidence: ContactResult | Report,
    evidence_source: FoldRoute,
    lineage: tuple[EventId, ...],
    edits: tuple[Edit, ...],
    roots_attempted: int,
    correction: Correction,
) -> Action:
    """
    Prefer correcting an already inserted, still-owned witnessed module over rebuilding it again.

    A blocker outside inserted material may need new local events. Exact intact
    ownership, not old ordinals or an event-count threshold, chooses that path.
    Geometry preparation revalidates the actual occupied witness before motion;
    this decision grants no physical certificate or new resource allocation.
    """
    if type(roots_attempted) is not int or not 0 <= roots_attempted <= 8:
        raise ValueError("Keep the original local root counter")
    if not isinstance(correction, Correction):
        raise ValueError("Keep explicit correction lifecycle state")
    witness = evidence.witness
    if (
        evidence_source is not current
        or witness is None
        or evidence.status != ("blocked" if isinstance(evidence, Report) else "penetration")
        or (isinstance(evidence, ContactResult) and evidence.limit is not None)
    ):
        return Action.STOP
    if isinstance(evidence, Report):
        assert evidence.witness is not None
        members = (evidence.witness.piece,)
    else:
        assert evidence.witness is not None
        members = evidence.witness.pieces
    if any(type(member) is not int or not 0 <= member < len(current.pieces) for member in members):
        return Action.STOP
    if correction is Correction.READY:
        if roots_attempted == 8:
            return Action.CORRECT_EXHAUSTED
        for edit in edits:
            window = edit.inserted_window(current, lineage)
            if window is not None and any(
                window.begin <= member < window.end for member in members
            ):
                return Action.CORRECT_MODULE
    return Action.REFINE if roots_attempted < 8 else Action.STOP


def preparation_declined(
    result: Result, current: FoldRoute, evidence: ContactResult | Report
) -> bool:
    """
    Permit further event work only after an explicit unchanged hardware-preparation decline.

    Zero accepted Newton steps alone cannot prove this: rejected retraction
    trials and initial reflections are motion attempts too. Unknown receipts,
    measured contact, a moved route or phase failures cannot authorize fallback.
    The caller must independently check its remaining original allocation.
    """
    detail = result.detail
    return (
        isinstance(evidence, Report)
        and evidence.status == "blocked"
        and evidence.witness is not None
        and result.contact is None
        and result.route is current
        and detail.get("status") == "unresolved"
        and detail.get("hardware_preparation_only") is True
        and detail.get("motion_attempted") is False
        and type(detail.get("stages")) is int
        and detail["stages"] == 1
        and type(detail.get("iterations")) is int
        and detail["iterations"] >= 1
        and all(
            type(detail.get(key)) is int and detail[key] == 0
            for key in ("newton_steps", "contacts", "contact_pairs")
        )
        and detail.get("stop_reason") in HARDWARE_PREPARATION_DECLINES
    )
