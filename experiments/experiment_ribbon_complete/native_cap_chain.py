"""
Construct conforming original material labels on a native vertex-connected cap chain.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, derivative, elevate, multiply
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc

from .exact_frame import Point
from .native_cap_material import CapMaterialBinding, CapMaterialMap, NativeCapCurve, bind


@dataclass(frozen=True)
class CapEndpointEvidence:
    """
    Retain unique converted-curve endpoint identity or unresolved geometric ambiguity.

    Capture adapters establish actual body-local vertex identity and points under
    the SAME native revision. The endpoint uncertainty is charged to the chain;
    endpoint coincidence alone never establishes whole-curve material fidelity.
    """

    native: NativeCapCurve
    observed_vertices: tuple[int, int]
    observed_points: tuple[Point, Point]
    ordered_vertices: tuple[int, int] | None
    upper_mm: Fraction | None
    status: str

    def __post_init__(self) -> None:
        """
        Keep endpoint qualification, original vertex identity and dimensional uncertainty consistent.
        """
        qualified = self.ordered_vertices is not None
        expected = (
            "qualified_cap_endpoint_identity" if qualified else "unresolved_cap_endpoint_identity"
        )
        if self.status != expected or (not qualified and self.upper_mm is not None):
            raise ValueError("Endpoint status must preserve unresolved identity")
        if self.ordered_vertices is not None and (
            len(self.ordered_vertices) != 2
            or set(self.ordered_vertices) != set(self.observed_vertices)
            or type(self.upper_mm) is not Fraction
            or not 0 <= self.upper_mm <= Fraction(1, 100)
        ):
            raise ValueError("A native endpoint permutation and exact dimensional bound required")


def orient_endpoints(
    native: NativeCapCurve,
    vertices: tuple[int, int],
    points: tuple[Point, Point],
    checkpoint: Callable[[], None],
) -> CapEndpointEvidence:
    """
    Assign native vertex IDs to converted control endpoints only when one orientation qualifies.
    """
    checkpoint()
    if (
        len(vertices) != 2
        or any(type(x) is not int for x in vertices)
        or vertices[0] == vertices[1]
        or len(points) != 2
        or any(len(p) != 3 or any(type(x) is not Fraction for x in p) for p in points)
    ):
        raise ValueError("Two distinct original native vertices and exact endpoint points required")
    accepted = []
    for reverse in (False, True):
        checkpoint()
        ordered = tuple(reversed(points)) if reverse else points
        error = max(
            sum((abs(a - b) for a, b in zip(p, q)), Fraction(0))
            for p, q in zip((native.controls[0], native.controls[-1]), ordered)
        )
        if error <= Fraction(1, 100):
            ids = (vertices[1], vertices[0]) if reverse else vertices
            accepted.append((ids, error))
    ids, error = accepted[0] if len(accepted) == 1 else (None, None)
    status = (
        "qualified_cap_endpoint_identity" if ids is not None else "unresolved_cap_endpoint_identity"
    )
    return CapEndpointEvidence(native, vertices, points, ids, error, status)


def parameter_discrepancy(first: CapMaterialMap, second: CapMaterialMap) -> Fraction:
    """
    Bound the original V relabelling at every normalized point of the SAME native curve.
    """
    if first.native is not second.native or first.sources is not second.sources:
        raise ValueError("The SAME native curve and original sources required for label comparison")

    def coefficients(mapping: CapMaterialMap) -> tuple[tuple[Fraction, ...], tuple[Fraction, ...]]:
        """
        Express a positive fractional-linear V map in the original converted-curve direction.
        """
        low, high = mapping.interval
        scale = mapping.projective_scale
        mapped_numerator, mapped_denominator = (low, high * scale), (Fraction(1), scale)
        return (
            (tuple(reversed(mapped_numerator)), tuple(reversed(mapped_denominator)))
            if mapping.reversed_native
            else (mapped_numerator, mapped_denominator)
        )

    a, w = coefficients(first)
    b, v = coefficients(second)
    numerator = add(multiply(a, v), multiply(b, w), Fraction(-1))
    denominator = multiply(w, v)
    return max(abs(x) / y for x, y in zip(numerator, denominator))


def profile_rates(profile: MaterialArc) -> tuple[Fraction, Fraction]:
    """
    Bound physical q/b derivatives per original V using the positive rational profile denominator.
    """
    weights = tuple(Fraction(w) for w in profile.weights)
    if (
        len(weights) != 3
        or min(weights) <= 0
        or len(profile.controls) != 3
        or any(len(p) != 2 for p in profile.controls)
    ):
        raise ValueError("The original complete positive rational quadratic profile required")
    denominator = multiply(weights, weights)
    rates = []
    for k in range(2):
        numerator = tuple(Fraction(p[k]) * w for p, w in zip(profile.controls, weights))
        residual = elevate(
            add(
                multiply(derivative(numerator), weights),
                multiply(numerator, derivative(weights)),
                Fraction(-1),
            ),
            4,
        )
        rates.append(max(abs(x) / y for x, y in zip(residual, denominator)))
    return rates[0], rates[1]


@dataclass(frozen=True)
class ConformingCapChain:
    """
    Retain one exact native-vertex label partition and every requalified whole-curve map.

    Geometry, native UVs and input targets are untouched. Combined errors include
    source geometry, endpoint uncertainty and physical s/q/b relabelling. This is
    a cap-chain receipt, not a new allowance per station, complete longitudinal
    path, face/interior atlas, trim, material strain, contact or junction flow.
    """

    original: tuple[CapMaterialBinding, ...]
    endpoints: tuple[CapEndpointEvidence, ...]
    bindings: tuple[CapMaterialBinding, ...]
    vertex_labels: tuple[tuple[int, Fraction], ...]
    relabel_upper_mm: tuple[Fraction, ...]
    accuracy_upper_mm: Fraction | None
    status: str

    def __post_init__(self) -> None:
        """
        Require complete owned maps and exact0/1 vertex coverage before a chain can be qualified.
        """
        if self.status != "qualified_conforming_cap_material_chain":
            return
        count = len(self.original)
        if (
            not count
            or len(self.bindings) != count
            or len(self.endpoints) != count
            or len(self.relabel_upper_mm) != count
            or len(self.vertex_labels) != count + 1
            or self.vertex_labels[0][1] != 0
            or self.vertex_labels[-1][1] != 1
            or len({i for i, _ in self.vertex_labels}) != count + 1
            or type(self.accuracy_upper_mm) is not Fraction
            or not 0 <= self.accuracy_upper_mm <= Fraction(1, 100)
            or any(type(x) is not Fraction or x < 0 for x in self.relabel_upper_mm)
            or any(
                b.mapping is None
                or b.native is not old.native
                or e.native is not old.native
                or b.sources is not old.sources
                or b.interval != (self.vertex_labels[i][1], self.vertex_labels[i + 1][1])
                for i, (b, old, e) in enumerate(zip(self.bindings, self.original, self.endpoints))
            )
        ):
            raise ValueError("A complete SAME-source conforming native material chain required")


def conform(
    original: tuple[CapMaterialBinding, ...],
    endpoints: tuple[CapEndpointEvidence, ...],
    cut_slopes: tuple[Fraction, Fraction],
    checkpoint: Callable[[], None],
) -> ConformingCapChain:
    """
    Partition original V=[0,1] along a single ordered native vertex chain and requalify both sources.

    Internal cuts are the exact midpoint of adjacent existing interval estimates.
    This chooses a material-label correspondence, never edits a native UV or
    repairs geometry. Fixed original profile endpoints remain0/1. Every changed
    curve map is bounded against BOTH frozen cap fields. Its label displacement
    is converted to s/q/b millimeters using original rational profile derivatives
    and original affine cut slopes; no dimensionless V tolerance is substituted.
    """
    checkpoint()
    if (
        not original
        or len(original) != len(endpoints)
        or len({b.native.edge_id for b in original}) != len(original)
        or len(cut_slopes) != 2
        or any(type(x) is not Fraction for x in cut_slopes)
        or any(b.mapping is None or b.sources is not original[0].sources for b in original)
        or any(e.native is not b.native for b, e in zip(original, endpoints))
    ):
        raise ValueError("Qualified SAME-source cap maps and owned endpoint evidence required")
    ordered = sorted(zip(original, endpoints), key=lambda item: item[0].interval[0])
    old, observed = tuple(p[0] for p in ordered), tuple(p[1] for p in ordered)

    def unresolved(reason: str) -> ConformingCapChain:
        """
        Preserve all original evidence without inventing a missing chain or acceptance bound.
        """
        return ConformingCapChain(old, observed, (), (), (), None, reason)

    vertices = []
    for bound, evidence in ordered:
        checkpoint()
        mapping = bound.mapping
        assert mapping is not None
        if evidence.ordered_vertices is None or evidence.upper_mm is None:
            return unresolved("unresolved_cap_endpoint_identity")
        a, b = evidence.ordered_vertices
        if mapping.reversed_native:
            a, b = b, a
        if vertices and vertices[-1] != a:
            return unresolved("unresolved_native_cap_chain_order")
        if not vertices:
            vertices.append(a)
        vertices.append(b)
    if len(set(vertices)) != len(vertices):
        return unresolved("unresolved_native_cap_chain_order")
    cuts = (
        (Fraction(0),)
        + tuple((a.interval[1] + b.interval[0]) / 2 for a, b in zip(old, old[1:]))
        + (Fraction(1),)
    )
    if any(a >= b for a, b in zip(cuts, cuts[1:])):
        return unresolved("unresolved_original_cap_partition")
    q_rate, b_rate = profile_rates(old[0].sources[0].profile)
    coordinate_rate = (1 + max(map(abs, cut_slopes))) * q_rate + b_rate
    bindings, errors = [], []
    maximum = Fraction(0)
    status = "qualified_conforming_cap_material_chain"
    for i, (prior, evidence) in enumerate(ordered):
        checkpoint()
        current = bind(
            prior.native, prior.sources, (cuts[i], cuts[i + 1]), prior.native.revision, checkpoint
        )
        first, second = prior.mapping, current.mapping
        if first is None or second is None or first.reversed_native != second.reversed_native:
            status = "unresolved_conforming_cap_curve"
            break
        relabel = parameter_discrepancy(first, second) * coordinate_rate
        assert evidence.upper_mm is not None
        combined = max(second.source_errors_upper_mm) + evidence.upper_mm + relabel
        bindings.append(current)
        errors.append(relabel)
        maximum = max(maximum, combined)
        if combined > Fraction(1, 100):
            status = "unresolved_conforming_cap_accuracy"
            break
    checkpoint()
    return ConformingCapChain(
        old, observed, tuple(bindings), tuple(zip(vertices, cuts)), tuple(errors), maximum, status
    )
