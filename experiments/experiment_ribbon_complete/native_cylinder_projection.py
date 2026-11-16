"""
Prove global original physical-coordinate projection on actual cylinder faces from whole-face enclosures.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction

from .cylinder_enclosure import NativeFaceBox
from .flat_cut_domain import FlatCutFrame

Interval = tuple[Fraction, Fraction]


def _ranges(
    frame: FlatCutFrame, box: NativeFaceBox, checkpoint: Callable[[], None]
) -> tuple[Interval, ...]:
    """
    Enclose each exact affine derivative of the native cylinder quadric on the entire owned box.
    """
    native = box.native
    corners = box.corners()
    result = []
    for column in frame.columns:
        checkpoint()
        radial = native.radial(column)
        values = tuple(
            2 * sum((a * (p - o) for a, p, o in zip(radial, point, native.origin)), Fraction(0))
            for point in corners
        )
        result.append((min(values), max(values)))
    return tuple(result)


@dataclass(frozen=True)
class ActualCylinderProjection:
    """
    Certify original (s,q) projection injectivity and conditioning on an actual native face.

    F(X)=|P(X-nativeOrigin)|²-R² vanishes on the native cylinder. Its derivative
    with respect to original physical b is affine in world X. Every enclosing
    box is convex, so their intersection contains the entire chord between any
    two actual face points. A common strict sign for F_b on that intersection
    makes two different b values at the SAME (s,q) impossible by the mean-value
    theorem. This proves injectivity on the actual face, independently of UV,
    converted surfaces, trimmed-loop closure, holes and source-profile conics.

    The same integrated identity gives |delta b| <= (M_s*|delta s|+
    M_q*|delta q|)/m. Original frame columns transfer this to a global world L1
    inverse bound; the original affine decoder supplies the forward bound.
    Their product must satisfy the existing numerical condition ceiling 1024.
    This is an inverse onto the actual projection image, not proof of coverage
    of the original material domain, isometry, paths or whole-output compliance.
    SDK actual-face enclosure and analytic-support contracts remain premises.
    """

    frame: FlatCutFrame
    boxes: tuple[NativeFaceBox, ...]
    checkpoint: InitVar[Callable[[], None]]
    derivative_intervals: tuple[Interval, ...] = field(init=False)
    branch_sign: int = field(init=False)
    branch_lower: Fraction | None = field(init=False)
    graph_partial_bounds: tuple[Fraction, Fraction] | None = field(init=False)
    inverse_world_lipschitz: Fraction | None = field(init=False)
    decoder_lipschitz: Fraction = field(init=False)
    condition_upper: Fraction | None = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Require identical native owners and intersect only bounds valid over every whole-face enclosure.
        """
        checkpoint()
        if not self.boxes:
            raise ValueError("A nonempty actual native face enclosure set required")
        first = self.boxes[0]
        if self.frame.region.value != first.native.region or any(
            box.native is not first.native or box.face_token != first.face_token
            for box in self.boxes
        ):
            raise ValueError("The SAME actual native face/token and original region required")
        ranges = tuple(_ranges(self.frame, box, checkpoint) for box in self.boxes)
        intervals = tuple(
            (max(row[k][0] for row in ranges), min(row[k][1] for row in ranges)) for k in range(3)
        )
        if any(low > high for low, high in intervals):
            raise ValueError("Consistent enclosures of one nonempty actual native face required")
        low, high = intervals[2]
        sign = 1 if low > 0 else -1 if high < 0 else 0
        lower = low if sign == 1 else -high if sign == -1 else None
        partials = None
        inverse_bound = None
        condition = None
        rows = self.frame.inverse.rows
        assert rows is not None
        decoder = max(abs(rows[0][k]) + abs(rows[1][k]) for k in range(3))
        if lower is not None:
            partials = tuple(max(map(abs, interval)) / lower for interval in intervals[:2])
            scales = tuple(sum(map(abs, column)) for column in self.frame.columns)
            inverse_bound = max(scales[k] + scales[2] * partials[k] for k in range(2))
            condition = inverse_bound * decoder
        object.__setattr__(self, "derivative_intervals", intervals)
        object.__setattr__(self, "branch_sign", sign)
        object.__setattr__(self, "branch_lower", lower)
        object.__setattr__(
            self, "graph_partial_bounds", None if partials is None else (partials[0], partials[1])
        )
        object.__setattr__(self, "inverse_world_lipschitz", inverse_bound)
        object.__setattr__(self, "decoder_lipschitz", decoder)
        object.__setattr__(self, "condition_upper", condition)
        checkpoint()

    @property
    def status(self) -> str:
        """
        Require a whole-enclosure branch separation and the unchanged coordinate-conditioning ceiling.
        """
        return (
            "certified_actual_native_sq_projection"
            if self.branch_lower is not None
            and self.condition_upper is not None
            and self.condition_upper <= 1024
            else "unresolved_actual_native_sq_projection"
        )
