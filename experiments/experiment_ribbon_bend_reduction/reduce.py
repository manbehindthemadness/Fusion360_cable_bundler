"""
Apply bounded bend-count-reducing rewrites with the unchanged full-volume contact gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from experiments.experiment_ribbon_fold_route.contact import ContactResult, inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .rewrite import Rewrite, reclose, rewrites


@dataclass(frozen=True)
class Trial:
    """
    Retain algebraic infeasibility and every completed contact proposal separately.
    """

    rewrite: Rewrite
    route: FoldRoute | None
    contact: ContactResult | None
    accepted: bool


def reduce_bends(
    route: FoldRoute,
    *,
    checkpoint: Callable[[], None] | None = None,
    record: Callable[[Trial], None] | None = None,
) -> tuple[FoldRoute, str]:
    """
    Accept the first valid largest reduction, at most24proposals/three passes.

    Order is fixed by fold reduction and route position, with no length ranking,
    stochastic seeds or numerical angle fitting. Each accepted rewrite strictly
    reduces bend count; unsuccessful projections/contact checks preserve the last
    valid route. Exhaustion is not proof of globally minimal bend structure.
    The caller must independently establish the baseline's physical acceptance.
    """
    current = route
    proposals = 0
    for _ in range(3):
        for rewrite in rewrites(current):
            if proposals >= 24:
                return current, "proposal_budget"
            if checkpoint is not None:
                checkpoint()
            proposals += 1
            candidate = reclose(current, rewrite)
            contact = (
                inspect_contact(candidate, checkpoint=checkpoint) if candidate is not None else None
            )
            accepted = contact is not None and contact.status == "separated"
            if record is not None:
                record(Trial(rewrite, candidate, contact, accepted))
            if accepted:
                if candidate is None:
                    raise ArithmeticError("Accepted rewrite lacks geometry.")
                current = candidate
                break
        else:
            return current, "no_accepted_rewrite"
    return current, "pass_budget"
