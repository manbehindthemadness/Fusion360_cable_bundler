"""
Prove positive entry/arc support while allowing zero distance only at the shared material cap.

In cap-local coordinates m=D+r*phi/c and X=D+c*rho*sin(phi)+s*s*r*phi/c,
where c=cos(bank)>0, D=before-q*tan(bank)>=0 and rho=r-sign*height>0.
For0<=phi<=angle<=pi, sinc(phi)>=sinc(angle)>=0. Thus X>=min(1,K)*m,
K=s*s+c*c*(1-max_height/r)*sinc(angle). A guarded positive K proves strict
interior support for m>0; m=0 remains a legitimate shared boundary. Exit-plane
material is outside this predicate and still requires its original guarded proof.
"""

from __future__ import annotations

import math

from devtools.ribbon_analysis.isometric_fold import CylindricalFold

from .contact_bounds import Cell
from .geometry import PlacedPiece


def entry_arc_supported(piece: PlacedPiece, cell: Cell, at_end: bool) -> bool:
    """
    Certify analytic entry/arc interiors for one physical-width, regular material cell.

    Retain the constructor's flat-cap domain and decline custom surface dispatch,
    nonfinite/outside cells, nonregular thickness and a numerically zero factor.
    The factor guard is dimensionless and invariant under uniform physical scale.
    Like the original monotone proof this concerns the analytic material map;
    native representation and actual hardware remain separate measured contracts.
    """
    if type(piece) is not PlacedPiece or type(piece.geometry) is not CylindricalFold:
        return False
    fold = piece.geometry
    coordinates = (
        cell.u.low,
        cell.u.high,
        cell.q.low,
        cell.q.high,
        cell.height.low,
        cell.height.high,
    )
    if any(not math.isfinite(value) for value in coordinates):
        return False
    low, high = (1 - cell.u.high, 1 - cell.u.low) if at_end else (cell.u.low, cell.u.high)
    maximum_height = max(abs(cell.height.low), abs(cell.height.high))
    bank = -fold.bank_radians if at_end else fold.bank_radians
    before = fold.after_mm if at_end else fold.before_mm
    angle, radius = abs(fold.angle_radians), fold.radius_mm
    c, s = math.cos(bank), math.sin(bank)
    if not (
        0 <= low <= high <= 1
        and -fold.width_mm / 2 <= cell.q.low <= cell.q.high <= fold.width_mm / 2
        and cell.height.low <= cell.height.high
        and 0 < angle <= math.pi
        and c > 0
        and radius > maximum_height
        and before >= fold.width_mm / 2 * abs(math.tan(bank))
    ):
        return False
    sinc = (
        0.0
        if angle == math.pi
        else max(0.0, math.nextafter((math.sin(angle) - 2e-15) / angle, -math.inf))
    )
    rho = max(0.0, math.nextafter(1 - math.nextafter(maximum_height / radius, math.inf), -math.inf))
    c2 = max(0.0, math.nextafter(c * c, -math.inf) - 2e-15)
    s2 = max(0.0, math.nextafter(s * s, -math.inf) - 2e-15)
    curved = math.nextafter(math.nextafter(c2 * rho, -math.inf) * sinc, -math.inf)
    factor = math.nextafter(s2 + curved, -math.inf)
    return math.isfinite(factor) and factor > 1e-11
