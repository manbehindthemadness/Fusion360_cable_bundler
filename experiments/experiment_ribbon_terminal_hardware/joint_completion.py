"""
Share immutable material readiness before ordinary or stalled final certification.
"""

from __future__ import annotations

import math

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight

from .feature_plane import SignedJoints


def closed_material(
    route: FoldRoute, model: SignedJoints, *, length_ceiling_mm: float | None
) -> bool:
    """
    Require the original ordered-cap, material and model-identity contracts before physical proof.

    An absent ceiling denotes the existing released quality goal, never a new
    growth allowance. Nonfinite measurements fail closed. This grants no native
    slot, contact or hardware certificate and performs no geometry correction.
    """
    if route.targets != model.original.targets or not model.preserves(route):
        return False
    length = route.material_length_mm
    if not math.isfinite(length) or (
        length_ceiling_mm is not None
        and (not math.isfinite(length_ceiling_mm) or length > length_ceiling_mm)
    ):
        return False
    caps = cap_error(route)
    if not math.isfinite(caps) or caps > 1e-7:
        return False
    material = material_error(route)
    return math.isfinite(material) and material <= 1e-10


def stalled_certificate_ready(
    route: FoldRoute,
    model: SignedJoints,
    residual: tuple[float, ...],
    *,
    length_ceiling_mm: float | None,
    minimum_straight_mm: float,
) -> bool:
    """
    Permit one unchanged closed shape to request actual proof after accepted motion.

    Finite guidance may remain unsatisfied; only the actual strict certificates
    can resolve that question. The caller must have accepted a correction and
    retained its original allowance and prevented any subsequent motion or
    constraint insertion in this stage. An angular/reflected owner may request
    this after ordinary negative discovery at actual material readiness; other
    owners retain their existing descent/projection decline trigger.
    Native slivers are ineligible: this final request cannot reclose or extend
    them. Absent slots are not material pieces and need no artificial runway.
    """
    return (
        len(residual) >= 6
        and all(math.isfinite(term) for term in residual)
        and math.isfinite(minimum_straight_mm)
        and minimum_straight_mm >= 0
        and closed_material(route, model, length_ceiling_mm=length_ceiling_mm)
        and all(
            piece.geometry.material_length_mm > minimum_straight_mm
            for piece in route.pieces
            if isinstance(piece.geometry, Straight)
        )
    )
