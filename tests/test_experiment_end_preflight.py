"""
Keep end-rule predictions independent of native construction and reverse traversal.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing import RibbonEndFit, RibbonShape
from cable_bundler.routing.geometry import Vector3
from cable_bundler.routing.ribbon import ribbon_frames
from cable_bundler.routing.ribbon_shape import solve_ribbon_shape
from experiments.experiment_ribbon_diagnosis.end_sections import CappedConnectionTurns
from experiments.experiment_ribbon_diagnosis.preflight import EndPlan
from experiments.experiment_ribbon_diagnosis.spatial import spatial_cases
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase


def fitted_shape(case: RibbonStressCase) -> RibbonShape:
    """
    Supply explicit ordered end centers without a Fusion dependency.
    """
    frames = ribbon_frames(case.route, case.start_width, case.end_width)
    initial = solve_ribbon_shape(frames, case.lines, case.diameter_mm)
    fits = tuple(
        RibbonEndFit(
            tuple(lane[index] for lane in initial.lanes),
            tuple(frames[index].thickness for _ in initial.lanes),
            approach_normal=frames[index].tangent,
        )
        for index in (0, -1)
    )
    return solve_ribbon_shape(
        frames, case.lines, case.diameter_mm, start_fit=fits[0], end_fit=fits[1]
    )


@pytest.mark.parametrize("case", spatial_cases(), ids=lambda case: case.name)
def test_every_ending_planned_even_when_trunk_rejected(case: RibbonStressCase) -> None:
    """
    Reject oversized internal blends and preserve every checked branch verbatim.
    """
    plan = EndPlan(case, CappedConnectionTurns(case, turn_degrees=15))
    report = plan.inspect(fitted_shape(case))
    assert report["verdict"] == "reject"
    assert "internal_end_region_exceeds_six_percent" in report["failures"]
    assert len(report["endings"]) == len(plan.routes) == 2 * case.lines
    assert report["kernel_prediction"] == "unresolved"
    for name, arguments in plan.inputs.items():
        assert plan(*arguments, name) is plan.routes[name]
    name = next(iter(plan.inputs))
    center, inward, bend, radius = plan.inputs[name]
    with pytest.raises(ValueError, match="differ"):
        plan(center.translated(inward, 0.01), inward, bend, radius, name)


def test_wrong_cap_normal_is_not_exempted_by_reverse_loft() -> None:
    """
    Require cap approach consistency even when branch curvature is acceptable.
    """
    case = spatial_cases()[4]
    shape = fitted_shape(case)
    assert shape.start_fit is not None
    shape = replace(shape, start_fit=replace(shape.start_fit, approach_normal=Vector3(1, 0, 0)))
    report = EndPlan(case, CappedConnectionTurns(case, turn_degrees=15)).inspect(shape)
    assert any("cap_approach_direction" in reason for reason in report["failures"])


def test_no_known_violation_is_not_a_kernel_success_prediction() -> None:
    """
    Keep incomplete certification unresolved rather than inferring a positive result.
    """
    case = spatial_cases()[4]
    shape = replace(
        fitted_shape(case),
        lengths_mm=(100.0,) * case.lines,
        spread=0.0,
        end_lead_mm=0.0,
        minimum_end_radius_mm=10.0,
        maximum_pitch_ratio=1.0,
    )
    report = EndPlan(case, CappedConnectionTurns(case, turn_degrees=15)).inspect(shape)
    assert report["failures"] == []
    assert report["verdict"] == "unresolved"
    assert report["kernel_prediction"] == "unresolved"
