"""
Audit geometric branch bending while retaining material, native and junction qualifications separately.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, multiply
from devtools.ribbon_analysis.pinch import PinchLimit

from .branch_plan import SpatialBranchPlan
from .branch_reference import validate_patches, validate_spans
from .curve_lengths import bounds
from .material_paths import square_root_lower
from .ruled_support import SupportBound, enclose
from .spatial_certificate import certify as certify_coordinates
from .spatial_certificate import cross, dot
from .spatial_frame import FrameSpan, components, differentiated


@dataclass(frozen=True)
class LateralBound:
    """
    Keep center wide-axis curvature and a dimensional comparison bound without a new angular tolerance.
    """

    frame: FrameSpan
    exact_zero: bool
    curvature_upper_per_mm: Fraction | None
    center_length_upper_mm: Fraction


def lateral(frame: FrameSpan) -> LateralBound:
    """
    Bound the curvature component toward the projected original width direction.

    Numerator is (C'' dot W)|C'|²-(C' dot C'')(C' dot W). Its
    denominator is |C'|³*|C' cross W|, so varying parameter speed or
    nonorthogonal raw axes do not manufacture a lateral bend. Exact zero is a
    useful identity, not a tighter physical distance acceptance requirement.
    """
    center, width, _ = frame.fields()
    velocity = differentiated(center)
    acceleration = differentiated(velocity)
    speed_squared = dot(velocity, velocity)
    normal = cross(velocity, width)
    normal_squared = dot(normal, normal)
    residual = add(
        multiply(dot(acceleration, width), speed_squared),
        multiply(dot(velocity, acceleration), dot(velocity, width)),
        Fraction(-1),
    )
    low_e, low_d = min(speed_squared), min(normal_squared)
    root_e = square_root_lower(low_e) if low_e > Fraction(0) else Fraction(0)
    root_d = square_root_lower(low_d) if low_d > Fraction(0) else Fraction(0)
    controls = tuple(zip(*components(frame.center)))
    length = bounds(controls)[1]
    curvature = (
        max(abs(x) for x in residual) / (low_e * root_e * root_d)
        if root_e > Fraction(0) and root_d > Fraction(0)
        else None
    )
    return LateralBound(frame, not any(residual), curvature, length)


@dataclass(frozen=True)
class BranchBendAudit:
    """
    Retain the same geometry and named support checks without a full physical success flag.
    """

    plan: SpatialBranchPlan
    supports: tuple[SupportBound, ...]
    lateral_bounds: tuple[LateralBound, ...]
    principal_reach_status: str
    normal_field_status: str
    coordinate_status: str
    lateral_status: str
    lateral_excursion_upper_mm: Fraction | None


def audit(plan: SpatialBranchPlan, checkpoint: Callable[[], None]) -> BranchBendAudit:
    """
    Measure actual support curvature, thickness correspondence and center wide-axis bending.

    The existing99.6% normal-offset regularity buffer remains dimensionless; it
    protects invertible thickness coordinates, not a new dimensional tolerance.
    Normal-field displacement and lateral geometric effect use one inclusive
    0.01mm allowance. No native, interior isometry, contact or junction claim follows.

    For lateral effect, remove only the tangent/width coupling from the orthonormal
    moving-frame angular-rate matrix. Both frame flows are orthogonal, so tangent
    error is at most the accumulated removed curvature; position error is at most
    L²*k/2 at center. Section points add at most R*L*k, where R encloses
    their distance from center; raw vector scale and shear are retained. This
    bounds departure from that no-lateral comparison for every interval,
    without changing actual targets or geometry. Sum physical length across spans
    before applying the bound once; source C1 continuity is required for this proof.
    """
    frames = validate_patches(plan.patches, checkpoint)
    supports, lateral_bounds = [], []
    coordinate_ok = True
    for span, frame in zip(plan.patches, frames):
        checkpoint()
        q_values, b_values = [], []
        for patch in span:
            proof = certify_coordinates(patch, checkpoint)
            coordinate_ok = coordinate_ok and proof.status == "certified"
            q_values.extend(p[0] / p[2] for row in patch.section_rows for p in row)
            b_values.extend(abs(p[1] / p[2]) for row in patch.section_rows for p in row)
        supports.append(enclose(frame, (min(q_values), max(q_values)), max(b_values)))
        lateral_bounds.append(lateral(frame))
        checkpoint()
    limit = Fraction(PinchLimit().fraction)
    reach_ok = all(
        row.principal_upper_per_mm is not None
        and row.principal_upper_per_mm * row.physical_half_thickness_upper_mm <= limit
        for row in supports
    )
    normal_ok = all(
        row.normal_distance_upper_mm is not None
        and row.normal_distance_upper_mm <= Fraction(1, 100)
        for row in supports
    )
    seams = validate_spans(frames, checkpoint)
    total_length = sum((row.center_length_upper_mm for row in lateral_bounds), Fraction(0))
    rates = [row.curvature_upper_per_mm for row in lateral_bounds]
    excursion = None
    if all(seam.first_jets_equal for seam in seams) and all(rate is not None for rate in rates):
        reach = max(row.transverse_reach_upper_mm for row in supports)
        excursion = (total_length**2 / 2 + reach * total_length) * max(
            rate for rate in rates if rate is not None
        )
    return BranchBendAudit(
        plan,
        tuple(supports),
        tuple(lateral_bounds),
        "certified" if reach_ok else "unresolved",
        "certified" if normal_ok else "unresolved",
        "certified" if coordinate_ok else "unresolved",
        "certified" if excursion is not None and excursion <= Fraction(1, 100) else "unresolved",
        excursion,
    )
