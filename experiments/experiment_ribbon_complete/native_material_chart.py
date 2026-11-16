"""
Bind actual native NURBS parameters to original material labels with a complete positional bound.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3217.extraction import Net
from artifacts.verification.resume3255.run import profile_reach
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc

from .spatial_frame import split_at
from .volume_boundary import RationalBoundaryResidual, compose, control_residual
from .volume_field import BendVolume, Point


@dataclass(frozen=True)
class NativeSurfaceSnapshot:
    """
    Own exact component-local millimetre controls captured from one unchanged native face.

    Capture adapters establish actual body/face identity and source hashes.
    Native renderer UVs are not inferred from geometry or profile names alone.
    """

    revision: str
    face_index: int
    piece_index: int
    profile_label: str
    degree_u: int
    degree_v: int
    knots_u: tuple[Fraction, ...]
    knots_v: tuple[Fraction, ...]
    rows: Net
    weights: tuple[tuple[Fraction, ...], ...]

    def __post_init__(self) -> None:
        """
        Reject malformed, nonpositive-weight or incomplete surface observations before binding.
        """
        if (
            not isinstance(self.revision, str)
            or not self.revision.strip()
            or not isinstance(self.profile_label, str)
            or not self.profile_label.strip()
            or any(type(x) is not int or x < 0 for x in (self.face_index, self.piece_index))
            or any(type(x) is not int or x < 1 for x in (self.degree_u, self.degree_v))
            or not self.rows
            or not self.rows[0]
        ):
            raise ValueError(
                "Explicit native identity, positive degrees and complete controls required"
            )
        count = len(self.rows[0])
        if (
            len(self.weights) != len(self.rows)
            or any(len(row) != count for row in self.rows + self.weights)
            or any(
                len(p) != 3 or any(type(x) is not Fraction for x in p)
                for row in self.rows
                for p in row
            )
            or any(type(w) is not Fraction or w <= 0 for row in self.weights for w in row)
            or len(self.knots_u) != len(self.rows) + self.degree_u + 1
            or len(self.knots_v) != count + self.degree_v + 1
            or any(type(x) is not Fraction for x in self.knots_u + self.knots_v)
            or any(
                a > b for knots in (self.knots_u, self.knots_v) for a, b in zip(knots, knots[1:])
            )
        ):
            raise ValueError(
                "Exact complete native tensor, positive weights and consistent knots required"
            )


@dataclass(frozen=True)
class NativeCorrespondence:
    """
    Bind a reusable exact control residual to the SAME original source/profile/native observations.
    """

    volume: BendVolume
    arc: MaterialArc
    native: NativeSurfaceSnapshot
    residual: RationalBoundaryResidual


@dataclass(frozen=True)
class NativeMaterialChart:
    """
    Retain a source-owned parameter correspondence, not a native injectivity or contact flag.

    The bound covers the complete untrimmed surface parameter rectangle, so also
    covers every retained trimmed point. Trim coverage, native global regularity,
    material increments, junction flow and volume contact remain independent.
    """

    volume: BendVolume
    arc: MaterialArc
    native: NativeSurfaceSnapshot
    position_upper_mm: Fraction | None
    status: str
    correspondence: NativeCorrespondence | None = None

    def __post_init__(self) -> None:
        """
        Refuse stale owned residuals when a chart's geometry or native observation is replaced.
        """
        owned = self.correspondence
        if owned is not None and (
            owned.volume is not self.volume
            or owned.arc is not self.arc
            or owned.native is not self.native
            or self.position_upper_mm != owned.residual.position_upper_mm
        ):
            raise ValueError(
                "Correspondence must own the SAME original source/profile/native chart"
            )
        if self.status == "certified_native_material_parameter_chart" and (
            owned is None
            or self.position_upper_mm is None
            or self.position_upper_mm > Fraction(1, 100)
        ):
            raise ValueError("A qualified native chart requires its owned complete position bound")


def bind(
    volume: BendVolume,
    arc: MaterialArc,
    native: NativeSurfaceSnapshot,
    source_piece: int,
    expected_revision: str,
    checkpoint: Callable[[], None],
) -> NativeMaterialChart:
    """
    Require original source knots/weights/identity before certifying phase=U and profile parameter=V.

    No remapping, degree guessing, normalization or geometric correction occurs.
    Native and canonical charts share nonnegative global U basis functions.
    Exact homogeneous control differences bound every position to0.01mm inclusive.
    A larger bound is unresolved, not proof of a dimensional violation.
    """
    checkpoint()
    if (
        native.piece_index != source_piece
        or native.profile_label != arc.label
        or native.revision != expected_revision
    ):
        raise ValueError(
            "The SAME native body, source piece and original profile identity required"
        )
    basis = volume.source.surface.basis
    weights = tuple(Fraction(w) for w in arc.weights)
    if (
        native.degree_u != 5
        or native.degree_v != 2
        or len(native.rows) != basis.count
        or native.knots_u != basis.knots
        or native.knots_v != (Fraction(0),) * 3 + (Fraction(1),) * 3
        or any(row != weights for row in native.weights)
    ):
        return NativeMaterialChart(volume, arc, native, None, "unresolved_native_parameterization")
    if (
        len(arc.controls) != 3
        or len(weights) != 3
        or min(weights) <= 0
        or any(len(p) != 2 for p in arc.controls)
    ):
        raise ValueError("Original positive rational quadratic profile required")
    if max(abs(Fraction(q)) for q, _ in arc.controls) > volume.source.half_mm:
        raise ValueError("Original profile must remain inside the captured source width")
    if profile_reach({"controls": arc.controls, "weights": arc.weights}) > volume.half_thickness_mm:
        raise ValueError("Original profile must remain inside the captured source thickness")
    rows = tuple(
        tuple(tuple(Fraction(getattr(p, k)) for k in "xyz") for p in row)
        for row in volume.source.surface.rows
    )
    normals = tuple(
        tuple(curve.controls[i] for curve in volume.normals) for i in range(basis.count)
    )
    canonical = compose(rows, normals, volume.source.half_mm, arc, checkpoint)
    residual = control_residual(canonical, native.rows, arc, checkpoint)
    upper = residual.position_upper_mm
    return NativeMaterialChart(
        volume,
        arc,
        native,
        upper,
        "certified_native_material_parameter_chart"
        if upper <= Fraction(1, 100)
        else "unresolved_native_position_bound",
        NativeCorrespondence(volume, arc, native, residual),
    )


@dataclass(frozen=True)
class NativeMaterialLabel:
    """
    Retain exact original surface material labels for one verified native parameter pair.
    """

    chart: NativeMaterialChart
    phase: Fraction
    profile_parameter: Fraction
    material_coordinates: Point
    canonical_point: Point


def decode(
    chart: NativeMaterialChart, phase: Fraction, parameter: Fraction, checkpoint: Callable[[], None]
) -> NativeMaterialLabel:
    """
    Decode original q/b and physical local material distance without a world inverse or image assumption.

    The caller establishes that parameters belong to this actual native face's
    trimmed chart, under the recorded revision. This function enforces the full
    source parameter domain and retains the complete-chart position bound.
    It neither changes native renderer UVs nor certifies whole-output compliance.
    """
    checkpoint()
    if (
        chart.status != "certified_native_material_parameter_chart"
        or chart.position_upper_mm is None
    ):
        raise ValueError("A certified SAME-source native parameter chart required")
    basis = chart.volume.source.surface.basis
    if (
        any(type(x) is not Fraction for x in (phase, parameter))
        or not basis.breaks[0] <= phase <= basis.breaks[-1]
        or not 0 <= parameter <= 1
    ):
        raise ValueError("Exact parameters inside the original native/source chart domain required")
    w = tuple(Fraction(x) for x in chart.arc.weights)
    denominator = split_at(w, parameter)[0][-1]
    q, b = tuple(
        split_at(
            tuple(Fraction(p[k]) * weight for p, weight in zip(chart.arc.controls, w)), parameter
        )[0][-1]
        / denominator
        for k in range(2)
    )
    volume = chart.volume
    material = (
        (volume.radius_mm * phase - volume.sine * q) / volume.cosine + volume.before_mm,
        q,
        b,
    )
    return NativeMaterialLabel(chart, phase, parameter, material, volume.jet(phase, q, b).point)
