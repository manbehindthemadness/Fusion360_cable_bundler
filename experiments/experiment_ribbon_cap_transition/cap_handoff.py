"""
Share solved cap-frame objects with a private native harness, without moving guides.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from cable_bundler.routing.geometry import difference, magnitude
from experiments.experiment_secure_discrete_ribbon.bank import bank_ribbon_frames
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame


@dataclass
class CapFrameHandoff:
    """
    Retain the harness frame container and adopt only equivalent solved endpoints.

    A 1e-12 mm/component-vector equivalence check permits floating-point identity
    differences, not geometry repair. The frozen EndPlan guard remains exact:
    planning and construction subsequently receive the same solved frame objects.
    No conductor centers, guide planes, interior nodes or connection targets move.
    """

    frames: list[RibbonFrame] = field(default_factory=list)

    def bank(
        self, frames: tuple[RibbonFrame, ...], lines: int, diameter_mm: float
    ) -> list[RibbonFrame]:
        """
        Perform the unchanged fixture banking once and retain its shared container.
        """
        if self.frames:
            raise RuntimeError("Cap handoff already bound; no repeated preparation.")
        self.frames = list(bank_ribbon_frames(frames, lines, diameter_mm))
        return self.frames

    def adopt(self, solved: tuple[RibbonFrame, ...]) -> None:
        """
        Validate both caps before atomically replacing either endpoint reference.

        Reject missing frames, nonfinite components and meaningful displacement or
        rotation. Interior harness frames are left alone; the trunk uses solved
        shape frames directly. This does not certify skin tangency or curvature.
        """
        if len(self.frames) < 2 or len(solved) < 2:
            raise ValueError("Cap handoff requires bound and solved endpoint frames.")
        for index in (0, -1):
            old, new = self.frames[index], solved[index]
            for name in ("origin", "tangent", "width", "thickness"):
                before, after = getattr(old, name), getattr(new, name)
                if (
                    any(
                        not math.isfinite(value)
                        for vector in (before, after)
                        for value in (vector.x, vector.y, vector.z)
                    )
                    or magnitude(difference(before, after)) > 1e-12
                ):
                    raise ValueError("Solved cap differs from the fixed native guide frame.")
        self.frames[0], self.frames[-1] = solved[0], solved[-1]
