"""
Verify stress geometry and expectations independently of current solver output.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import (
    CubicBezier,
    Vector3,
    cross,
    difference,
    dot,
    lerp,
    magnitude,
    unit,
)
from experiments.experiment_secure_discrete_ribbon.cases import (
    Expectation,
    RibbonStressCase,
    audit_end_boundary,
    stress_cases,
)
from experiments.experiment_secure_discrete_ribbon.contract import (
    UnsafeRibbon,
    certify_curvature,
    discrete_profile_reach,
)
from experiments.experiment_secure_discrete_ribbon.end_boundary import EndBoundary
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame
from experiments.experiment_secure_discrete_ribbon.reporting import (
    compare_outcomes,
    matrix_fingerprint,
    maximum_frame_step,
    summarize,
)
from experiments.experiment_secure_discrete_ribbon.transitions import (
    connection_turn,
    transition_coverage,
)


def test_matrix_is_deterministic_and_crosses_all_lane_counts() -> None:
    """
    Preserve reproducible identities, exact geometry, and nine distinct families.
    """
    cases = stress_cases()
    assert cases == stress_cases()
    assert matrix_fingerprint(cases) == matrix_fingerprint(stress_cases())
    assert len(cases) == len({case.name for case in cases}) == 27
    assert len({case.route.cable_id for case in cases}) == 27
    families = {case.family for case in cases}
    assert len(families) == 9
    for lines in (3, 5, 19):
        assert {case.family for case in cases if case.lines == lines} == families


@pytest.mark.parametrize("case", stress_cases(), ids=lambda case: case.name)
def test_full_end_guides_share_five_width_diameter_sphere(case: RibbonStressCase) -> None:
    """
    Constrain both complete cable ends, while explicitly permitting sweep excursions.
    """
    width = case.lines * case.diameter_mm
    report = audit_end_boundary(case)
    assert report["status"] == "contained"
    assert case.end_boundary.diameter_mm == 5 * width
    assert float(report["maximum_guide_radius_mm"]) <= 2.5 * width
    assert magnitude(
        difference(case.route.curves[0].start, case.route.curves[-1].end)
    ) == pytest.approx(2 * width)


@pytest.mark.parametrize("excursion_widths", (0.0, 20.0))
def test_boundary_neither_requires_nor_prohibits_sweep_excursions(excursion_widths: float) -> None:
    """
    Accept the same bounded ends with an entirely internal or external sweep.

    Only the endpoint constraint is tested here, not curve admissibility.
    """
    case = stress_cases()[0]
    start, end = case.route.curves[0].start, case.route.curves[-1].end
    offset = Vector3(0, 0, excursion_widths * case.lines * case.diameter_mm)
    curve = CubicBezier(
        start,
        lerp(start, end, 1 / 3).translated(offset, 1),
        lerp(start, end, 2 / 3).translated(offset, 1),
        end,
    )
    route = replace(case.route, curves=(curve,), points=(start, end))
    assert audit_end_boundary(replace(case, route=route)) == audit_end_boundary(case)
    assert (
        magnitude(difference(curve.point(0.5), case.end_boundary.center))
        > case.end_boundary.diameter_mm / 2
    ) is (excursion_widths > 0)


def test_boundary_rejects_invalid_or_displaced_guides_without_repair() -> None:
    """
    Reject sphere contract violations rather than translating or clamping input.
    """
    case = stress_cases()[0]
    with pytest.raises(ValueError, match="five cable widths"):
        audit_end_boundary(replace(case, end_boundary=EndBoundary(case.end_boundary.center, 1)))
    moved = replace(
        case, end_boundary=EndBoundary(Vector3(10000, 0, 0), case.end_boundary.diameter_mm)
    )
    with pytest.raises(ValueError, match="outside"):
        audit_end_boundary(moved)
    with pytest.raises(ValueError, match="finite and positive"):
        EndBoundary(Vector3(float("nan"), 0, 0), 10).require_contains((Vector3(0, 0, 0),))
    with pytest.raises(ValueError, match="outside"):
        case.end_boundary.require_contains((Vector3(float("inf"), 0, 0),))


def test_repeat_comparison_never_promotes_stable_failures_to_success() -> None:
    """
    Keep safety rejections, guard gaps, and valid builds in separate buckets.
    """
    rows: list[dict[str, object]] = [
        {"name": "a", "status": "guard_gap", "stage": "curvature"},
        {"name": "b", "status": "expected_rejection", "stage": "guide"},
        {"name": "c", "status": "built_and_audited"},
    ]
    assert compare_outcomes(rows, list(reversed(rows))) == []
    assert summarize(rows) == {"guard_gap": 1, "expected_rejection": 1, "built_and_audited": 1}
    changed = [*rows[:2], {"name": "c", "status": "audit_failure", "stage": "interference"}]
    assert compare_outcomes(rows, changed) == ["c"]
    assert compare_outcomes(rows, rows[:2]) == ["c"]


def test_complete_frame_metric_includes_roll_without_centerline_bend() -> None:
    """
    A straight route with 90 degrees of bank must not report zero frame change.
    """
    a = RibbonFrame(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1))
    b = RibbonFrame(Vector3(10, 0, 0), Vector3(1, 0, 0), Vector3(0, 0, 1), Vector3(0, -1, 0))
    assert maximum_frame_step((a, b)) == pytest.approx(90)


@pytest.mark.parametrize("case", stress_cases(), ids=lambda case: case.name)
def test_curves_have_regular_c1_joins(case: RibbonStressCase) -> None:
    """
    Do not mistake a sharp fixture join for a failure of the ribbon solver.
    """
    for a, b in zip(case.route.curves, case.route.curves[1:]):
        assert magnitude(difference(a.end, b.start)) < 1e-8
        assert dot(unit(a.derivative(1)), unit(b.derivative(0))) > 1 - 1e-10
    reach = discrete_profile_reach(case.lines, case.diameter_mm)
    if case.expectation is Expectation.CURVATURE_REJECTION:
        with pytest.raises(UnsafeRibbon, match="cannot be certified"):
            certify_curvature(case.route, reach)
    else:
        assert certify_curvature(case.route, reach).maximum_ratio <= 0.8


def test_crossing_controls_are_repeated_interior_points_not_tight_bends() -> None:
    """
    Demonstrate the nonlocal guard gap without constructing unsafe Fusion solids.
    """
    for case in stress_cases():
        if case.expectation is not Expectation.NONLOCAL_REJECTION:
            continue
        assert case.route.curves[1].end == case.route.curves[5].end
        first, second = case.route.curves[1].derivative(1), case.route.curves[5].derivative(1)
        assert abs(dot(unit(first), unit(second))) < 0.9
        reach = discrete_profile_reach(case.lines, case.diameter_mm)
        assert certify_curvature(case.route, reach).maximum_ratio <= 0.8
        sampled_ratio = max(
            reach
            * magnitude(cross(curve.derivative(i / 128), curve.second_derivative(i / 128)))
            / magnitude(curve.derivative(i / 128)) ** 3
            for curve in case.route.curves
            for i in range(129)
        )
        assert sampled_ratio < 0.1


@pytest.mark.parametrize("case", stress_cases(), ids=lambda case: case.name)
def test_every_outcome_includes_curved_cap_and_connection_transitions(
    case: RibbonStressCase,
) -> None:
    """
    Apply the same turns and ordered coverage to positive and negative controls.
    """
    coverage = transition_coverage(case.lines)
    assert [(row["end"], row["lane"]) for row in coverage] == [
        (end, lane) for end in ("A", "B") for lane in range(1, case.lines + 1)
    ]
    assert all(row["status"] == "not_reached" for row in coverage)
    radius = 8 * case.lines * case.diameter_mm
    for curve, endpoint, width in (
        (case.route.curves[0], 0, case.start_width),
        (case.route.curves[-1], 1, case.end_width),
    ):
        assert abs(dot(unit(curve.derivative(0)), unit(curve.derivative(1)))) < 1e-10
        assert magnitude(cross(curve.derivative(endpoint), curve.second_derivative(endpoint))) > 0
        inward = unit(curve.derivative(endpoint))
        if endpoint == 1:
            inward = Vector3(-inward.x, -inward.y, -inward.z)
        bend = unit(cross(inward, width))
        for lane in range(case.lines):
            center = curve.point(endpoint).translated(
                width, (lane - (case.lines - 1) / 2) * case.diameter_mm
            )
            branch = connection_turn(center, inward, bend, radius, f"{case.name}/{endpoint}/{lane}")
            exit_curve = branch.curves[0]
            assert exit_curve.end == center
            assert dot(unit(exit_curve.derivative(1)), inward) == pytest.approx(1)
            assert abs(dot(unit(exit_curve.derivative(0)), inward)) < 1e-10
            assert certify_curvature(branch, case.diameter_mm).maximum_ratio <= 0.8
