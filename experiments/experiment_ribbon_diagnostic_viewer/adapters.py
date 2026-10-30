"""
Reject the former diagnostic search dispatch without importing historical solvers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from devtools.ribbon_analysis.contracts import RibbonPath

from .procedures import selections

if TYPE_CHECKING:
    from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase


def execute(
    identifier: str, case: EndpointCase, settings: dict[str, Any], checkpoint: Callable[[], None]
) -> tuple[RibbonPath | None, dict[str, Any]]:
    """
    Reject stale direct calls before any seed, transport or fitting work can run.
    """
    del case, checkpoint
    selections([{"id": identifier, "settings": settings}])
    raise AssertionError("Discovery selection unexpectedly succeeded.")
