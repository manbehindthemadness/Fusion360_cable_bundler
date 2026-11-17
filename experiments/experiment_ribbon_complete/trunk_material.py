"""
Measure source-owned Hermite trunk paths against their common material-distance charts.

The unchanged authoring map supplies every control. Native image/trim fidelity,
interior material ownership and flow across source seams remain separate checks.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from fractions import Fraction

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Straight
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc
from experiments.experiment_ribbon_fold_route.material_surfaces import material_patches

from .contracts import ConductorKey
from .curve_lengths import distance
from .execution import RibbonPlan
from .material_accounting import TrunkDiscrepancy
from .material_distance import DistanceSpan, MaterialDistanceAudit, measure
from .material_phase import uniform_phase_chart
from .material_traces import traces
from .spatial_frame import restrict


@dataclass
class TrunkMetricWork:
    """
    Charge every captured polynomial span to one caller-owned measurement allocation.
    """

    maximum_spans: int
    checkpoint: Callable[[], None]
    spans: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        """
        Refuse missing or ambiguous allocation sizes.
        """
        if type(self.maximum_spans) is not int or self.maximum_spans < 1:
            raise ValueError("A positive trunk measurement span allocation is required")

    def take(self) -> None:
        """
        Stop before capturing another span without creating a replacement allocation.
        """
        self.checkpoint()
        if self.spans >= self.maximum_spans:
            raise RuntimeError("Shared trunk metric span allocation exhausted")
        self.spans += 1


def piece_path(piece: PlacedPiece, q: Fraction, work: TrunkMetricWork) -> MaterialDistanceAudit:
    """
    Extract one fixed-q midplane path through the exact current authoring implementation.

    A repeated profile coordinate is an evaluation probe, never a new contour or
    native build. Its three identical columns reduce the unchanged authoring map
    to a polynomial path. Every original phase cell is measured without fitting,
    subdivision search or an ideal-isometry substitution. Bend phase maps to
    s=before+R*phase/cos(bank)-q*tan(bank), retaining staggered material cuts.
    Physical phase uses the exact requested uniform partition. The unchanged
    controls still evaluate their original encoded cells; their derivative error
    against these material increments includes phase encoding, without an extra
    tolerance or an assumption of unit speed. Spatial seam gaps remain recorded.

    Intersect original cells with the declared0..L material domain, restricting
    the SAME controls exactly. Empty outside-domain leads contribute no curve.
    This is domain restriction, not endpoint clamping or geometry repair.
    """
    work.checkpoint()
    if type(piece) is not PlacedPiece or type(piece.geometry) not in (Straight, CylindricalFold):
        raise ValueError(
            "Original supported material pieces required; custom dispatch is unqualified"
        )
    if type(q) is not Fraction or Fraction(float(q)) != q:
        raise ValueError("The original material label must have an exact authoring representation")
    geometry = piece.geometry
    length = Fraction(geometry.material_length_mm)
    coordinate = float(q)
    probe = MaterialArc(((coordinate, 0.0),) * 3, (1.0,) * 3, "material-coordinate-probe")
    patches = material_patches((piece,), (probe,))
    spans = []
    for patch in patches:
        work.checkpoint()
        if any(row[0] != row[1] or row[0] != row[2] for row in patch.rows):
            raise ValueError("Authoring probe no longer represents one fixed material path")
        controls = tuple(
            tuple(Fraction(getattr(row[0], axis)) for axis in "xyz") for row in patch.rows
        )
        if isinstance(geometry, Straight):
            intervals = ((Fraction(0), length, controls),)
        else:
            cosine, sine = (
                Fraction(math.cos(geometry.bank_radians)),
                Fraction(math.sin(geometry.bank_radians)),
            )
            if cosine <= 0:
                raise ValueError("A positive source crease cosine is required")
            radius = Fraction(geometry.radius_mm)
            entry = Fraction(geometry.before_mm) - q * sine / cosine
            exit_cut = entry + radius * Fraction(abs(geometry.angle_radians)) / cosine
            if patch.region == "before":
                intervals = ((Fraction(0), entry, controls),)
            elif patch.region == "after":
                intervals = ((exit_cut, length, controls),)
            elif patch.region == "bend":
                chart = uniform_phase_chart(abs(geometry.angle_radians), patch.knots_u)
                breaks = chart.nominal
                if len(controls) != 3 * (len(breaks) - 1) + 1:
                    raise ValueError("Original cubic phase cells and complete controls required")
                intervals = tuple(
                    (
                        entry + radius * low / cosine,
                        entry + radius * high / cosine,
                        controls[3 * i : 3 * i + 4],
                    )
                    for i, (low, high) in enumerate(zip(breaks, breaks[1:]))
                )
            else:
                raise ValueError("Unknown original material region")
        for low, high, points in intervals:
            # Preserve the original polynomial on its intersection with the material domain.
            start, end = max(Fraction(0), low), min(length, high)
            if start >= end:
                continue
            work.take()
            if start != low or end != high:
                axes = tuple(
                    restrict(
                        tuple(p[k] for p in points),
                        (start - low) / (high - low),
                        (end - low) / (high - low),
                    )
                    for k in range(3)
                )
                points = tuple(tuple(axis[i] for axis in axes) for i in range(len(points)))
            spans.append(DistanceSpan(start, end, points))
    return measure(tuple(spans), length, work.checkpoint)


def labels(plan: RibbonPlan) -> dict[ConductorKey, tuple[Fraction, Fraction, Fraction]]:
    """
    Require matching original root labels at both ends before measuring any trunk path.
    """
    output = {}
    for branch in plan.branches:
        if branch.source.attachment.attachment_id != branch.source.root_attachment_id:
            continue
        sections = tuple(patch.section for patch in branch.patches[0])
        left, right = traces(sections)
        center = Fraction(sections[0].center_q_mm)
        values = (center + left.root_q_mm, center, center + right.root_q_mm)
        key = branch.source.conductor
        if key in output and output[key] != values:
            raise ValueError("Opposite original roots disagree on trunk material labels")
        output[key] = values
    if set(output) != set(plan.captured.conductors):
        raise ValueError("Every conductor needs original trunk root labels")
    return output


@dataclass(frozen=True)
class TrunkPathMetric:
    """
    Keep the original trunk, label and complete per-piece measured controls together.
    """

    route: FoldRoute
    q_mm: Fraction
    pieces: tuple[MaterialDistanceAudit, ...]
    upper_mm: Fraction
    piece_join_gaps_upper_mm: tuple[Fraction, ...]


@dataclass(frozen=True)
class TrunkMetricAudit:
    """
    Retain actual planned path bounds without clearing seam/native/full-material qualifications.
    """

    plan: RibbonPlan
    paths: tuple[TrunkPathMetric, ...]
    conductors: tuple[TrunkDiscrepancy, ...]
    prefix_residuals_mm: tuple[Fraction, ...]


def audit(plan: RibbonPlan, work: TrunkMetricWork) -> TrunkMetricAudit:
    """
    Bound every required path pair through all original trunk pieces once.

    Each label's absolute local speed errors add before pairwise comparison,
    without cancellation or per-piece slack. All pieces use common physical
    local distance, never common bend phase. Recorded source prefix roundoff and
    spatial seam gaps do not disappear and do not imply a joined material map.
    These receipts qualify planned piecewise longitudinal metrics only.
    """
    work.checkpoint()
    route = plan.trunk.route
    if route is None or plan.unattempted_route_ids or route.targets != plan.captured.trunk:
        raise ValueError("A complete original trunk and all original endings are required")
    ordered = labels(plan)
    unique = sorted({q for values in ordered.values() for q in values})
    if any(abs(q) > Fraction(route.half_width_mm) for q in unique):
        raise ValueError("Captured root label lies outside the original trunk domain")
    paths = []
    for q in unique:
        measured = tuple(piece_path(piece, q, work) for piece in route.pieces)
        joins = tuple(
            distance(a.spans[-1].source.controls[-1], b.spans[0].source.controls[0])[1]
            for a, b in zip(measured, measured[1:])
        )
        paths.append(
            TrunkPathMetric(
                route, q, measured, sum((r.upper_mm for r in measured), Fraction(0)), joins
            )
        )
    by_q = {path.q_mm: path for path in paths}
    findings = []
    for conductor, coordinates in ordered.items():
        values = sorted((by_q[q].upper_mm for q in coordinates), reverse=True)
        findings.append(
            TrunkDiscrepancy(
                plan.captured,
                conductor,
                values[0] + values[1],
                "source-owned Hermite controls on original piecewise material-distance charts",
            )
        )
    lengths = tuple(Fraction(piece.geometry.material_length_mm) for piece in route.pieces)
    prefixes = tuple(
        Fraction(start) - sum(lengths[:i], Fraction(0)) for i, start in enumerate(route.starts_mm)
    )
    return TrunkMetricAudit(plan, tuple(paths), tuple(findings), prefixes)
