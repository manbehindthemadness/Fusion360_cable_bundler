"""
Qualify native face parameter conditioning in the same physical coordinates as global separation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .native_face_embedding import NativeFaceEmbedding
from .native_material_chart import NativeSurfaceSnapshot
from .native_trim_boundary import derivative_bounds


def parameter_bounds(
    partials: tuple[Fraction, Fraction],
    scales: tuple[Fraction, Fraction],
    separation: Fraction,
) -> tuple[Fraction, Fraction, Fraction]:
    """
    Bound forward/inverse infinity norms and their product in declared physical parameter units.

    The native field has a three-by-two Jacobian. Global Euclidean separation
    gives minimum singular value>=separation, hence inverse-on-image2norm<=1/m.
    Converting a world three-vector to infinity norm costs at most sqrt(3)<=2.
    Forward infinity norm is at most the sum of the scaled world-L1 column
    bounds. This numerical conditioning bound grants no physical strain slack.
    """
    if (
        len(partials) != 2
        or any(type(x) is not Fraction or x < 0 for x in partials)
        or len(scales) != 2
        or any(type(x) is not Fraction or x <= 0 for x in scales)
        or type(separation) is not Fraction
        or separation <= 0
    ):
        raise ValueError(
            "Exact nonnegative partials and positive physical scales/separation required"
        )
    forward = partials[0] / scales[0] + partials[1] / scales[1]
    inverse = 2 / separation
    return forward, inverse, forward * inverse


@dataclass(frozen=True)
class NativeFaceCondition:
    """
    Retain same-native numerical conditioning, not trim coverage or a complete material-chart pass.

    The fixed coordinates are (R*phase,cV*V), in millimeters. This does not
    establish material isometry or permit cap/face labels to disagree. Native
    trim, cap adoption, interior maps and longitudinal material metrics remain
    separate requirements even when this1024 gate is qualified.
    """

    embedding: NativeFaceEmbedding
    native: NativeSurfaceSnapshot
    partial_upper: tuple[Fraction, Fraction] | None
    forward_upper: Fraction | None
    inverse_upper: Fraction | None
    condition_upper: Fraction | None
    status: str

    def __post_init__(self) -> None:
        """
        Reject stale native observations and qualification without owned positive embedding evidence.
        """
        if self.native is not self.embedding.chart.native:
            raise ValueError("Conditioning must own the SAME native surface and embedding")
        if self.status == "certified_native_face_parameter_conditioning" and (
            self.embedding.status != "certified_native_face_global_injectivity"
            or self.embedding.evidence is None
            or self.partial_upper is None
            or self.forward_upper is None
            or self.inverse_upper is None
            or self.condition_upper is None
            or self.condition_upper > 1024
            or self.condition_upper != self.forward_upper * self.inverse_upper
        ):
            raise ValueError("Owned global embedding and a qualified1024 parameter bound required")


def certify(embedding: NativeFaceEmbedding, checkpoint: Callable[[], None]) -> NativeFaceCondition:
    """
    Derive native derivative bounds on the exact snapshot owned by the embedding before applying1024.
    """
    checkpoint()
    native = embedding.chart.native
    lower, scale_v = embedding.separation_lower, embedding.profile_lower_mm
    if (
        embedding.status != "certified_native_face_global_injectivity"
        or embedding.evidence is None
        or lower is None
        or lower <= 0
        or scale_v is None
        or scale_v <= 0
    ):
        return NativeFaceCondition(
            embedding, native, None, None, None, None, "unresolved_native_face_embedding"
        )
    partials = derivative_bounds(native, checkpoint)
    forward, inverse, condition = parameter_bounds(
        partials, (embedding.chart.volume.radius_mm, scale_v), lower
    )
    status = (
        "certified_native_face_parameter_conditioning"
        if condition <= 1024
        else "unresolved_native_face_parameter_conditioning"
    )
    checkpoint()
    return NativeFaceCondition(embedding, native, partials, forward, inverse, condition, status)
