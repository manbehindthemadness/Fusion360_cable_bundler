"""
Recover approximate canonical bend coordinates with exact residual and conditional coordinate bounds.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .exact_frame import invert
from .material_inverse import solve
from .ruled_support import square_root_upper
from .volume_field import BendVolume, Point
from .volume_injectivity import GlobalBendProof


@dataclass(frozen=True)
class BendInverse:
    """
    Retain same-source approximate labels without claiming native or exact image membership.

    The material error bound applies only IF the target lies in this canonical
    volume image. Domain, profile membership, native correspondence and contact
    remain separate. An unresolved receipt may retain a last numerical proposal.
    """

    volume: BendVolume
    proof: GlobalBendProof
    coordinates: Point
    material_coordinates: Point
    residual_upper_mm: Fraction
    material_error_upper_if_in_image_mm: Fraction
    status: str


def _proposal(volume: BendVolume, target: Point) -> tuple[float, float, float]:
    """
    Use the analytic reference only to choose one Newton start, never to authorize coordinates.
    """
    frame = invert(volume.columns)
    if frame.rows is None:
        raise ValueError("A nonsingular original reference frame required")
    delta = tuple(
        t - o - f * volume.before_mm for t, o, f in zip(target, volume.origin, volume.forward)
    )
    x, eta, z = (float(sum((a * b for a, b in zip(row, delta)), Fraction(0))) for row in frame.rows)
    radius, c, s = float(volume.radius_mm), float(volume.cosine), float(volume.sine)
    radial = radius - volume.sign * z
    principal = math.atan2(x, radial)
    low, high = map(
        float, (volume.source.surface.basis.breaks[0], volume.source.surface.basis.breaks[-1])
    )
    phase = min(
        (principal, principal + math.tau, principal - math.tau),
        key=lambda u: max(low - u, 0.0, u - high),
    )
    phase = min(high, max(low, phase))
    return phase, c * eta + radius * phase * s, volume.sign * (radius - math.hypot(x, radial))


def recover(
    volume: BendVolume,
    proof: GlobalBendProof,
    target: Point,
    take_step: Callable[[], None],
    checkpoint: Callable[[], None],
) -> BendInverse:
    """
    Make at most six caller-debited Newton corrections on the SAME captured volume.

    The caller owns root/CPU/time allocations, including recovery0.4CPU/2wall/
    24Newton when applicable. No fallback start, renewal or independent pool is
    introduced. Clipping changes numerical proposals only, never geometry.
    Each accepted proposal is in the original phase/q/b box and has exact L1
    world residual and conditional physical s/q/b error within one0.01mm allowance.

    Global separation in (R*phase,q,b) bounds coordinate error by residual/lower.
    The exact affine conversion to physical material distance s adds its safe
    Frobenius norm. A tighter residual may therefore be needed for coordinate
    validity; it is not a tighter physical dimensional acceptance rule.
    """
    checkpoint()
    if len(target) != 3 or any(type(x) is not Fraction for x in target):
        raise ValueError("Three exact finite world coordinates required")
    if (
        proof.volume is not volume
        or proof.status != "certified_bend_global_injectivity"
        or proof.separation_lower is None
        or proof.separation_lower <= 0
        or len(proof.spans) != len(volume.source.spans)
        or tuple(s.index for s in proof.spans) != tuple(range(len(volume.source.spans)))
    ):
        raise ValueError("A complete global proof of the SAME original canonical bend required")
    try:
        proposed = _proposal(volume, target)
    except OverflowError as error:
        raise ValueError("Target/reference exceeds numerical proposal range") from error
    if not all(math.isfinite(x) for x in proposed):
        raise ValueError("Target/reference exceeds numerical proposal range")
    breaks = volume.source.surface.basis.breaks
    limits = (
        (breaks[0], breaks[-1]),
        (-volume.source.half_mm, volume.source.half_mm),
        (-volume.half_thickness_mm, volume.half_thickness_mm),
    )
    multiplier = (
        square_root_upper(2 + (1 + volume.sine**2) / volume.cosine**2) / proof.separation_lower
    )

    def coordinates(values: tuple[float, ...]) -> Point:
        """
        Clip exact representations to original domains, including nonbinary rational endpoints.
        """
        return tuple(min(high, max(low, Fraction(x))) for x, (low, high) in zip(values, limits))

    current = coordinates(proposed)
    for iteration in range(7):
        checkpoint()
        jet = volume.jet(*current)
        residual = tuple(a - t for a, t in zip(jet.point, target))
        upper = sum(map(abs, residual), Fraction(0))
        coordinate_upper = multiplier * upper
        material = (
            (volume.radius_mm * current[0] - volume.sine * current[1]) / volume.cosine
            + volume.before_mm,
            current[1],
            current[2],
        )
        accepted = max(upper, coordinate_upper) <= Fraction(1, 100)
        result = BendInverse(
            volume,
            proof,
            current,
            material,
            upper,
            coordinate_upper,
            "within_dimensional_tolerance" if accepted else "unresolved",
        )
        if accepted or iteration == 6:
            return result
        take_step()
        correction = solve(
            tuple(tuple(float(x) for x in column) for column in jet.columns),
            tuple(float(x) for x in residual),
        )
        if correction is None:
            return result
        proposed = tuple(float(x) - d for x, d in zip(current, correction))
        if not all(math.isfinite(x) for x in proposed):
            return result
        current = coordinates(proposed)
    raise RuntimeError("Bounded Newton traversal must return a final receipt")
