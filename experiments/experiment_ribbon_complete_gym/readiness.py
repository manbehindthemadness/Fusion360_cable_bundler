"""
Keep sampled native-support proximity advisory without granting physical acceptance.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from artifacts.verification.resume3148.admission import Policy, Scope
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute


class ConstructionReadiness(Policy):
    """
    Preserve the inherited risk measurement while allowing unchanged routes onward.

    Support proximity is a sampled construction-risk indicator, not a necessary
    native failure or a physical collision. Actual construction, topology and
    material correspondence retain their separate checks. Measurement, recorder
    and resource exceptions propagate; no geometry, clocks or budgets change.
    """

    def accepts(
        self,
        route: FoldRoute,
        checkpoint: Callable[[], None],
        record: Callable[[dict[str, Any]], None],
        scope: Scope,
    ) -> bool:
        """
        Retain each original proximity witness as a warning, never a route veto.

        This return permits only numerical proposal admission. It establishes
        neither native construction nor an invertible texture/material map.
        """

        def warn(event: dict[str, Any]) -> None:
            """
            Preserve raw risk values and distinguish the superseded screen verdict.
            """
            record(
                {
                    **event,
                    "screen_status": event["status"],
                    "status": "construction_warning",
                    "claim": "Sampled support proximity; native construction and material correspondence remain unverified",
                }
            )

        super().accepts(route, checkpoint, warn, scope)
        return True
