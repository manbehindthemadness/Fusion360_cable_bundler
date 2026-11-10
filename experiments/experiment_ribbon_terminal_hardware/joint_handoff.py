"""
Retain a fully closed proposal and its actual blocker without transferring acceptance or work allowances.
"""

from __future__ import annotations

from dataclasses import dataclass

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .check import Report


@dataclass(frozen=True)
class JointHandoff:
    """
    Preserve one immutable closed candidate with demonstrated material or connector intrusion.

    This is rejected geometry, never an accepted result or a renewed solver
    allocation. Incomplete checks cannot invent a material crossing or connector
    witness. The next stage must certify its changed geometry independently.
    """

    route: FoldRoute
    evidence: ContactResult | Report

    def __post_init__(self) -> None:
        """
        Require an existing strict blocker and closed ordered cap positions before yielding control.
        """
        expected = "blocked" if isinstance(self.evidence, Report) else "penetration"
        if self.evidence.status != expected or self.evidence.witness is None:
            raise ValueError("A joint handoff requires demonstrated intrusion")
        if cap_error(self.route) > 1e-7:
            raise ValueError("A joint handoff requires closed ordered caps")
