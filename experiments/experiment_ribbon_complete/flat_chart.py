"""
Retain affine flat material coordinates in physical distance, including zero-length lead tips.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Straight

from .exact_frame import FrameInverse, Point, invert
from .volume_field import BendVolume, bend_columns


class FlatRegion(Enum):
    """
    Identify original straight and crease-side flat material regions explicitly.
    """

    STRAIGHT = "straight"
    BEFORE = "before"
    AFTER = "after"


@dataclass(frozen=True)
class MaterialCut:
    """
    Keep an exact affine boundary in common material distance s(q), without clamping tiny fragments.
    """

    offset: Fraction
    slope: Fraction = Fraction(0)

    def __post_init__(self) -> None:
        """
        Refuse an ambiguous or inexact material-domain boundary.
        """
        if any(type(x) is not Fraction for x in (self.offset, self.slope)):
            raise ValueError("Exact material cut coefficients required")

    def at(self, q: Fraction) -> Fraction:
        """
        Evaluate the unchanged longitudinal cut at one original material label.
        """
        return self.offset + self.slope * q


@dataclass(frozen=True)
class FlatChart:
    """
    Map physical s/q/b through one fixed frame, with separately retained source-domain cuts.

    A lead can have zero extent at an outer tip without a singular chart: no
    division by its q-dependent length or normalized lead fraction occurs.
    Empty/tiny negative cut extents remain visible to coverage/native audits.
    Coordinate invertibility does not establish native image or junction flow.
    """

    source: BendVolume | PlacedPiece
    region: FlatRegion
    origin: Point
    columns: tuple[Point, ...]
    low: MaterialCut
    high: MaterialCut

    def __post_init__(self) -> None:
        """
        Keep region/source identity and complete exact affine data explicit.
        """
        if (
            not isinstance(self.region, FlatRegion)
            or not isinstance(self.source, (BendVolume, PlacedPiece))
            or (self.region is FlatRegion.STRAIGHT) != isinstance(self.source, PlacedPiece)
            or (
                isinstance(self.source, PlacedPiece)
                and not isinstance(self.source.geometry, Straight)
            )
            or len(self.origin) != 3
            or any(type(x) is not Fraction for x in self.origin)
        ):
            raise ValueError("Original source identity and complete exact flat origin required")
        invert(self.columns)

    def point(self, s: Fraction, q: Fraction, b: Fraction) -> Point:
        """
        Evaluate the fixed affine chart without changing its physical material coordinates.
        """
        if any(type(x) is not Fraction for x in (s, q, b)):
            raise ValueError("Exact physical material coordinates required")
        return tuple(
            o + sum((v[k] * x for v, x in zip(self.columns, (s, q, b))), Fraction(0))
            for k, o in enumerate(self.origin)
        )

    def coordinates(self, point: Point, proof: FlatCoordinateProof) -> Point:
        """
        Invert the same certified chart exactly; domain/profile membership remains a separate check.
        """
        if len(point) != 3 or any(type(x) is not Fraction for x in point):
            raise ValueError("An exact three-dimensional world point required")
        if (
            proof.chart is not self
            or proof.status != "certified_affine_material_chart"
            or proof.frame.rows is None
        ):
            raise ValueError("A certified proof of the SAME original flat chart is required")
        delta = tuple(x - y for x, y in zip(point, self.origin))
        return tuple(
            sum((a * b for a, b in zip(row, delta)), Fraction(0)) for row in proof.frame.rows
        )


def straight(piece: PlacedPiece) -> FlatChart:
    """
    Preserve the original constant straight-piece material frame without evaluating or refitting a route.
    """
    if not isinstance(piece.geometry, Straight):
        raise ValueError("An original straight material piece is required")
    origin, forward, across = (
        tuple(Fraction(getattr(p, k)) for k in "xyz")
        for p in (piece.pose.origin, piece.pose.tangent, piece.pose.width)
    )
    columns = bend_columns(forward, across, Fraction(1), Fraction(0))
    return FlatChart(
        piece,
        FlatRegion.STRAIGHT,
        origin,
        columns,
        MaterialCut(Fraction(0)),
        MaterialCut(Fraction(piece.geometry.material_length_mm)),
    )


@dataclass(frozen=True)
class LeadFrameData:
    """
    Retain only original pose, bank and endpoint scalars required by affine flat continuations.

    These inputs do not certify a bend or reconstruct its midsurface. Capture
    adapters must establish their source provenance; no frame fitting or unit
    trigonometry is inferred from the stored coefficients.
    """

    origin: Point
    forward: Point
    columns: tuple[Point, ...]
    cosine: Fraction
    sine: Fraction
    radius_mm: Fraction
    before_mm: Fraction
    end_phase: Fraction
    end_sine: Fraction
    end_cosine: Fraction
    sign: int

    def __post_init__(self) -> None:
        """
        Validate complete exact metadata without imposing normalization or constructing bend spans.
        """
        if (
            any(
                len(p) != 3 or any(type(x) is not Fraction for x in p)
                for p in (self.origin, self.forward)
            )
            or any(
                type(x) is not Fraction
                for x in (
                    self.cosine,
                    self.sine,
                    self.radius_mm,
                    self.before_mm,
                    self.end_phase,
                    self.end_sine,
                    self.end_cosine,
                )
            )
            or min(self.cosine, self.radius_mm) <= 0
            or type(self.sign) is not int
            or self.sign not in (-1, 1)
        ):
            raise ValueError("Exact original lead pose and endpoint metadata required")
        invert(self.columns)


def lead_components(
    data: LeadFrameData, region: FlatRegion, length_mm: Fraction
) -> tuple[Point, tuple[Point, ...], MaterialCut, MaterialCut]:
    """
    Derive original affine lead geometry directly from captured endpoint metadata, without bend-span extraction.

    The full-volume entry below delegates to this same arithmetic. Lightweight
    inspection can supply the identical hashed metadata without eagerly
    reconstructing unrelated C2 tensor spans. Returned geometry alone is not a
    source-owned FlatChart or a physical/native qualification.
    """
    if (
        region not in (FlatRegion.BEFORE, FlatRegion.AFTER)
        or type(length_mm) is not Fraction
        or length_mm <= 0
    ):
        raise ValueError(
            "An explicit crease-side region and captured positive piece length required"
        )
    x, eta, normal = data.columns
    c, s, radius, before = data.cosine, data.sine, data.radius_mm, data.before_mm
    theta = data.end_phase
    entry = MaterialCut(before, -s / c)
    exit_cut = MaterialCut(before + radius * theta / c, -s / c)
    if region is FlatRegion.BEFORE:
        along = tuple(c * a - s * b for a, b in zip(x, eta))
        across = tuple(s * a + c * b for a, b in zip(x, eta))
        origin = tuple(
            o + f * before - a * before for o, f, a in zip(data.origin, data.forward, along)
        )
        return origin, (along, across, normal), MaterialCut(Fraction(0)), entry
    sn, cs = data.end_sine, data.end_cosine
    along = tuple(x[k] * cs * c - eta[k] * s + normal[k] * data.sign * sn * c for k in range(3))
    across = tuple(x[k] * cs * s + eta[k] * c + normal[k] * data.sign * sn * s for k in range(3))
    thickness = tuple(-data.sign * sn * x[k] + cs * normal[k] for k in range(3))
    d = -c * before - radius * theta
    origin = tuple(
        data.origin[k]
        + data.forward[k] * before
        + x[k] * (radius * sn + cs * d)
        + eta[k] * s * before
        + normal[k] * data.sign * (radius * (1 - cs) + sn * d)
        for k in range(3)
    )
    return origin, (along, across, thickness), exit_cut, MaterialCut(length_mm)


def lead(volume: BendVolume, region: FlatRegion, length_mm: Fraction) -> FlatChart:
    """
    Preserve source ownership while sharing the exact endpoint-only flat-frame arithmetic.
    """
    data = LeadFrameData(
        volume.origin,
        volume.forward,
        volume.columns,
        volume.cosine,
        volume.sine,
        volume.radius_mm,
        volume.before_mm,
        volume.source.surface.basis.breaks[-1],
        volume.fields.sine.controls[-1],
        volume.fields.cosine.controls[-1],
        volume.sign,
    )
    origin, columns, low, high = lead_components(data, region, length_mm)
    return FlatChart(volume, region, origin, columns, low, high)


@dataclass(frozen=True)
class FlatCoordinateProof:
    """
    Retain exact global affine coordinate validity without clearing domain/native/flow qualifications.
    """

    chart: FlatChart
    frame: FrameInverse
    condition_upper: Fraction | None
    status: str


def certify(chart: FlatChart) -> FlatCoordinateProof:
    """
    Apply the same strict positive determinant and1024 conditioning requirement in physical units.
    """
    frame = invert(chart.columns)
    condition = None if frame.inverse_norm is None else frame.norm * frame.inverse_norm
    status = (
        "certified_affine_material_chart"
        if frame.determinant > 0 and condition is not None and condition <= 1024
        else "unresolved"
    )
    return FlatCoordinateProof(chart, frame, condition, status)
