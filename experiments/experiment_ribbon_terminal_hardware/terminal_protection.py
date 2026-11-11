"""
Preserve both terminal neighborhoods while material correction compensates fixed caps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from experiments.experiment_ribbon_feature_insertion.separation import Region, Side, locate, regions
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy, cap_region

from .check import mating_frame
from .feature_guidance import member_planes
from .feature_plane import FeaturePlane, SignedJoints
from .model import Hardware, Terminal


@dataclass(frozen=True)
class Protection:
    """
    Restore conservative terminal separation while retaining certified mating-cap contact.
    """

    plane: FeaturePlane
    minimum_gap: float

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
    Require the existing 1e-7mm enclosure separation preference unless the
    original actual mating piece has a complete analytic cap-side certificate.
    That certified touch retains its original gap capped at the same preference.
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
    cell = Cell(
        0,
        Span(0, 1),
        Span(-model.original.half_width_mm, model.original.half_width_mm),
        Span(-model.original.targets.diameter_mm / 2, model.original.targets.diameter_mm / 2),
    )
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
            touching = (
                tags[-1 if at_end else 0] == part.reference
                and mating_frame(model.original, box)
                and cap_region(
                    locate(model.original, model.original.pieces, part.reference),
                    cell,
                    at_end,
                    CapPolicy.ANALYTIC_SUPPORT,
                )
            )
            minimum = 1e-7 / model.scale
            result.append(
                Protection(part, min(part.gap(baseline), minimum) if touching else minimum)
            )
    checkpoint()
    return tuple(result)
