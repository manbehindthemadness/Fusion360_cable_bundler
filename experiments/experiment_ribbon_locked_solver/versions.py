"""
Declare the two gym solver methods while keeping archived v1 identities meaningful.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .settings import VERSION, Settings

V2 = "guide-material-v2"
DEFAULT_VERSION = V2


@dataclass(frozen=True)
class Method:
    """
    Bind an explicit solver identity to its public defaults and diagnostic explanation.
    """

    identifier: str
    label: str
    source: str
    defaults: Settings
    scope: str
    optimization_detail: str

    def payload(self) -> dict[str, Any]:
        """
        Advertise controls without importing numerical or native construction modules.
        """
        return {
            "id": self.identifier,
            "label": self.label,
            "settings": asdict(self.defaults),
            "scope": self.scope,
            "optimization_detail": self.optimization_detail,
        }


METHODS = (
    Method(
        V2,
        "Material solver v2",
        "experiments/experiment_ribbon_locked_solver/solver_v2.py",
        Settings(0, False, True),
        "Guide-directed tight folds with bounded existing-bend contraction. Smoothing is optional; full physical compliance remains unverified.",
        "Shorten the route by relocating existing bends and straightaways before smoothing. Keep the original safe route if no shorter replacement passes contact.",
    ),
    Method(
        VERSION,
        "Material solver v1",
        "experiments/experiment_ribbon_locked_solver/solver.py",
        Settings(),
        "Original joint construction with optional aesthetic smoothing and material coordinates; full physical compliance remains unverified.",
        "Shorten the coarse route by adjusting bends and straightaways together, independently of aesthetic smoothing.",
    ),
)


def method(identifier: Any) -> Method:
    """
    Reject unknown or malformed identities before creating jobs or selecting implementations.
    """
    if isinstance(identifier, str):
        for entry in METHODS:
            if entry.identifier == identifier:
                return entry
    raise ValueError("Choose material solver v1 or v2")
