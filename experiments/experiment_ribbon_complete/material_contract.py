"""
Bind the required longitudinal metrics to persistent left/center/right atlas trajectories.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .collared_transport import MaterialLabel, collar, evaluate, label
from .material_atlas import MaterialAtlas, validate
from .material_traces import MidlineAudit, traces
from .spatial_transition import SpatialPatch

Controls = tuple[tuple[Fraction, ...], ...]


def boundary_controls(patch: SpatialPatch, coordinate: Fraction) -> Controls:
    """
    Retain the complete rational world trajectory at one exact original edge label.
    """
    return tuple(
        tuple(evaluate(tuple(p[k] for p in row), coordinate) for k in range(4))
        for row in patch.rows
    )


@dataclass(frozen=True)
class MaterialPathContract:
    """
    Retain atlas, metric receipt and three exact trajectories without claiming whole material compliance.

    Labels and controls are ordered left/center/right. Span controls use each
    original frame's local parameter and homogeneous world coordinates. The
    inherited metric bound covers every corresponding local interval and totals.
    No inverse approximation is used to choose the source material paths.
    """

    atlas: MaterialAtlas
    midline: MidlineAudit
    labels: tuple[MaterialLabel, MaterialLabel, MaterialLabel]
    span_controls: tuple[tuple[Controls, Controls, Controls], ...]
    status: str


def bind(
    atlas: MaterialAtlas, midline: MidlineAudit, checkpoint: Callable[[], None]
) -> MaterialPathContract:
    """
    Connect existing longitudinal bounds to the same certified source-material map exactly.

    T(u,s=1,v)=P(u,v) and T(u,s=0,v)=0 for the stored collar policy.
    Therefore required boundary labels and the canonical center have precisely
    the world trajectories already measured against C. Canonical seam ownership
    must preserve the entire homogeneous control curve, not only sampled points.
    One accumulated0.01mm metric allowance is inherited, with no per-span slack.

    The caller supplies the original immutable MidlineAudit, such as the receipt
    retained by an actual branch-length measurement. Ownership, exact trace/patch
    correspondence and bound accounting are checked; receipt construction remains
    the responsibility of material_traces.audit. No extra measurement allocation
    is created here. Unresolved metric evidence stays unresolved; incomplete or
    stale receipts reject. Transverse metric compatibility, physical curvature,
    contact, junctions and native fidelity are separate outstanding requirements.
    """
    validate(atlas, checkpoint)
    plan = atlas.plan
    if midline.plan is not plan:
        raise ValueError("Material metrics must retain the same original atlas plan")
    left, right = traces(atlas.geometry.transverse.sections)
    if (midline.left, midline.right) != (left, right) or len(midline.spans) != len(plan.patches):
        raise ValueError("Complete original midline trace and span coverage is required")
    if collar(Fraction(0)) != Fraction(0) or collar(Fraction(1)) != Fraction(1):
        raise ValueError("Stored transport policy does not preserve center/boundary trajectories")
    points = (
        label(plan, left.edge_index, left.coordinate, Fraction(1)),
        label(plan, 0, Fraction(0), Fraction(0)),
        label(plan, right.edge_index, right.coordinate, Fraction(1)),
    )
    output = []
    accumulated: Fraction | None = Fraction(0)
    for span, proofs in zip(plan.patches, midline.spans):
        checkpoint()
        if len(proofs) != 2:
            raise ValueError("Both ordered side-path bounds are required on every span")
        side_controls = []
        for trace, point, proof in zip((left, right), (points[0], points[2]), proofs):
            patch = span[trace.edge_index]
            if proof.patch is not patch or proof.edge_coordinate != trace.coordinate:
                raise ValueError(
                    "Material metric receipt has stale or mislabelled trajectory provenance"
                )
            original = boundary_controls(patch, trace.coordinate)
            canonical = boundary_controls(span[point.edge_index], point.edge_coordinate)
            if original != canonical:
                raise ValueError("Canonical source label changes the measured world trajectory")
            side_controls.append(canonical)
            bound = proof.discrepancy_upper_mm
            if bound is not None and bound < Fraction(0):
                raise ValueError("A material discrepancy upper bound cannot be negative")
            if bound is None:
                accumulated = None
            elif accumulated is not None:
                accumulated += bound
        fields = span[0].frame.fields()[0]
        center = tuple(
            tuple(field[i] for field in fields) + (Fraction(1),) for i in range(len(fields[0]))
        )
        output.append((side_controls[0], center, side_controls[1]))
    state = (
        "certified" if accumulated is not None and accumulated <= Fraction(1, 100) else "unresolved"
    )
    if midline.pairwise_upper_mm != accumulated or midline.status != state:
        raise ValueError("Material metric receipt has inconsistent complete-path bound accounting")
    return MaterialPathContract(
        atlas,
        midline,
        points,
        tuple(output),
        "certified_corresponding_midlines" if state == "certified" else "unresolved",
    )
