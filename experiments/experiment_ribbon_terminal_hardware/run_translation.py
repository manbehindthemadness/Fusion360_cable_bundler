"""
Translate an actually blocked feature by redistributing original straight lengths with fixed bends.
"""

from __future__ import annotations

from functools import cached_property
from typing import Callable

from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .check import Report
from .feature_guidance import member_planes
from .feature_plane import FeaturePlane, SignedJoints
from .joint_derivatives import jacobian
from .model import Hardware
from .straight_projection import shortest_run_step


class StraightSlots(SignedJoints):
    """
    Free only original runway coordinates, including absent slots; preserve every bend parameter.
    """

    @cached_property
    def indices(self) -> tuple[int, ...]:
        """
        Exclude all bend angles, banks and radii from the existing material model.
        """
        return tuple(i for i in range(len(self.full.initial)) if i % 4 == 0)


def translate(
    source: FoldRoute, evidence: Report, hardware: Hardware, checkpoint: Callable[[], None]
) -> FoldRoute | None:
    """
    Select one linear cap/member-clearance correction without changing bend geometry or targets.

    Return no proposal for unsupported actual evidence, unresolved algebra or
    invalid coordinates. A returned route is not certified: the caller must
    charge one unused logical update and enforce caps, material, native minimum,
    complete self-contact and both terminal boxes within its original allowance.
    Length may grow to restore invalid hardware geometry; no shortening is claimed.
    """
    model = StraightSlots(source)
    values = model.initial
    plane = FeaturePlane.create(model, source, evidence, hardware, values)
    if plane is None:
        return None
    parts = member_planes([plane], model, values)

    def equations(coordinates: tuple[float, ...]) -> tuple[float, ...]:
        """
        Preserve the ordered caps and each actual feature member's own separating halfspace.
        """
        return model.residual(coordinates) + tuple(
            1e-7 / model.scale - part.gap(coordinates) for part in parts
        )

    residual = equations(values)
    matrix = jacobian(
        model, values, equations, len(residual), set(), checkpoint, admissible=model.admissible
    )
    delta = shortest_run_step(model, values, matrix, residual, checkpoint)
    if delta is None:
        return None
    trial = tuple(a + b for a, b in zip(values, delta))
    return model.route(trial) if model.admissible(trial) else None
