"""
Lift captured winding-region coverage to a surface patch in original physical material and world coordinates.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction

from artifacts.verification.resume3217.metric import product

from .material_paths import combine
from .native_planar_projection import NativePlanarProjection, label_numerators
from .native_surface_metric import rational_partial_bounds
from .projected_filled_domain import ProjectedFilledDomain


def _profile_error(
    projected: ProjectedFilledDomain, checkpoint: Callable[[], None]
) -> tuple[Fraction, Fraction]:
    """
    Bound the complete surface's b displacement from the correct finite original profile graph.

    Positive rational control hulls enclose all decoded physical q/b values.
    The conic's b derivative must retain one sign over their convex hull with
    original profile controls. A mean-value bound includes native q overhang;
    the nearest in-range q is only a proof witness, never a changed coordinate.
    """
    first = projected.boundary[0].finite
    surface, frame, graph = first.trace.surface, first.frame, first.graph
    labels = label_numerators(surface, frame)
    weight = surface.weights
    coordinates = labels[1], labels[2], weight
    denominator = product(weight, weight)
    residual = ((Fraction(0),),)
    for i in range(3):
        for j in range(3):
            checkpoint()
            residual = combine(
                residual, product(coordinates[i], coordinates[j]), graph.conic.matrix[i][j]
            )
    error = max(abs(n) / d for ns, ds in zip(residual, denominator) for n, d in zip(ns, ds))
    controls = tuple(
        (labels[1][i][j] / w, labels[2][i][j] / w)
        for i, row in enumerate(weight)
        for j, w in enumerate(row)
    )
    hull = tuple(tuple(map(Fraction, p)) for p in graph.conic.arc.controls) + controls
    gradients = tuple(
        tuple(
            2 * sum(graph.conic.matrix[k][j] * x for j, x in enumerate((*p, Fraction(1))))
            for k in range(2)
        )
        for p in hull
    )
    hb = [g[1] for g in gradients]
    lower = min(hb) if min(hb) > 0 else -max(hb) if max(hb) < 0 else Fraction(0)
    if lower <= 0:
        raise ValueError(
            "The SAME separated original profile graph branch required over the whole surface"
        )
    low, high = graph.interval
    overhang = max(max(low - q, q - high, Fraction(0)) for q, _ in controls)
    return (error + max(abs(g[0]) for g in gradients) * overhang) / lower, overhang


@dataclass(frozen=True)
class SurfaceLoopMaterialCoverage:
    """
    Bound both directions of a comparison surface patch against the original material patch.

    Original UV traces and straight UV endpoint bridges lie in the same convex
    natural rectangle. Their surface images close a loop inside its globally
    injective physical (s,q) projection. That image is a topological disk; winding
    of a contained loop is zero outside it. The comparison filled region can
    therefore be lifted through the unique surface inverse. No arbitrary world
    chord or implicit output welding is used to establish surface membership.

    Integrated global UV metrics bound every replacement bridge. Adding their
    summed physical-label length to the old collar retains its winding homotopy
    and convex source-core argument. Whole-tensor conic and branch bounds then
    lift planar distances through original b(q), in both material and world L1.

    This does not identify the comparison patch with an actual SDK trimmed face,
    establish native-original correspondence, or certify isometry or path lengths.
    """

    projected: ProjectedFilledDomain
    projection: NativePlanarProjection
    checkpoint: InitVar[Callable[[], None]]
    bridge_world_lengths_mm: tuple[Fraction, ...] = field(init=False)
    bridge_label_lengths_mm: tuple[Fraction, ...] = field(init=False)
    collar_upper_mm: Fraction = field(init=False)
    profile_graph_error_mm: Fraction = field(init=False)
    profile_q_overhang_mm: Fraction = field(init=False)
    lift_factor: Fraction = field(init=False)
    forward_upper_mm: Fraction = field(init=False)
    reverse_upper_mm: Fraction = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Require identical surface/frame owners and derive every bridge, graph and distance bound under one checkpoint.
        """
        checkpoint()
        first = self.projected.boundary[0].finite
        surface, frame, graph = first.trace.surface, first.frame, first.graph
        if (
            self.projection.surface is not surface
            or self.projection.frame is not frame
            or self.projection.status != "certified_global_native_sq_projection"
        ):
            raise ValueError("The SAME globally injective physical surface projection required")
        metric = rational_partial_bounds(surface, checkpoint)
        inverse = frame.inverse.rows
        assert inverse is not None
        inverse_one = max(sum(abs(row[k]) for row in inverse) for k in range(3))
        endpoints = []
        for directed in self.projected.boundary:
            controls = directed.finite.trace.curve.controls
            endpoints.append(
                (controls[-1], controls[0]) if directed.reversed else (controls[0], controls[-1])
            )
        bridges = []
        for current, following in zip(endpoints, endpoints[1:] + endpoints[:1]):
            checkpoint()
            bridges.append(
                sum(scale * abs(a - b) for scale, a, b in zip(metric, current[1], following[0]))
            )
        labels = tuple(inverse_one * length for length in bridges)
        collar = self.projected.collar_upper_mm + sum(labels)
        error, overhang = _profile_error(self.projected, checkpoint)
        scales = tuple(sum(map(abs, column)) for column in frame.columns)
        lift = max(1 + graph.slope_upper, scales[0], scales[1] + scales[2] * graph.slope_upper)
        residual = max(Fraction(1), scales[2]) * error
        reverse = 2 * self.projected.source_radius_mm * collar / self.projected.source_inradius_mm
        object.__setattr__(self, "bridge_world_lengths_mm", tuple(bridges))
        object.__setattr__(self, "bridge_label_lengths_mm", labels)
        object.__setattr__(self, "collar_upper_mm", collar)
        object.__setattr__(self, "profile_graph_error_mm", error)
        object.__setattr__(self, "profile_q_overhang_mm", overhang)
        object.__setattr__(self, "lift_factor", lift)
        object.__setattr__(self, "forward_upper_mm", lift * collar + residual)
        object.__setattr__(self, "reverse_upper_mm", lift * reverse + residual)
        checkpoint()

    @property
    def status(self) -> str:
        """
        Require one inclusive joint material/world allowance and a nonempty collar-free source core.
        """
        return (
            "within_comparison_surface_material_coverage"
            if 2 * self.collar_upper_mm < self.projected.source_inradius_mm
            and max(self.forward_upper_mm, self.reverse_upper_mm) <= Fraction(1, 100)
            else "unresolved_comparison_surface_material_coverage"
        )
