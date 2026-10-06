"""
Bind explicit experimental sphere policy without modifying the shared auditor.
"""

from __future__ import annotations

from functools import partial
from types import ModuleType

from experiments.experiment_secure_discrete_ribbon.cases import audit_end_boundary


def bind_sphere_policy(harness: ModuleType, diameter_widths: float) -> None:
    """
    Supply the approved diameter multiplier to one private harness instance.

    The original auditor still validates size, finiteness and full guide
    containment. Its default and all other module instances remain untouched.
    """
    harness.audit_end_boundary = partial(audit_end_boundary, diameter_widths=diameter_widths)
