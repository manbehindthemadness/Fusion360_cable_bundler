"""
Rebind actual hardware guidance to a larger signed-joint domain before any correction motion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .feature_guidance import ContactGuidance, ContactMotion, member_planes
from .feature_plane import FeaturePlane, SignedJoints
from .model import Hardware


@dataclass(frozen=True)
class HardwareDomain:
    """
    Retain one new coordinate model and the same actual hardware features rebound to it.
    """

    model: SignedJoints
    planes: list[FeaturePlane]
    members: list[FeaturePlane]


def expand(
    source: FoldRoute,
    guidance: ContactGuidance,
    hardware: Hardware,
    checkpoint: Callable[[], None],
) -> HardwareDomain | None:
    """
    Prepare angular/straight mobility at the identical closed material shape without executing a step.

    The caller must first receive no admissible initial straight-projection step,
    preserve its original clocks/counters and replace model-bound caches. Every
    fold sign/radius/profile and ordered cap remains authoritative. Rebinding
    guidance neither measures clearance nor grants another motion allowance.
    """
    checkpoint()
    if guidance.motion is not ContactMotion.ADAPTIVE_HARDWARE:
        raise ValueError("Hardware-domain expansion requires an explicit adaptive policy")
    if cap_error(source) > 1e-7 or material_error(source) > 1e-10:
        raise ArithmeticError("Hardware-domain expansion requires closed material geometry")
    if source.targets != hardware.targets:
        raise ValueError("Hardware-domain expansion must retain the same fixed targets")
    model = SignedJoints(source)
    planes = guidance.planes(model, hardware, model.initial)
    if not planes:
        return None
    members = member_planes(planes, model, model.initial)
    checkpoint()
    if len(members) > 13:
        return None
    return HardwareDomain(model, planes, members)
