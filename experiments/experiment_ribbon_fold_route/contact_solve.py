"""
Apply bounded contact-driven runway corrections without accepting unchecked geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .contact import ContactResult, inspect_contact
from .geometry import FoldRoute


@dataclass(frozen=True)
class ContactTrial:
    """
    Retain each candidate before analysis and its completed contact disposition.
    """

    index: int
    runway_mm: float
    route: FoldRoute
    report: ContactResult | None


class SelfContactError(ValueError):
    """
    Preserve rejected geometry/history without claiming the endpoint layout impossible.
    """

    def __init__(self, history: tuple[ContactTrial, ...]) -> None:
        """
        Retain every completed correction for diagnostics and recovery.
        """
        last = history[-1]
        super().__init__(
            f"Ribbon self-contact {last.report.status if last.report else 'unresolved'}; bounded correction exhausted."
        )
        self.route = last.route
        self.report = last.report
        self.history = history


def resolve_contact(
    build: Callable[[float], FoldRoute],
    runway_step_mm: float,
    *,
    maximum_corrections: int,
    maximum_pairs: int,
    maximum_depth: int,
    checkpoint: Callable[[], None] | None,
    record: Callable[[ContactTrial], None] | None,
) -> FoldRoute:
    """
    Extend fold runways only after an actual contact check rejects the current path.

    One correction advances by the full nominal width+thickness support span.
    This is a bounded geometric repair, not proof that this spacing must clear.
    Recomputed closure preserves targets; every changed path is independently
    checked. Unresolved checks never pass and exhaustion never proves impossibility.
    """
    if (
        isinstance(maximum_corrections, bool)
        or not isinstance(maximum_corrections, int)
        or not 0 <= maximum_corrections <= 8
    ):
        raise ValueError("Use0..8bounded runway corrections.")
    history = []
    for index in range(maximum_corrections + 1):
        if checkpoint is not None:
            checkpoint()
        runway = index * runway_step_mm
        route = build(runway)
        if record is not None:
            record(ContactTrial(index, runway, route, None))
        report = inspect_contact(
            route, maximum_pairs=maximum_pairs, maximum_depth=maximum_depth, checkpoint=checkpoint
        )
        trial = ContactTrial(index, runway, route, report)
        history.append(trial)
        if record is not None:
            record(trial)
        if report.status == "separated":
            return route
    raise SelfContactError(tuple(history))
