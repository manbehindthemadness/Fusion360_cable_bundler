"""
Adopt shared material labels on actual flat cap edges without guessing native parameter conventions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .exact_frame import Point
from .flat_correspondence import controls
from .native_cap_chain import ConformingCapChain
from .native_cap_material import CapMaterialBinding, NativeCapCurve
from .native_flat_cylinder import NativeCylinderSnapshot
from .native_flat_embedding import FlatSupportEmbedding


@dataclass(frozen=True)
class FlatCapIncidence:
    """
    Retain an actual captured face/converted-edge association under one native revision.

    Capture adapters establish original face/edge incidence and component-local
    analytic-to-NURBS image provenance. Converted parameters are not assumed to
    equal native edge angles, coedge parameters or cylinder UV coordinates.
    """

    native: NativeCylinderSnapshot
    curve: NativeCapCurve

    def __post_init__(self) -> None:
        """
        Reject cross-revision associations before material-label adoption.
        """
        if self.native.revision != self.curve.revision:
            raise ValueError("Face and edge must retain the SAME native revision")


def source_side(
    embedding: FlatSupportEmbedding,
    chain: ConformingCapChain,
    binding: CapMaterialBinding,
    incidence: FlatCapIncidence,
) -> int:
    """
    Require owned actual native incidence and the unique original ordered flat source.
    """
    support = embedding.support
    native = support.native
    if (
        incidence.native is not native
        or incidence.curve is not binding.native
        or binding.native.revision != native.revision
        or not any(b is binding for b in chain.bindings)
        or binding.mapping is None
    ):
        raise ValueError("The SAME actual face/curve and owned cap-chain binding required")
    matches = [
        i
        for i, source in enumerate(binding.sources)
        if source.region == (native.piece_index, native.region)
    ]
    if len(matches) != 1 or binding.sources[matches[0]].profile != support.arc:
        raise ValueError("The original unique ordered flat region/profile required")
    return matches[0]


def source_control_error(
    embedding: FlatSupportEmbedding, binding: CapMaterialBinding, side: int
) -> Fraction:
    """
    Recompute a whole-curve canonical cut bound using the SAME positive original profile weights.
    """
    support = embedding.support
    chart = support.chart
    cut = chart.high if side == 0 else chart.low
    expected = controls(chart, cut, support.arc)
    return max(
        sum((abs(a - b) for a, b in zip(p, q)), Fraction(0))
        for p, q in zip(expected, binding.sources[side].controls)
    )


@dataclass(frozen=True)
class FlatCapBoundary:
    """
    Retain approximate whole-edge label compatibility, not native trim or support-image membership.

    The original cap map assigns common q/b and physical cut s directly. World
    error adds the source-owned chain bound and radial projection distance once.
    Exact inverse-on-image membership, material increments and junction flow
    remain separate requirements even when this dimensional gate qualifies.
    """

    embedding: FlatSupportEmbedding
    chain: ConformingCapChain
    binding: CapMaterialBinding
    incidence: FlatCapIncidence
    side: int
    source_control_upper_mm: Fraction
    world_upper_mm: Fraction | None

    def __post_init__(self) -> None:
        """
        Recheck owned cuts and derived bounds so stale replacements cannot retain qualification.
        """
        side = source_side(self.embedding, self.chain, self.binding, self.incidence)
        position, chain_error = (
            self.embedding.support.position_upper_mm,
            self.chain.accuracy_upper_mm,
        )
        expected = None if position is None or chain_error is None else position + chain_error
        if (
            self.side != side
            or self.source_control_upper_mm
            != source_control_error(self.embedding, self.binding, side)
            or self.world_upper_mm != expected
        ):
            raise ValueError("The SAME canonical cut and recomputed boundary bounds required")

    @property
    def status(self) -> str:
        """
        Require both coordinate and whole-edge construction gates without trusting a stored pass flag.
        """
        qualified = (
            self.embedding.status == "certified_flat_support_global_coordinates"
            and self.chain.status == "qualified_conforming_cap_material_chain"
            and self.source_control_upper_mm
            <= self.binding.sources[self.side].canonical_error_upper_mm
            and self.world_upper_mm is not None
            and self.world_upper_mm <= Fraction(1, 100)
        )
        return (
            "qualified_flat_cap_material_labels"
            if qualified
            else "unresolved_flat_cap_material_labels"
        )

    def material_coordinates(self, coordinate: Fraction) -> Point:
        """
        Decode physical s/q/b at an exact normalized converted-curve parameter through the shared cap map.
        """
        mapping = self.binding.mapping
        if self.status != "qualified_flat_cap_material_labels" or mapping is None:
            raise ValueError("A qualified SAME-source flat cap boundary required")
        q, b = mapping.profile_coordinates(coordinate)
        chart = self.embedding.support.chart
        cut = chart.high if self.side == 0 else chart.low
        return cut.at(q), q, b


def adopt(
    embedding: FlatSupportEmbedding,
    chain: ConformingCapChain,
    binding: CapMaterialBinding,
    incidence: FlatCapIncidence,
    checkpoint: Callable[[], None],
) -> FlatCapBoundary:
    """
    Bind an actual flat edge to common labels while preserving every source/native geometry and uncertainty.
    """
    checkpoint()
    side = source_side(embedding, chain, binding, incidence)
    source_error = source_control_error(embedding, binding, side)
    position, chain_error = embedding.support.position_upper_mm, chain.accuracy_upper_mm
    world_error = None if position is None or chain_error is None else position + chain_error
    checkpoint()
    return FlatCapBoundary(embedding, chain, binding, incidence, side, source_error, world_error)
