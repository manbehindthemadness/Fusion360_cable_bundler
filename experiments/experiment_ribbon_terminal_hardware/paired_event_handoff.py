"""
Admit witnessed paired material returns using only the adaptive parent's remaining work.
"""

from __future__ import annotations

from typing import Any, Callable

from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_paired_return.factors import bracket
from experiments.experiment_ribbon_paired_return.sequence import Result
from experiments.experiment_ribbon_paired_return.sequence import recover as recover_pair

from .check import Report
from .gate import Gate
from .joint_handoff import JointHandoff
from .recovery_limits import Work


def recover(
    source: FoldRoute,
    evidence: ContactResult,
    hardware_evidence: Report | None,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    work: Work,
    maximum_roots: int,
    minimum_straight_mm: float,
    on_event_refinement: Callable[[JointHandoff], None] | None = None,
) -> Result | None:
    """
    Decline unsupported current witnesses before starting any child action or root derivation.

    Admission only revalidates the already measured occupied point, not a new
    pair search or clearance proof. Its preparation shares the parent's clocks.
    An admitted child charges its own witness admission and all subsequent work;
    the caller must absorb every counter even if it fails. Coexisting hardware
    retains its actual source pose and complete member guidance.
    """
    if (
        maximum_roots < 2
        or evidence.status != "penetration"
        or evidence.witness is None
        or evidence.limit is not None
    ):
        return None
    checkpoint()
    if bracket(source, evidence.witness) is None:
        return None
    checkpoint()
    return recover_pair(
        source,
        evidence,
        terminal,
        checkpoint,
        record,
        work=work,
        maximum_roots=maximum_roots,
        minimum_straight_mm=minimum_straight_mm,
        hardware_evidence=hardware_evidence,
        on_event_refinement=on_event_refinement,
    )
