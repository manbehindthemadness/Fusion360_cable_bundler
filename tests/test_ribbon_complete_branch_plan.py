"""
Verify whole frozen-branch assembly without counting analytical fixtures as geometry coverage.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Literal
from uuid import UUID

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.branch_plan import SpatialBranchPlan, assemble
from experiments.experiment_ribbon_complete.capture import capture
from experiments.experiment_ribbon_complete.contracts import BranchPlan, CompleteRibbonInput
from experiments.experiment_ribbon_complete.root_profiles import (
    CapFrame,
    RootProfile,
    bind_frame,
    partition,
)
from experiments.experiment_ribbon_complete.spatial_frame import ChartOrientation, FrameSpan
from tests.test_ribbon_complete_capture import inputs
from tests.test_ribbon_complete_lengths import checkpoint

Y, Z = Vector3(0, 1, 0), Vector3(0, 0, 1)
Data = tuple[CompleteRibbonInput, BranchPlan, RootProfile, float, CapFrame, tuple[FrameSpan, ...]]


def data(side: Literal["start", "end"] = "start", split: bool = False) -> Data:
    """
    Retain the existing synthetic fixture's exact captured3mm branch, identity and target poses.
    """
    complete = capture(*inputs())
    index = 0 if side == "start" else 1
    connection = complete.group.connection_ids[index]
    source = next(
        b
        for b in complete.branches
        if b.source.leg.start_connection_id == connection and b.conductor.pin_number == 1
    )
    port = complete.caps[index]
    cap = bind_frame(complete.trunk, side, port.target.point, port.target.tangent)
    root = partition(2, 0.75)[0]
    curve = source.source.route.curves[0]
    center = (curve.end, curve.control_b, curve.control_a, curve.start)
    orientation = ChartOrientation.NEGATIVE if index == 0 else ChartOrientation.POSITIVE
    if split:
        a, b = center[0], center[-1]
        middle = Vector3((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2)
        frames = (
            FrameSpan(Fraction(0), Fraction(1, 2), (a, middle), (Y,), (Z,), orientation),
            FrameSpan(Fraction(1, 2), Fraction(1), (middle, b), (Y,), (Z,), orientation),
        )
    else:
        frames = (FrameSpan(Fraction(0), Fraction(1), center, (Y,), (Z,), orientation),)
    return complete, source, root, -0.375, cap, frames


def planned(values: Data) -> SpatialBranchPlan:
    """
    Assemble only the unchanged source branch under the shared caller checkpoint.
    """
    complete, source, root, center, cap, frames = values
    return assemble(complete, source.source.leg.route_id, root, center, cap, frames, checkpoint)


def with_frames(values: Data, frames: tuple[FrameSpan, ...]) -> Data:
    """
    Replace only the supplied frame sequence while retaining the complete typed input.
    """
    return values[0], values[1], values[2], values[3], values[4], frames


@pytest.mark.parametrize("side", ("start", "end"))
def test_branch_preserves_identity_reference_targets_and_missing_physical_checks(
    side: Literal["start", "end"],
) -> None:
    """
    Round ends and coordinates can pass while material/native acceptance remains explicitly outstanding.
    """
    values = data(side)
    result = planned(values)
    assert result.source is values[1]
    assert result.source.source.route is values[1].source.route
    assert all(p.status == "certified" for p in result.coordinates + result.terminations)
    assert result.center_error_squared_mm2 == Fraction(0)
    assert "material_metrics" in result.outstanding and "native_junctions" in result.outstanding
    assert "termination_correspondence" not in result.outstanding
    assert result.source.association_ids == values[1].association_ids


def test_shared_spans_keep_one_global_morph_and_exact_source_jet_continuity() -> None:
    """
    Reversed preview traversal and split frame intervals preserve the same full curve.
    """
    result = planned(data(split=True))
    assert len(result.patches) == 2 and result.center_error_squared_mm2 == Fraction(0)
    assert all(seam.first_jets_equal and seam.second_jets_equal for seam in result.seams)
    assert "span_jet_continuity" not in result.outstanding


def test_missing_global_interval_is_not_reordered_or_filled() -> None:
    """
    Refuse a gap in the supplied span partition before geometry qualification.
    """
    values = data(split=True)
    first, second = values[-1]
    with pytest.raises(ValueError, match="share intervals"):
        planned(with_frames(values, (first, replace(second, low=Fraction(3, 4)))))


def test_an_open_material_source_seam_is_not_snapped_within_dimensional_tolerance() -> None:
    """
    A discontinuous source chart cannot acquire a valid material coordinate by a small-gap waiver.
    """
    values = data(split=True)
    first, second = values[-1]
    moved = second.center[0].translated(Y, 0.001)
    with pytest.raises(ValueError, match="open source seam"):
        planned(with_frames(values, (first, replace(second, center=(moved, second.center[-1])))))


def test_source_derivative_mismatch_and_curve_displacement_stay_unqualified() -> None:
    """
    A closed but differently parameterized/bent span cannot inherit continuity or reference acceptance.
    """
    values = data(split=True)
    first, second = values[-1]
    middle = Vector3(-2, -0.375, 0)
    result = planned(
        with_frames(
            values, (first, replace(second, center=(second.center[0], middle, second.center[-1])))
        )
    )
    assert "span_jet_continuity" in result.outstanding
    assert "centerline_correspondence" in result.outstanding


def test_scaled_terminal_frame_is_not_accepted_as_the_prescribed_circle() -> None:
    """
    A positive coordinate chart does not hide a changed termination radius.
    """
    values = data()
    original = values[-1][0]
    scaled = replace(original, width=(Y,) * 3 + (Vector3(0, 2, 0),) * 3)
    result = planned(with_frames(values, (scaled,)))
    assert all(c.status == "certified" for c in result.coordinates)
    assert "termination_correspondence" in result.outstanding


def test_correct_round_section_does_not_waive_wrong_boundary_approach() -> None:
    """
    Native pose coincidence alone cannot establish flow across the entire termination.
    """
    values = data()
    original = values[-1][0]
    moving = replace(original, thickness=(Z,) * 4 + (Vector3(0, 0.2, 1), Z))
    result = planned(with_frames(values, (moving,)))
    assert all(p.distance_upper_mm <= Fraction(1, 100) for p in result.terminations)
    assert "termination_correspondence" in result.outstanding


def test_axial_and_radial_errors_share_one_dimensional_allowance() -> None:
    """
    Two separate0.009mm deviations do not each receive an independent0.01mm acceptance budget.
    """
    values = data()
    original = values[-1][0]
    center = original.center[:-1] + (original.center[-1].translated(Vector3(-1, 0, 0), 0.009),)
    changed = replace(original, center=center, width=(Y,) * 3 + (Vector3(0, 1.024, 0),) * 3)
    result = planned(with_frames(values, (changed,)))
    assert "termination_correspondence" in result.outstanding
    assert any(p.distance_upper_mm > Fraction(1, 100) for p in result.terminations)


def test_unknown_route_identity_cannot_select_another_conductor() -> None:
    """
    Geometric similarity cannot replace persistent branch identity.
    """
    complete, _source, root, center, cap, frames = data()
    with pytest.raises(ValueError, match="captured branch"):
        assemble(complete, UUID(int=999999), root, center, cap, frames, checkpoint)
