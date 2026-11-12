"""
Preserve both terminal neighborhoods while material correction compensates fixed caps.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from experiments.experiment_ribbon_feature_insertion.separation import Region, Side, regions

from .check import mating_frame
from .feature_guidance import member_planes
from .feature_plane import FeaturePlane, SignedJoints
from .model import Hardware, Terminal


class ProtectionBasis(Enum):
    """
    Distinguish a matched source mating boundary from an ordinary enclosure clearance preference.
    """

    CLEARANCE = "enclosure_clearance"
    MATING_BOUNDARY = "source_mating_boundary"


@dataclass(frozen=True)
class Protection:
    """
    Retain terminal motion preferences without granting any hardware clearance certificate.
    """

    plane: FeaturePlane
    minimum_gap: float
    basis: ProtectionBasis = ProtectionBasis.CLEARANCE

    def residual(self, values: tuple[float, ...]) -> float:
        """
        Evaluate the retained clearance inequality without granting physical acceptance.
        """
        return self.minimum_gap - self.plane.gap(values)


def _covered(observed: list[FeaturePlane]) -> set[tuple[Terminal, Region]]:
    """
    Identify actual member equations that replace a weaker protective preference.
    """
    return {(part.box.terminal, member) for part in observed for member in part.members}


def uncovered(
    protections: tuple[Protection, ...], observed: list[FeaturePlane]
) -> tuple[Protection, ...]:
    """
    Retain other source protections when later witnessed equations take precedence for a member.
    """
    covered = _covered(observed)
    return tuple(
        protection
        for protection in protections
        if (protection.plane.box.terminal, protection.plane.reference) not in covered
    )


def prepare(
    model: SignedJoints,
    hardware: Hardware,
    observed: list[FeaturePlane],
    checkpoint: Callable[[], None],
) -> tuple[Protection, ...]:
    """
    Bind actual terminal folds and occupied inward straight members at the unchanged source.

    Existing witnessed member equations take precedence. Each remaining member
    selects its closest existing SAT family once, with complete width/thickness.
    Require the existing 1e-7mm enclosure separation preference except for the
    exact original mating piece at its actual matched terminal frame. That
    piece shares a point with the hardware's closed mating face, so positive
    whole-member separation would conflict with fixed cap closure. Retain its
    original gap capped at the same preference, even when the entire bend needs
    subdivision rather than a single analytic cap-side proof. This boundary
    allowance supplies no clearance proof and does not extend to other members.
    A negative enclosure gap is not a penetration witness; these conservative
    inequalities cannot establish clearance. Mating straights and absent material are excluded.
    Final complete hardware and self-contact certificates remain mandatory.
    """
    checkpoint()
    if model.original.targets != hardware.targets:
        raise ValueError("Terminal protection requires the same fixed target poses")
    if not model.folds:
        return ()
    baseline = tuple(model.full.initial[index] for index in model.indices)
    tags = regions(model.original)
    occupied = set(tags)
    covered = _covered(observed)
    result: list[Protection] = []
    for box in hardware.boxes:
        ordinal = 0 if box.terminal is Terminal.START else len(model.folds) - 1
        fold = Region(ordinal, False)
        inward = Region(ordinal + 1 if box.terminal is Terminal.START else ordinal, True)
        members = tuple(
            member
            for member in (fold, inward)
            if member in occupied
            and (not member.straight or 0 < member.fold < len(model.folds))
            and (box.terminal, member) not in covered
        )
        if not members:
            continue
        checkpoint()
        prototype = FeaturePlane(model, fold, members, box, 0, Side.BEFORE)
        for part in member_planes([prototype], model, baseline):
            checkpoint()
            at_end = box.terminal is Terminal.END
            touching = tags[-1 if at_end else 0] == part.reference and mating_frame(
                model.original, box
            )
            minimum = 1e-7 / model.scale
            result.append(
                Protection(
                    part,
                    min(part.gap(baseline), minimum) if touching else minimum,
                    ProtectionBasis.MATING_BOUNDARY if touching else ProtectionBasis.CLEARANCE,
                )
            )
    checkpoint()
    return tuple(result)
