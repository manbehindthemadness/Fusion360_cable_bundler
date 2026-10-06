"""
Protect local intersection, exact cap and collateral-review contracts without Fusion.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.section_comparison import comparison_findings
from experiments.experiment_ribbon_cap_transition.section_sampling import (
    SectionSamplingRejected,
    sample_section_planes,
    section_metrics,
)
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame
from experiments.experiment_secure_discrete_ribbon.shape import RibbonEndFit, RibbonShape


def _shape(xs: tuple[float, ...] = (0, 1.2, 2.2, 3)) -> RibbonShape:
    """
    Make two ordered source lanes with fixed caps and offset interior samples.
    """
    frames = tuple(
        RibbonFrame(Vector3(i, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1))
        for i in range(4)
    )
    lanes = tuple(tuple(Vector3(x, y, 0) for x in xs) for y in (0, 1.5))
    fits = tuple(
        RibbonEndFit(
            tuple(lane[i] for lane in lanes),
            (Vector3(0, 0, 1),) * 2,
            approach_normal=Vector3(1, 0, 0),
        )
        for i in (0, -1)
    )
    return RibbonShape(frames, lanes, (3, 3), 0, False, 1, fits[0], fits[1])


def test_intersections_preserve_caps_identity_and_source_segment_coordinates() -> None:
    """
    Remove longitudinal station mismatch without moving targets or mutating input.
    """
    original = _shape()
    sampled = sample_section_planes(original, 1.5)
    assert original == _shape()
    assert sampled.shape.frames is original.frames
    assert sampled.shape.start_fit is original.start_fit
    assert sampled.shape.end_fit is original.end_fit
    assert sampled.source_parameters[0] == pytest.approx((0, 1 / 1.2, 1.8, 3))
    for source, lane in zip(original.lanes, sampled.shape.lanes):
        assert lane[0] is source[0] and lane[-1] is source[-1]
        assert tuple(point.x for point in lane) == pytest.approx((0, 1, 2, 3))
        assert all(point.y == source[0].y for point in lane)
    assert sampled.maximum_same_index_displacement_mm == pytest.approx(0.2)
    assert section_metrics(sampled.shape, 1.5)["maximum_center_off_plane_mm"] < 1e-12


def test_already_planar_samples_are_unchanged_and_vertex_hits_are_not_ambiguous() -> None:
    """
    Deduplicate the same vertex shared by both local source segments.
    """
    shape = _shape((0, 1, 2, 3))
    sampled = sample_section_planes(shape, 1.5)
    assert sampled.shape == shape
    assert sampled.source_parameters == ((0, 1, 2, 3),) * 2
    assert sampled.maximum_same_index_displacement_mm == 0


@pytest.mark.parametrize(
    "xs,reason",
    [
        ((0, 0.1, 0.2, 3), "0 local crossings"),
        ((0, 2, 0, 3), "2 local crossings"),
        ((0, 1, 1, 3), "coplanar source segment"),
    ],
)
def test_missing_and_ambiguous_local_crossings_do_not_project_or_fallback(
    xs: tuple[float, ...], reason: str
) -> None:
    """
    Reject even when a remote segment could intersect the requested plane.
    """
    with pytest.raises(SectionSamplingRejected, match=reason):
        sample_section_planes(_shape(xs), 1.5)


def test_reversed_station_traversal_and_nonplanar_caps_are_rejected() -> None:
    """
    Preserve lane traversal and never repair the authoritative endpoint sample.
    """
    shape = _shape((0, 1, 2, 3))
    frames = list(shape.frames)
    frames[1] = replace(frames[1], origin=Vector3(2, 0, 0))
    frames[2] = replace(frames[2], origin=Vector3(1, 0, 0))
    with pytest.raises(SectionSamplingRejected, match="traversal reversed"):
        sample_section_planes(replace(shape, frames=tuple(frames)), 1.5)
    with pytest.raises(SectionSamplingRejected, match="fixed cap"):
        sample_section_planes(_shape((0.1, 1, 2, 3)), 1.5)


def test_nonfinite_input_is_not_reported_as_geometry_rejection() -> None:
    """
    Distinguish malformed source data from a finite unsuccessful intersection.
    """
    with pytest.raises(ValueError, match="finite"):
        sample_section_planes(_shape((0, float("nan"), 2, 3)), 1.5)


def test_regression_comparison_keeps_findings_separate_from_length_goals() -> None:
    """
    Detect new findings and worsening radius even in an already-rejected case.
    """
    baseline = {
        "status": "reject",
        "failures": ["old"],
        "source_shape": {},
        "preflight": {"occupied_and_lane_checks": {"sampled_whole_lane_minimum_radius_mm": 2.0}},
    }
    candidate = {
        "status": "reject",
        "failures": ["old", "new"],
        "source_shape": {},
        "preflight": {
            "warnings": ["trunk_lane_length_spread"],
            "occupied_and_lane_checks": {"sampled_whole_lane_minimum_radius_mm": 1.9},
        },
    }
    assert comparison_findings(baseline, candidate) == [
        "new",
        "worsened:sampled_whole_lane_minimum_radius_mm",
    ]
    assert comparison_findings(baseline, baseline) == []


def test_lost_samples_and_source_solve_drift_trigger_review() -> None:
    """
    Do not disguise failure to construct numerical sections as an unresolved pass.
    """
    baseline = {"status": "unresolved", "failures": [], "source_shape": {"fixed": True}}
    candidate = {"status": "rule_rejected", "failures": [], "source_shape": {"fixed": True}}
    assert comparison_findings(baseline, candidate) == ["candidate_lost_baseline_section_samples"]
    candidate["source_shape"] = {"fixed": False}
    assert "unchanged_source_solve_drift" in comparison_findings(baseline, candidate)


def test_worsening_spacing_stops_even_when_compression_already_failed() -> None:
    """
    Protect the per-mechanic stop that the first comparison failed to implement.
    """
    baseline = {
        "status": "reject",
        "failures": ["sampled_section_neighbor_compression"],
        "section_metrics": {
            "minimum_neighbor_pitch_ratio": 0.984,
            "maximum_neighbor_pitch_ratio": 1.026,
        },
    }
    candidate = {
        "status": "reject",
        "failures": ["sampled_section_neighbor_compression"],
        "section_metrics": {
            "minimum_neighbor_pitch_ratio": 0.978,
            "maximum_neighbor_pitch_ratio": 1.026,
        },
    }
    assert comparison_findings(baseline, candidate) == ["worsened:minimum_neighbor_pitch_ratio"]
