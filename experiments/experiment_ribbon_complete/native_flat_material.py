"""
Decode original flat material coordinates on native faces and bound continuous label distortion.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .cylinder_enclosure import EnclosedCylinderFace
from .exact_frame import Point
from .flat_chart import FlatCoordinateProof, certify
from .native_flat_embedding import FlatSupportEmbedding


def label_bounds(
    embedding: FlatSupportEmbedding, frame: FlatCoordinateProof
) -> tuple[Fraction, Fraction, Fraction]:
    """
    Transfer source-owned Euclidean position and L1 derivative errors into one physical-label L1 allowance.

    The induced matrix1 norm bounds simultaneous s/q/b errors; using an infinity
    norm here would not bound their sum. The position estimate is Euclidean, so
    sqrt(3)<=2 converts it to a world L1 bound before applying that matrix norm.
    E_s is already the explicit full covering-domain world L1 derivative residual
    from the SAME support embedding, not inferred
    from small position error. Integration dominates every longitudinal subinterval
    and the complete interval without cancellation or per-station allowances.
    """
    proof = embedding.evidence
    rows = frame.frame.rows
    position = embedding.support.position_upper_mm
    if (
        frame.chart is not embedding.support.chart
        or frame != certify(embedding.support.chart)
        or frame.status != "certified_affine_material_chart"
        or rows is None
        or embedding.status != "certified_flat_support_global_coordinates"
        or position is None
        or proof.error_partials is None
    ):
        raise ValueError(
            "The SAME qualified flat frame and explicit projection derivatives required"
        )
    inverse_one = max(sum(abs(row[k]) for row in rows) for k in range(3))
    if position < 0 or proof.error_partials[0] < 0 or proof.interval_mm[1] <= proof.interval_mm[0]:
        raise ValueError("Nonnegative source errors on a positive physical interval required")
    error = 2 * inverse_one * position
    rate = inverse_one * proof.error_partials[0]
    complete = rate * (proof.interval_mm[1] - proof.interval_mm[0])
    return error, rate, complete


@dataclass(frozen=True)
class FlatNativeMaterialField:
    """
    Own original physical s/q/b decoding and its source-projection label/increment bounds.

    The affine coordinate field is defined on all actual native face points.
    Error bounds compare source material labels to their decoded values on the
    support projection. They do NOT establish that this projected source image
    equals the actual trimmed face, or assign a foreign point face membership.
    Profile-domain, discrete conductor coverage and whole-ribbon physical gates
    therefore remain separate even when this coordinate field qualifies.
    """

    embedding: FlatSupportEmbedding
    native_face: EnclosedCylinderFace
    frame: FlatCoordinateProof
    label_error_upper_mm: Fraction
    increment_error_rate: Fraction
    complete_increment_upper_mm: Fraction

    def __post_init__(self) -> None:
        """
        Reject foreign native owners and stale frame or bound replacements.
        """
        if (
            self.native_face.box.native is not self.embedding.support.native
            or self.native_face.window.status != "certified_intrinsic_cylinder_window"
            or (
                self.label_error_upper_mm,
                self.increment_error_rate,
                self.complete_increment_upper_mm,
            )
            != label_bounds(self.embedding, self.frame)
        ):
            raise ValueError(
                "The SAME owned native face/material frame and derived label bounds required"
            )

    @property
    def status(self) -> str:
        """
        Apply one inclusive dimensional allowance to combined labels and every interval, without a trim pass.
        """
        return (
            "qualified_flat_native_material_field"
            if self.label_error_upper_mm <= Fraction(1, 100)
            and self.complete_increment_upper_mm <= Fraction(1, 100)
            else "unresolved_flat_native_material_field"
        )

    def coordinates(self, point: Point) -> Point:
        """
        Recover original physical s/q/b by the SAME global affine inverse, without clamping or UV inference.

        A caller claiming native-face coordinates must establish actual point
        membership under this face revision. The field itself neither projects
        the point nor silently changes the original profile or longitudinal cuts.
        """
        if self.status != "qualified_flat_native_material_field":
            raise ValueError("A qualified same-source material field required")
        return self.embedding.support.chart.coordinates(point, self.frame)


def bind(
    embedding: FlatSupportEmbedding,
    native_face: EnclosedCylinderFace,
    checkpoint: Callable[[], None],
) -> FlatNativeMaterialField:
    """
    Bind complete native intrinsic coverage to the original physical material frame and explicit error derivatives.
    """
    checkpoint()
    frame = certify(embedding.support.chart)
    error, rate, complete = label_bounds(embedding, frame)
    checkpoint()
    return FlatNativeMaterialField(embedding, native_face, frame, error, rate, complete)
