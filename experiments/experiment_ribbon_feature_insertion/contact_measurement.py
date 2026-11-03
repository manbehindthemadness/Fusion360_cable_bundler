"""
Keep the temporary pair-budget diagnostic override distinct from normal contact acceptance.
"""

from __future__ import annotations

from enum import Enum

from experiments.experiment_ribbon_fold_route.contact import ContactResult


class ContactPolicy(str, Enum):
    """
    Require separation normally; an explicitly configured gym may retain aborted measurements.
    """

    STRICT = "require_separation"
    LOG_PAIR_LIMIT = "temporary_log_pair_limit"

    def permits_geometry(self, result: ContactResult) -> bool:
        """
        Allow only a separated result or explicitly identified pair-budget exhaustion.

        Penetration, depth/regularity ambiguity and hard source/resource failures
        are never converted into diagnostic geometry permission. The original
        unresolved result must remain attached to any retained route.
        """
        return result.status == "separated" or (
            self is ContactPolicy.LOG_PAIR_LIMIT
            and result.status == "unresolved"
            and result.limit == "pairs"
        )
