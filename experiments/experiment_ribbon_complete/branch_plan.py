"""
Assemble immutable spatial branches while retaining captured identity and outstanding physical gates.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from uuid import UUID

from .branch_reference import SpanSeam, center_error_squared, validate_spans
from .branch_terminal import TerminalCertificate
from .branch_terminal import certify as certify_terminal
from .contracts import BranchPlan, CompleteRibbonInput
from .profile_transition import TransitionTiming, build
from .root_profiles import CapFrame, RootProfile
from .spatial_certificate import CoordinateCertificate
from .spatial_certificate import certify as certify_coordinates
from .spatial_frame import FrameSpan
from .spatial_transition import SpatialPatch, bind_root, compose


@dataclass(frozen=True)
class SpatialBranchPlan:
    """
    Keep the same frozen geometry for authoring/audits without a whole-branch success flag.

    Patches follow supplied span order then source profile-edge order. Source
    attachment, conductor, associations and routing controls remain unchanged.
    Captured branch previews traverse terminal-to-cap; this plan reverses only
    traversal, not persistent material identities.
    """

    source: BranchPlan
    patches: tuple[tuple[SpatialPatch, ...], ...]
    seams: tuple[SpanSeam, ...]
    coordinates: tuple[CoordinateCertificate, ...]
    terminations: tuple[TerminalCertificate, ...]
    center_error_squared_mm2: Fraction
    outstanding: tuple[str, ...]


def assemble(
    complete: CompleteRibbonInput,
    route_id: UUID,
    root: RootProfile,
    root_center_q_mm: float,
    cap: CapFrame,
    frames: tuple[FrameSpan, ...],
    checkpoint: Callable[[], None],
    *,
    timing: TransitionTiming = TransitionTiming.QUINTIC,
) -> SpatialBranchPlan:
    """
    Bind a complete captured branch to explicit frames and an already-qualified native root.

    Root ownership/source receipt validation belongs to the caller before this
    geometric step. Missing native/material/contact checks always remain listed.
    Unresolved coefficient bounds are retained rather than turned into failures
    or silently repaired. Shared caller time/memory limits cover all nested work.
    """
    matches = [branch for branch in complete.branches if branch.source.leg.route_id == route_id]
    if len(matches) != 1 or root.pin_number != matches[0].conductor.pin_number:
        raise ValueError("One captured branch and its original conductor root are required")
    branch = matches[0]
    seams = validate_spans(frames, checkpoint)
    diameter = branch.source.leg.diameter_mm
    radius = (complete.group.diameter_mm if diameter is None else diameter) / 2
    sections = build(root, root_center_q_mm, radius, timing=timing)
    patches = tuple(
        tuple(compose(section, frame, checkpoint) for section in sections) for frame in frames
    )
    coordinates = []
    for span in patches:
        for patch in span:
            checkpoint()
            coordinates.append(certify_coordinates(patch, checkpoint))
    for patch in patches[0]:
        bind_root(patch, cap)
    terminations = tuple(
        certify_terminal(patch, branch.source.terminal, checkpoint) for patch in patches[-1]
    )
    error = center_error_squared(frames, branch.source.route, checkpoint)
    outstanding = [
        "material_metrics",
        "complete_path_lengths",
        "curvature",
        "contact",
        "interior_ownership",
        "native_fidelity",
        "native_junctions",
    ]
    if error > Fraction(1, 100) ** 2:
        outstanding.append("centerline_correspondence")
    if any(not seam.first_jets_equal or not seam.second_jets_equal for seam in seams):
        outstanding.append("span_jet_continuity")
    if any(proof.status != "certified" for proof in coordinates):
        outstanding.append("coordinate_regularity")
    if any(proof.status != "certified" for proof in terminations):
        outstanding.append("termination_correspondence")
    return SpatialBranchPlan(
        branch, patches, seams, tuple(coordinates), terminations, error, tuple(outstanding)
    )
