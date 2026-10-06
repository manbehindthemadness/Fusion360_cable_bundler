"""
Check cap-policy isolation, fixed targets, per-lane corrections and unchanged guards.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from cable_bundler.routing.geometry import CubicBezier, Vector3, cross, dot, unit
from cable_bundler.routing.parallel import RoutePreview
from experiments.experiment_ribbon_cap_transition.ends import (
    SmoothCapTransition,
    align_branch_cap,
    cap_direction,
    correction_weights,
)
from experiments.experiment_ribbon_cap_transition.planning import prepare_candidate
from experiments.experiment_ribbon_cap_transition.screen import screen_cases
from experiments.experiment_ribbon_cap_transition.solver import solve_candidate
from experiments.experiment_ribbon_diagnosis.compact import compact_cases
from experiments.experiment_ribbon_diagnosis.inputs import analytic_guide_frame
from experiments.experiment_ribbon_diagnosis.spatial import spatial_cases
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon, certify_curvature
from experiments.experiment_secure_discrete_ribbon.end_boundary import EndBoundary
from experiments.experiment_secure_discrete_ribbon.frames import ribbon_frames
from experiments.experiment_secure_discrete_ribbon.shape import (
    RibbonEndFit,
    _blend_end_fit,
    solve_ribbon_shape,
)


def cap_fit(case: RibbonStressCase, at_start: bool) -> RibbonEndFit:
    """
    Author fixed ordered straight-guide centers from exact fixture inputs.
    """
    frame = analytic_guide_frame(case, at_start)
    return RibbonEndFit(
        tuple(
            frame.origin.translated(frame.width, (i - (case.lines - 1) / 2) * case.diameter_mm)
            for i in range(case.lines)
        ),
        (frame.thickness,) * case.lines,
        approach_normal=frame.tangent,
    )


@pytest.mark.parametrize("case", spatial_cases(), ids=lambda case: case.name)
def test_explicit_tangents_preserve_cap_width_and_lane_order(case: RibbonStressCase) -> None:
    """
    Align both endpoint frames before transport across the retained spatial families.
    """
    tangents = (case.route.curves[0].derivative(0), case.route.curves[-1].derivative(1))
    candidate = ribbon_frames(
        case.route, case.start_width, case.end_width, endpoint_tangents=tangents
    )
    baseline = ribbon_frames(case.route, case.start_width, case.end_width)
    assert len(candidate) == len(baseline) == 32
    assert tuple(frame.origin for frame in candidate) == tuple(frame.origin for frame in baseline)
    for index, tangent, width in (
        (0, tangents[0], case.start_width),
        (-1, tangents[1], case.end_width),
    ):
        assert dot(candidate[index].tangent, unit(tangent)) == pytest.approx(1)
        assert dot(candidate[index].width, unit(width)) == pytest.approx(1)
        assert dot(candidate[index].thickness, unit(cross(tangent, width))) == pytest.approx(1)
    assert ribbon_frames(case.route, case.start_width, case.end_width) == baseline


@pytest.mark.parametrize("at_start", (True, False))
def test_each_lane_corrects_its_own_slope_without_a_shared_middle_lane_bias(at_start: bool) -> None:
    """
    Preserve reflection symmetry, endpoints, ordering and all samples beyond support.
    """
    distances = (0.0, 1.0, 3.0, 10.0, 97.0, 99.0, 100.0)
    lanes = tuple(tuple(Vector3(s, sign * (1 + 0.1 * s), 0) for s in distances) for sign in (-1, 1))
    index = 0 if at_start else -1
    fit = RibbonEndFit(
        tuple(lane[index] for lane in lanes),
        (Vector3(0, 0, 1),) * 2,
        approach_normal=Vector3(1, 0, 0),
    )
    policy = SmoothCapTransition()
    corrected = policy.blend(lanes, fit, at_start=at_start, distances_mm=distances, lead_mm=10.0)
    historical = _blend_end_fit(lanes, fit, at_start=at_start, distances_mm=distances, lead_mm=10.0)
    reversed_fit = replace(fit, centers=tuple(reversed(fit.centers)))
    reversed_result = policy.blend(
        tuple(reversed(lanes)),
        reversed_fit,
        at_start=at_start,
        distances_mm=distances,
        lead_mm=10.0,
    )
    assert corrected == tuple(reversed(reversed_result))
    assert corrected != historical
    assert tuple(lane[index] for lane in corrected) == fit.centers
    for a, b in zip(*corrected):
        assert a.x == pytest.approx(b.x)
        assert a.y == pytest.approx(-b.y)
    for offset, distance in enumerate(distances):
        if (distance if at_start else 100 - distance) >= 10:
            assert tuple(lane[offset] for lane in corrected) == tuple(
                lane[offset] for lane in lanes
            )


def test_quintic_correction_adds_no_boundary_curvature() -> None:
    """
    Check physical first and second derivatives at each side of the support.
    """
    lead, step = 10.0, 0.0001
    assert correction_weights(0, lead) == (1.0, 0.0)
    assert correction_weights(lead, lead) == correction_weights(lead + 1, lead) == (0.0, 0.0)
    for boundary, sign, first_expected in ((0.0, 1, (0.0, 1.0)), (lead, -1, (0.0, 0.0))):
        values = [correction_weights(boundary + sign * i * step, lead) for i in range(3)]
        for component in (0, 1):
            first = (
                -3 * values[0][component] + 4 * values[1][component] - values[2][component]
            ) / (2 * sign * step)
            second = (
                values[0][component] - 2 * values[1][component] + values[2][component]
            ) / step**2
            assert first == pytest.approx(first_expected[component], abs=1e-7)
            assert second == pytest.approx(0, abs=0.0001)


def test_branch_alignment_keeps_connection_target_and_its_exact_orientation() -> None:
    """
    Change only the cap handle, retaining route identity and all earlier spans.
    """
    first = CubicBezier(*(Vector3(x, 0, 0) for x in (-30, -20, -10, 0)))
    last = CubicBezier(Vector3(0, 0, 0), Vector3(10, 0, 0), Vector3(20, 1, 0), Vector3(30, 0, 0))
    route = RoutePreview(
        UUID(int=1), "fixed branch", (first.start, first.end, last.end), (first, last)
    )
    aligned = align_branch_cap(route, Vector3(1, 0, 0))
    assert aligned.cable_id == route.cable_id and aligned.cable_number == route.cable_number
    assert aligned.points == route.points
    assert aligned.curves[0] == first
    assert aligned.curves[-1].start == last.start
    assert aligned.curves[-1].control_a == last.control_a
    assert aligned.curves[-1].end == last.end
    assert aligned.curves[0].derivative(0) == route.curves[0].derivative(0)
    assert dot(unit(aligned.curves[-1].derivative(1)), Vector3(1, 0, 0)) == pytest.approx(1)
    assert certify_curvature(aligned, 1.0).maximum_ratio <= 0.8
    with pytest.raises(ValueError, match="reverse"):
        align_branch_cap(route, Vector3(-1, 0, 0))


def straight_case() -> RibbonStressCase:
    """
    Supply a gentle control independent of the spatial diagnostic failures.
    """
    curve = CubicBezier(*(Vector3(x, 0, 0) for x in (0, 100 / 3, 200 / 3, 100)))
    route = RoutePreview(UUID(int=2), "straight cap control", (curve.start, curve.end), (curve,))
    return replace(
        compact_cases()[0],
        name="straight cap control",
        route=route,
        lines=19,
        diameter_mm=1.5,
        end_boundary=EndBoundary(Vector3(50, 0, 0), 142.5),
    )


def test_candidate_keeps_straight_control_and_historical_procedure_unchanged() -> None:
    """
    Preserve equal lanes while bounding support without adding folds or sections.
    """
    case = straight_case()
    start, end = cap_fit(case, True), cap_fit(case, False)
    frames = ribbon_frames(case.route, case.start_width, case.end_width)
    baseline = solve_ribbon_shape(
        frames, case.lines, case.diameter_mm, start_fit=start, end_fit=end
    )
    candidate = solve_candidate(case, start, end)
    assert candidate.lanes == baseline.lanes
    assert candidate.lengths_mm == (100.0,) * case.lines
    assert candidate.meets_length_target and not candidate.folded
    assert candidate.end_lead_mm == 0.0
    assert baseline.end_lead_mm == 28.5
    assert (
        solve_ribbon_shape(frames, case.lines, case.diameter_mm, start_fit=start, end_fit=end)
        == baseline
    )
    bad_start = replace(start, approach_normal=Vector3(1, 1, 0))
    with pytest.raises(ValueError, match="does not match"):
        solve_candidate(case, bad_start, end)


def test_candidate_still_rejects_existing_macaroni_negative_control() -> None:
    """
    Keep the original conservative contract in front of candidate construction.
    """
    case = spatial_cases()[0]
    with pytest.raises(UnsafeRibbon):
        solve_candidate(case, cap_fit(case, True), cap_fit(case, False))


def test_complete_plan_preserves_targets_without_charging_unnecessary_support() -> None:
    """
    Reuse corrected branches and charge only the support actually required.
    """
    case = straight_case()
    shape, plan, report = prepare_candidate(case, cap_fit(case, True), cap_fit(case, False))
    assert report["verdict"] == "unresolved"
    assert report["failures"] == []
    assert len(plan.routes) == len(report["combined_end_regions"]) == 2 * case.lines
    for name, arguments in plan.inputs.items():
        original = plan.turns.fixed_routes[name]
        branch = plan.routes[name]
        assert branch.curves[0].start == original.curves[0].start
        assert branch.curves[0].control_a == original.curves[0].control_a
        assert branch.curves[-1].end == original.curves[-1].end
        assert plan(*arguments, name) is branch
    assert shape.meets_length_target


def test_screen_keeps_direction_controls_and_spatial_challenges_separate() -> None:
    """
    Keep all declared directions and broader challenges at the requested five widths.
    """
    cases = screen_cases()
    assert len(cases) == 8 and cases[5:7] == spatial_cases(5.0)[-2:]
    for case in cases[:5]:
        assert case.lines == 19 and case.diameter_mm == 1.5
        certify_curvature(case.route, 14.5)
        for at_start in (True, False):
            frame = analytic_guide_frame(case, at_start)
            case.end_boundary.require_contains(
                tuple(frame.origin.translated(frame.width, sign * 28.5 / 2) for sign in (-1, 1))
            )


@pytest.mark.parametrize("case", screen_cases()[:5], ids=lambda case: case.name)
def test_translated_lanes_need_no_end_flattening(case: RibbonStressCase) -> None:
    """
    Preserve equal translated lanes and exact cap directions across the controls.
    """
    from experiments.experiment_ribbon_cap_transition.planning import ShortConnectionFixture

    shape, plan, report = prepare_candidate(
        case,
        cap_fit(case, True),
        cap_fit(case, False),
        fixture=ShortConnectionFixture(case, turn_degrees=15),
    )
    assert shape.end_lead_mm == 0.0 and not shape.folded
    assert shape.spread < 1e-12
    assert report["failures"] == []
    assert all(end["cap_normal_error_degrees"] < 1e-5 for end in report["endings"])
    assert len(plan.routes) == 38


@pytest.mark.parametrize("bad", (Vector3(0, 0, 0), Vector3(float("nan"), 0, 0)))
def test_unusable_normals_never_receive_a_fallback_direction(bad: Vector3) -> None:
    """
    Reject missing geometric direction rather than silently inventing an axis.
    """
    with pytest.raises(ValueError):
        cap_direction(bad, Vector3(1, 0, 0))
    case = straight_case()
    with pytest.raises(ValueError):
        ribbon_frames(
            case.route, case.start_width, case.end_width, endpoint_tangents=(bad, Vector3(1, 0, 0))
        )
