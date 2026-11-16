"""
Bind one native shared cap curve to the same original material-profile labels on both regions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, multiply
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc

from .contact_junction_binding import RegionKey
from .exact_frame import Point
from .spatial_frame import restrict


@dataclass(frozen=True)
class NativeCapCurve:
    """
    Retain an entire captured positive quadratic Bezier representation of one bounded native edge.

    The adapter establishes native ownership and that conversion preserves the
    bounded edge image. Its normalized Bezier parameter is not the edge's
    original angle or a face co-edge parameter.
    """

    revision: str
    edge_id: int
    controls: tuple[Point, ...]
    weights: tuple[Fraction, ...]

    def __post_init__(self) -> None:
        """
        Require explicit ownership and complete exact positive-weight quadratic data.
        """
        if (
            not isinstance(self.revision, str)
            or not self.revision.strip()
            or type(self.edge_id) is not int
            or self.edge_id < 0
            or len(self.controls) != 3
            or len(self.weights) != 3
            or any(len(p) != 3 or any(type(x) is not Fraction for x in p) for p in self.controls)
            or any(type(w) is not Fraction or w <= 0 for w in self.weights)
        ):
            raise ValueError("A complete exact native quadratic cap curve required")


@dataclass(frozen=True)
class MaterialCapSource:
    """
    Retain the original cap field, profile identity and separately qualified canonical discrepancy.

    Source adapters bind controls and error to their frozen evidence. A source
    error is charged once alongside the native correspondence error. These
    local receipts grant no additional complete-path dimensional allowance.
    """

    region: RegionKey
    profile: MaterialArc
    controls: tuple[Point, ...]
    canonical_error_upper_mm: Fraction
    source_tag: str

    def __post_init__(self) -> None:
        """
        Require exact original cap geometry and an explicit nonnegative canonical error.
        """
        if (
            len(self.region) != 2
            or type(self.region[0]) is not int
            or self.region[0] < 0
            or self.region[1] not in ("straight", "before", "bend", "after")
            or len(self.controls) != 3
            or any(len(p) != 3 or any(type(x) is not Fraction for x in p) for p in self.controls)
            or len(self.profile.controls) != 3
            or any(len(p) != 2 for p in self.profile.controls)
            or len(self.profile.weights) != 3
            or min(self.profile.weights) <= 0
            or type(self.canonical_error_upper_mm) is not Fraction
            or self.canonical_error_upper_mm < 0
            or not isinstance(self.source_tag, str)
            or not self.source_tag.strip()
        ):
            raise ValueError(
                "Exact original material cap controls and qualified source error required"
            )


@dataclass(frozen=True)
class CapMaterialMap:
    """
    Keep a positive fractional-linear label map shared by both original cap fields.

    The map is a bijection onto the supplied original profile interval. Native
    orientation is retained explicitly. Geometry, labels and targets are never
    fitted or moved. A scalar parameter bijection does not establish the whole
    surface or interior atlas, trim coverage, material increments or contact.
    """

    native: NativeCapCurve
    sources: tuple[MaterialCapSource, MaterialCapSource]
    interval: tuple[Fraction, Fraction]
    reversed_native: bool
    projective_scale: Fraction
    source_errors_upper_mm: tuple[Fraction, Fraction]

    def __post_init__(self) -> None:
        """
        Keep the parameter bijection and both exact dimensional bounds internally valid.
        """
        if (
            type(self.reversed_native) is not bool
            or type(self.projective_scale) is not Fraction
            or self.projective_scale <= 0
            or len(self.interval) != 2
            or any(type(x) is not Fraction for x in self.interval)
            or not 0 <= self.interval[0] < self.interval[1] <= 1
            or len(self.source_errors_upper_mm) != 2
            or any(
                type(x) is not Fraction or not 0 <= x <= Fraction(1, 100)
                for x in self.source_errors_upper_mm
            )
        ):
            raise ValueError(
                "A positive exact original-label bijection and both dimensional bounds required"
            )

    def parameter(self, coordinate: Fraction) -> Fraction:
        """
        Decode the SAME original material V from the normalized converted-native curve parameter.
        """
        if type(coordinate) is not Fraction or not 0 <= coordinate <= 1:
            raise ValueError("An exact unit native curve parameter required")
        z = 1 - coordinate if self.reversed_native else coordinate
        scaled = self.projective_scale * z / (1 - z + self.projective_scale * z)
        a, b = self.interval
        return a + (b - a) * scaled

    def profile_coordinates(self, coordinate: Fraction) -> tuple[Fraction, Fraction]:
        """
        Generate the SAME original q/b labels shared by both cap regions without a geometric inverse.
        """
        v = self.parameter(coordinate)
        profile = self.sources[0].profile
        factors = tuple(
            Fraction(w) * basis
            for w, basis in zip(profile.weights, ((1 - v) ** 2, 2 * v * (1 - v), v * v))
        )
        denominator = sum(factors, Fraction(0))
        labels = tuple(
            sum((Fraction(p[k]) * w for p, w in zip(profile.controls, factors)), Fraction(0))
            / denominator
            for k in range(2)
        )
        return labels[0], labels[1]

    def native_coordinate(self, parameter: Fraction) -> Fraction:
        """
        Invert the positive label map exactly without assuming an edge-angle parameter identity.
        """
        a, b = self.interval
        if type(parameter) is not Fraction or not a <= parameter <= b:
            raise ValueError(
                "An exact original profile parameter inside this cap interval required"
            )
        t = (parameter - a) / (b - a)
        coordinate = t / (self.projective_scale + (1 - self.projective_scale) * t)
        return 1 - coordinate if self.reversed_native else coordinate


@dataclass(frozen=True)
class CapMaterialBinding:
    """
    Retain unique orientation qualification or explicit unresolved geometric/label ambiguity.
    """

    native: NativeCapCurve
    sources: tuple[MaterialCapSource, MaterialCapSource]
    interval: tuple[Fraction, Fraction]
    mapping: CapMaterialMap | None
    candidate_errors_upper_mm: tuple[tuple[Fraction, Fraction], ...]
    status: str

    def __post_init__(self) -> None:
        """
        Refuse stale maps when the binding's native curve or original sources are replaced.
        """
        mapping = self.mapping
        if mapping is not None and (
            mapping.native is not self.native
            or mapping.sources is not self.sources
            or mapping.interval != self.interval
            or mapping.source_errors_upper_mm
            != self.candidate_errors_upper_mm[int(mapping.reversed_native)]
        ):
            raise ValueError("The binding must own the SAME native curve and original cap sources")
        expected = (
            "qualified_shared_cap_material_parameter"
            if mapping is not None
            else "unresolved_shared_cap_material_parameter"
        )
        if self.status != expected:
            raise ValueError("Cap material status must preserve unresolved correspondence")


def bind(
    native: NativeCapCurve,
    sources: tuple[MaterialCapSource, MaterialCapSource],
    interval: tuple[Fraction, Fraction],
    expected_revision: str,
    checkpoint: Callable[[], None],
) -> CapMaterialBinding:
    """
    Qualify one shared original V map by whole-curve homogeneous residual bounds on both regions.

    Restrict the original homogeneous quadratic to [a,b]. Under
    t=lambda*z/(1-z+lambda*z), its homogeneous control i is multiplied by
    lambda**i. Choose positive lambda to match the first two weight ratios;
    remaining weight/position differences stay in the exact residual. This
    defines an explicit map, rather than inferring parameter identity from
    endpoint matches. Cross multiplication over positive denominators bounds
    all points, not just samples. Both possible native orientations are tested;
    zero or two acceptable orientations remain unresolved. Scalar derivative
    variation above1024 remains unresolved without changing a work budget.
    """
    checkpoint()
    if (
        native.revision != expected_revision
        or len(sources) != 2
        or sources[0].region == sources[1].region
        or sources[0].profile != sources[1].profile
        or len(interval) != 2
        or any(type(x) is not Fraction for x in interval)
        or not 0 <= interval[0] < interval[1] <= 1
    ):
        raise ValueError(
            "The SAME native revision and two original same-profile cap regions required"
        )
    source_weights = tuple(Fraction(w) for w in sources[0].profile.weights)
    fields = []
    for source in sources:
        checkpoint()
        axes = tuple(
            restrict(
                tuple(
                    (p[k] if k < 3 else Fraction(1)) * w
                    for p, w in zip(source.controls, source_weights)
                ),
                *interval,
            )
            for k in range(4)
        )
        fields.append(axes)
    candidates = []
    accepted = []
    for reversed_native in (False, True):
        checkpoint()
        controls = tuple(reversed(native.controls)) if reversed_native else native.controls
        weights = tuple(reversed(native.weights)) if reversed_native else native.weights
        w = fields[0][3]
        scale = w[0] * weights[1] / (w[1] * weights[0])
        errors = []
        for source, axes in zip(sources, fields):
            checkpoint()
            transformed = tuple(
                tuple(value * scale**i for i, value in enumerate(axis)) for axis in axes
            )
            denominator = multiply(transformed[3], weights)
            residuals = tuple(
                add(
                    multiply(transformed[k], weights),
                    multiply(
                        tuple(p[k] * weight for p, weight in zip(controls, weights)), transformed[3]
                    ),
                    Fraction(-1),
                )
                for k in range(3)
            )
            error = max(
                sum((abs(axis[j]) for axis in residuals), Fraction(0)) / d
                for j, d in enumerate(denominator)
            )
            errors.append(error + source.canonical_error_upper_mm)
        pair = errors[0], errors[1]
        candidates.append(pair)
        if max(pair) <= Fraction(1, 100) and max(scale, 1 / scale) ** 2 <= 1024:
            accepted.append(CapMaterialMap(native, sources, interval, reversed_native, scale, pair))
    mapping = accepted[0] if len(accepted) == 1 else None
    status = (
        "qualified_shared_cap_material_parameter"
        if mapping is not None
        else "unresolved_shared_cap_material_parameter"
    )
    checkpoint()
    return CapMaterialBinding(native, sources, interval, mapping, tuple(candidates), status)
