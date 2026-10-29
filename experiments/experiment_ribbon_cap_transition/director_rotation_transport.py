"""
Adapt constant-material-speed fields to shared unit-rotation transport.

Historical fields retain their original normalized material-length parameter.
"""

from __future__ import annotations

from typing import Callable

from devtools.ribbon_analysis.inspection.capture import transported

from .director_fields import DirectorField
from .director_motion_transport import DirectorMotion, integrate_motion
from .director_transport import INITIAL, DirectorPath, State


def integrate_rotation(
    field: DirectorField, steps: int, checkpoint: Callable[[], None], *, initial: State = INITIAL
) -> DirectorPath:
    """
    Integrate the same intrinsic fields with structural unit director axes.

    Same grids/checkpoints and dense-output contract as the historical adapter.
    This remains constant material speed;variable-progress fields use an explicit
    motion callback and a separately typed path.
    """

    def motion(u: float) -> DirectorMotion:
        """
        Preserve the historical curvature-to-normalized-turn conversion exactly.
        """
        k, eta, _ = field.sample(u)
        return DirectorMotion(field.length_mm, k * field.length_mm, eta)

    states, rates = integrate_motion(motion, steps, checkpoint, initial=initial)
    path = DirectorPath(field, states, rates)
    transported(path, steps)
    return path
