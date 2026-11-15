"""
Expose non-cap flat material that a permanently touching terminal support can hide.
"""

from __future__ import annotations

from dataclasses import dataclass

from cable_bundler.routing.geometry import dot
from experiments.experiment_ribbon_feature_insertion.separation import locate
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase

from .flat_separation import FlatPart, flat_span
from .model import Terminal
from .terminal_protection import Protection, ProtectionBasis


@dataclass(frozen=True)
class MatingPhase:
    """
    Add complete opposite-flat guidance alongside the unchanged whole-member protection.

    A fixed mating cap can dominate the whole-member minimum at zero while the
    other flat approaches that halfspace. Its separate bound supplies usable
    slack and derivatives before intrusion. Neither row certifies clearance;
    full hardware and material checks remain mandatory.
    """

    protection: Protection
    part: FlatPart

    @classmethod
    def create(cls, protection: Protection) -> MatingPhase | None:
        """
        Bind only the opposite flat of an actual source-mating terminal fold.
        """
        plane = protection.plane
        ordinal = 0 if plane.box.terminal is Terminal.START else len(plane.model.folds) - 1
        if (
            protection.basis is not ProtectionBasis.MATING_BOUNDARY
            or plane.reference.straight
            or plane.reference.fold != ordinal
            or plane.members != (plane.reference,)
        ):
            return None
        source = plane.model.original
        part = FlatPart(
            FlatPhase.AFTER if plane.box.terminal is Terminal.START else FlatPhase.BEFORE,
            -source.half_width_mm,
            source.half_width_mm,
            source.targets.diameter_mm / 2,
        )
        return cls(protection, part)

    def __call__(self, values: tuple[float, ...]) -> float:
        """
        Retain the same hardware axis, full width/thickness and original physical gap.
        """
        plane = self.protection.plane
        piece = locate(plane.model.original, plane.model.pieces(values), plane.reference)
        axis = plane.separation_direction(values)
        low, _ = flat_span(piece, self.part, axis)
        gap = (low - max(dot(corner, axis) for corner in plane.corners)) / plane.model.scale
        return self.protection.minimum_gap - gap
