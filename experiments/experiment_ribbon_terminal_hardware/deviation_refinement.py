"""
Spend unused spatial-deviation work on the shared evidence-driven recovery sequence.
"""

from __future__ import annotations

from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .deviation_sequence import recover
from .gate import Gate
from .recovery_limits import Work


def refine(
    source: FoldRoute,
    contact: ContactResult,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    work: Work,
    maximum_length_mm: float,
    minimum_straight_mm: float,
) -> Result | None:
    """
    Continue one measured deviation with the caller's exact nonrenewable allocation.

    The shared sequence selects coupled material guidance, actual return
    reversals and fixed-bend connector correction from current evidence only.
    Missing evidence or exhausted work never grants another guide or root.
    """
    return recover(
        source,
        contact,
        terminal,
        checkpoint,
        record,
        work=work,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
    )
