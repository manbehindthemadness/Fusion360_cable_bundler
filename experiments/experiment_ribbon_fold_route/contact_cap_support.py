"""
Prove additional shared-cap halfspaces from the complete local plane-cylinder-plane map.
"""

from __future__ import annotations

import math
from enum import Enum

from .contact_bounds import Cell, cap_neighborhood
from .geometry import PlacedPiece, Straight


class CapPolicy(Enum):
    """
    Keep historical monotone certification available beside the additional analytic support proof.
    """

    MONOTONE = "monotone"
    ANALYTIC_SUPPORT = "analytic_support"


def cap_region(piece: PlacedPiece, cell: Cell, at_end: bool, policy: CapPolicy) -> bool:
    """
    Certify a cell on its proper cap side without exempting adjacent material wholesale.

    Preserve the original monotonicity proof. The optional support proof treats
    the entry plane exactly, bounds the entire circular part by nonnegative sine,
    and checks every clipped exit-plane vertex at both thickness extremes.
    A conservative positive local guard rejects uncertain extra proofs. No world
    translation cancellation, contact acceptance tolerance or geometric repair.
    """
    if cap_neighborhood(piece, cell, at_end):
        return True
    if policy is CapPolicy.MONOTONE:
        return False
    assert not isinstance(piece.geometry, Straight)
    fold = piece.geometry
    bank = -fold.bank_radians if at_end else fold.bank_radians
    angle = abs(fold.angle_radians)
    sign = math.copysign(1.0, -fold.angle_radians if at_end else fold.angle_radians)
    before = fold.after_mm if at_end else fold.before_mm
    low, high = (1 - cell.u.high, 1 - cell.u.low) if at_end else (cell.u.low, cell.u.high)
    heights = (
        (-cell.height.high, -cell.height.low) if at_end else (cell.height.low, cell.height.high)
    )
    c, s = math.cos(bank), math.sin(bank)
    radius = fold.radius_mm
    if not 0 < angle <= math.pi or c <= 0 or radius <= max(abs(h) for h in heights):
        return False
    scale = 1 + before + fold.material_length_mm
    scale += max(abs(cell.q.low), abs(cell.q.high)) + max(abs(h) for h in heights)
    guard = 1e-11 * scale
    # For the circular part, X=before-q*tan(bank)+cos(bank)*rho*sin(phase)
    # +sin(bank)^2*xi/cos(bank). Each term after the first pair is nonnegative.
    if before - max(s / c * cell.q.low, s / c * cell.q.high) <= guard:
        return False
    points = tuple(
        (u * fold.material_length_mm - before, q)
        for u, q in (
            (low, cell.q.low),
            (high, cell.q.low),
            (high, cell.q.high),
            (low, cell.q.high),
        )
    )
    arc = radius * angle
    vertices: list[tuple[float, float]] = []
    for a, b in zip(points, points[1:] + points[:1]):
        xa, xb = c * a[0] + s * a[1], c * b[0] + s * b[1]
        if xa >= arc:
            vertices.append(a)
        if xa < arc < xb or xb < arc < xa:
            fraction = (arc - xa) / (xb - xa)
            vertices.append((a[0] + fraction * (b[0] - a[0]), a[1] + fraction * (b[1] - a[1])))
    sine, cosine = math.sin(angle), math.cos(angle)
    for along, q in vertices:
        xi, eta = c * along + s * q, -s * along + c * q
        for height in heights:
            x = before + c * ((radius - sign * height) * sine + (xi - arc) * cosine) - s * eta
            if x <= guard:
                return False
    return True
