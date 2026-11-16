"""
Certify captured filled rational sections inside the existing clipped-disk positive-support model.

This authorizes only enclosing profile support. It does not transfer analytic
fold maps, negative witnesses, inverse membership or contact acceptance.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, multiply
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import ProfileArc, profile_arcs
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc


@dataclass(frozen=True)
class ProfileSupportCover:
    """
    Keep original section ownership and each whole rational-arc disk witness.
    """

    arcs: tuple[MaterialArc, ...]
    lines: int
    diameter_mm: float
    padding_mm: Fraction
    disk_indices: tuple[int, ...]
    status: str


def covered(arc: MaterialArc, sign: int, disk: ProfileArc, padding: Fraction) -> bool:
    """
    Enclose a complete graph arc and every vertical segment from its boundary to b=0.

    Positive rational weights preserve q control bounds. The implicit circle
    numerator is a degree4 Bernstein polynomial; nonpositive coefficients prove
    whole-curve containment in the SAME padded disk used by the support kernel.
    Both b=0 endpoints are in that convex disk, so the entire q interval's
    baseline and its vertical fill to the graph remain inside too.
    """
    q = tuple(Fraction(p[0]) for p in arc.controls)
    b = tuple(sign * Fraction(p[1]) for p in arc.controls)
    w = tuple(Fraction(x) for x in arc.weights)
    cx, cy, radius = (
        Fraction(disk.center_q),
        Fraction(disk.center_height),
        Fraction(disk.radius) + padding,
    )
    if min(q) < Fraction(disk.low_q) - padding or max(q) > Fraction(disk.high_q) + padding:
        return False
    if any((x - cx) ** 2 + cy**2 > radius**2 for x in (min(q), max(q))):
        return False
    x = tuple((value - cx) * weight for value, weight in zip(q, w))
    y = tuple((value - cy) * weight for value, weight in zip(b, w))
    residual = add(add(multiply(x, x), multiply(y, y)), multiply(w, w), -(radius**2))
    return max(residual) <= Fraction(0)


def certify(
    arcs: tuple[MaterialArc, ...], lines: int, diameter_mm: float, checkpoint: Callable[[], None]
) -> ProfileSupportCover:
    """
    Prove upper/lower graph coverage and padded-disk containment before reusing clipped profile support.

    Unknown shapes remain unresolved. Closed endpoints, monotone q controls and
    one tiled interval per half prevent substituting a disconnected boundary or
    loop for the filled section. The1e-12*diameter padding is the old kernel's
    outward numerical enclosure, not a new physical accuracy requirement.
    """
    checkpoint()
    disks = profile_arcs(lines, diameter_mm)
    padding = Fraction(math.nextafter(1e-12 * diameter_mm, math.inf))
    if (
        not arcs
        or len({arc.label for arc in arcs}) != len(arcs)
        or any(
            len(arc.controls) != 3
            or len(arc.weights) != 3
            or any(len(p) != 2 for p in arc.controls)
            for arc in arcs
        )
        or any(
            type(x) not in (int, float, Fraction) or not math.isfinite(x)
            for arc in arcs
            for x in arc.weights + tuple(x for p in arc.controls for x in p)
        )
        or any(w <= 0 for arc in arcs for w in arc.weights)
    ):
        raise ValueError("Complete finite original positive-weight rational profile required")
    if any(a.controls[-1] != b.controls[0] for a, b in zip(arcs, arcs[1:] + arcs[:1])):
        return ProfileSupportCover(arcs, lines, diameter_mm, padding, (), "unresolved_open_outline")
    bands: dict[int, list[tuple[Fraction, Fraction]]] = {1: [], -1: []}
    choices = []
    for arc in arcs:
        checkpoint()
        q = tuple(Fraction(p[0]) for p in arc.controls)
        b = tuple(Fraction(p[1]) for p in arc.controls)
        sign = 1 if min(b) >= 0 and max(b) > 0 else -1 if max(b) <= 0 and min(b) < 0 else 0
        if not sign or not (q[0] <= q[1] <= q[2] or q[0] >= q[1] >= q[2]) or q[0] == q[2]:
            return ProfileSupportCover(
                arcs, lines, diameter_mm, padding, tuple(choices), "unresolved_non_graph_outline"
            )
        bands[sign].append((min(q[0], q[2]), max(q[0], q[2])))
        candidates = [i for i, disk in enumerate(disks) if covered(arc, sign, disk, padding)]
        if not candidates:
            return ProfileSupportCover(
                arcs, lines, diameter_mm, padding, tuple(choices), "unresolved_disk_cover"
            )
        choices.append(candidates[0])
    upper, lower = sorted(bands[1]), sorted(bands[-1])
    if not upper or upper != lower or any(a[1] != b[0] for a, b in zip(upper, upper[1:])):
        return ProfileSupportCover(
            arcs, lines, diameter_mm, padding, tuple(choices), "unresolved_graph_coverage"
        )
    return ProfileSupportCover(
        arcs, lines, diameter_mm, padding, tuple(choices), "certified_positive_support_cover"
    )
