"""
Schedule strict contact certificates around bounded affine radius descent.
"""

from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from typing import Any, Callable, Generator

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .radius_descent import Proposal, proposals
from .radius_descent import direction as direction

__all__ = ["ContactSchedule", "direction", "ease"]


def _advance(stream: Generator[Proposal, bool, str], accepted: bool | None) -> Proposal | str:
    """
    Read a proposal or its stop reason without swallowing recorder/checkpoint errors.
    """
    try:
        return next(stream) if accepted is None else stream.send(accepted)
    except StopIteration as stopped:
        return stopped.value


class ContactSchedule(Enum):
    """
    Preserve historical per-step checks alongside deferred final-descent certification.
    """

    PER_STEP = "per_step"
    FINAL_DESCENT = "final_descent"


def ease(
    source: FoldRoute,
    length_growth: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    contact_schedule: ContactSchedule = ContactSchedule.PER_STEP,
) -> tuple[FoldRoute, str]:
    """
    Reduce lane curvature within the original material/peak/length and proposal bounds.

    Per-step mode retains eight contact proposals and halves rejected improvements.
    Deferred mode computes the same bounded mathematical descent first, then checks
    its final proposal and, if necessary, its immediate predecessor. No more than
    two complete certificates are attempted. Failed certification retains the input
    route; intermediate mathematical improvements never imply contact acceptance.
    The caller establishes baseline material/contact acceptance. Errors propagate.
    """
    if not isinstance(contact_schedule, ContactSchedule):
        raise ValueError("Choose an explicit radius contact schedule")
    if cap_error(source) > 1e-7:
        raise ValueError("Aesthetic input must retain the complete ordered caps.")
    stream = proposals(source, length_growth, checkpoint, record)
    current = source
    contacts = 0
    candidates: list[Proposal] = []
    try:
        proposal = _advance(stream, None)
        while isinstance(proposal, Proposal):
            event = proposal.event
            if contact_schedule is ContactSchedule.FINAL_DESCENT:
                record(
                    {
                        **event,
                        "stage": "radius_math",
                        "status": "curvature_improved_contact_unmeasured",
                    }
                )
                candidates.append(proposal)
                accepted = True
            else:
                if contacts >= 8:
                    record({**event, "status": "unattempted_contact_budget"})
                    return current, "contact_proposal_budget"
                record({**event, "status": "contact_started"})
                contact = inspect_contact(proposal.route, checkpoint=checkpoint)
                contacts += 1
                accepted = contact.status == "separated"
                record(
                    {
                        **event,
                        "contact": asdict(contact),
                        "status": "accepted" if accepted else contact.status,
                    }
                )
                if accepted:
                    current = proposal.route
            proposal = _advance(stream, accepted)
        reason = proposal
    finally:
        stream.close()
    if contact_schedule is ContactSchedule.PER_STEP:
        return current, reason
    record({"stage": "radius_math", "status": reason, "proposals": len(candidates)})
    for proposal in reversed(candidates[-2:]):
        checkpoint()
        record({**proposal.event, "stage": "radius_certificate", "status": "contact_started"})
        contact = inspect_contact(proposal.route, checkpoint=checkpoint)
        accepted = contact.status == "separated"
        record(
            {
                **proposal.event,
                "stage": "radius_certificate",
                "contact": asdict(contact),
                "status": "accepted" if accepted else contact.status,
            }
        )
        if accepted:
            return proposal.route, "certified_math_descent"
    return source, "baseline_retained" if candidates else reason
