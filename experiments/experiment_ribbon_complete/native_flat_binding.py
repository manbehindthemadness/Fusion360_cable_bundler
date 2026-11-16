"""
Bind whole-face domain accuracy to source-owned native material decoding without claiming full-path compliance.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass

from .exact_frame import Point
from .flat_cut_domain import from_chart
from .native_flat_domain import NativeFlatDomainAccuracy
from .native_flat_material import FlatNativeMaterialField


@dataclass(frozen=True)
class NativeFlatBinding:
    """
    Own coordinate and domain evidence for one original profile on one actual native face.

    The source-owned field retains its validated full chart. The independently
    captured domain frame must match its exact original coefficients and cuts;
    comparing geometry here does not transfer a bend certificate to metadata.
    Native snapshots and original profile objects must share identity, and all
    enclosures must name the same actual face token. No bound is strengthened:
    coordinate/source-projection increment accuracy and distance to the original
    domain remain distinct claims, each under its existing dimensional allowance.
    Actual native full-path metrics, volume, conductor coverage and junction flow
    are not established by this binding.
    """

    material: FlatNativeMaterialField
    domain: NativeFlatDomainAccuracy
    checkpoint: InitVar[Callable[[], None]]

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Reject foreign owners, differing source geometry and enclosure token mismatches before qualification.
        """
        checkpoint()
        support = self.material.embedding.support
        boxes = (
            *self.domain.profile.boxes,
            self.domain.cuts.low_box,
            self.domain.cuts.high_box,
        )
        if (
            self.domain.profile.conic.arc is not support.arc
            or self.domain.profile.frame != from_chart(self.material.frame)
            or any(
                box.native is not support.native
                or box.face_token != self.material.native_face.box.face_token
                for box in boxes
            )
        ):
            raise ValueError(
                "The SAME native face, original profile and exact source frame required"
            )
        checkpoint()

    @property
    def status(self) -> str:
        """
        Qualify only the paired coordinate/domain claims, leaving whole material-chart acceptance separate.
        """
        return (
            "qualified_native_flat_coordinate_domain_binding"
            if self.material.status == "qualified_flat_native_material_field"
            and self.domain.status == "within_native_original_flat_domain_accuracy"
            else "unresolved_native_flat_coordinate_domain_binding"
        )

    def coordinates(self, point: Point) -> Point:
        """
        Decode without projection or clamping; callers still establish actual point membership on this face.
        """
        if self.status != "qualified_native_flat_coordinate_domain_binding":
            raise ValueError("A qualified native coordinate/domain binding required")
        return self.material.coordinates(point)
