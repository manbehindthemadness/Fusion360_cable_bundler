"""
Protect canonical cap identity and the fixed reversal fixture without Fusion solves.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from experiments.experiment_ribbon_cap_transition.cap_handoff import CapFrameHandoff
from experiments.experiment_ribbon_cap_transition.fixtures import reversal_case
from experiments.experiment_ribbon_cap_transition.regression_cases import comparison_cases
from experiments.experiment_ribbon_diagnosis.end_sections import CappedConnectionTurns
from experiments.experiment_ribbon_diagnosis.inputs import analytic_guide_frame
from experiments.experiment_ribbon_diagnosis.preflight import EndPlan
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame


def test_reversal_fixture_has_opposite_tangents_signed_widths_and_four_width_sphere() -> None:
    """
    Check authored boundary conditions, not solver or native geometry success.
    """
    case = reversal_case()
    left, right = (analytic_guide_frame(case, at_start) for at_start in (True, False))
    assert dot(left.tangent, right.tangent) == pytest.approx(-1)
    assert left.width == Vector3(0, 1, 0) and right.width == Vector3(0, -1, 0)
    assert case.end_boundary.diameter_mm == 4 * case.lines * case.diameter_mm
    assert len(case.route.curves) == 2
    a, b = case.route.curves
    assert magnitude(difference(a.end, b.start)) < 1e-12
    assert dot(unit(a.derivative(1)), unit(b.derivative(0))) == pytest.approx(1)
    assert magnitude(difference(left.origin, right.origin)) == pytest.approx(60)


@pytest.mark.parametrize(
    "case_id",
    (
        "spatial_s_twist45_19x1.5",
        "regression_asymmetric_arch",
        "regression_twisted_quarter",
        "regression_orthogonal_bends",
    ),
)
def test_handoff_preserves_exact_plan_guard_and_endpoint_identity(case_id: str) -> None:
    """
    Canonicalize equivalent references without weakening the frozen input guard.

    Synthetic cap rounding is tested across retained boundary conditions. No
    complete ribbon shape or branch planner inspection is executed by this test.
    """
    case = next(case for case in comparison_cases() if case.name == case_id)
    start, end = (analytic_guide_frame(case, at_start) for at_start in (True, False))
    rounded = replace(end, thickness=end.thickness.translated(Vector3(1, 0, 0), 1e-16))
    handoff = CapFrameHandoff([start, start, rounded])
    solved = (start, end)
    plan = EndPlan(case, CappedConnectionTurns(case))
    center = end.origin
    inward = Vector3(-end.tangent.x, -end.tangent.y, -end.tangent.z)
    bend = Vector3(-end.thickness.x, -end.thickness.y, -end.thickness.z)
    plan.inputs["B1"] = (center, inward, bend, 1.0)
    plan.routes["B1"] = case.route
    changed_bend = bend.translated(Vector3(1, 0, 0), 1e-12)
    with pytest.raises(ValueError, match="inputs differ"):
        plan(center, inward, changed_bend, 1.0, "B1")
    original_container = handoff.frames
    handoff.adopt(solved)
    assert handoff.frames is original_container
    assert handoff.frames[0] is start and handoff.frames[-1] is end
    assert handoff.frames[1] is start
    assert plan(center, inward, bend, 1.0, "B1") is case.route


@pytest.mark.parametrize("delta", (1e-8, math.nan))
def test_handoff_rejects_movement_and_nonfinite_axes_atomically(delta: float) -> None:
    """
    Do not alter even the first endpoint if the second cap fails equivalence.
    """
    case = reversal_case()
    start, end = (analytic_guide_frame(case, at_start) for at_start in (True, False))
    handoff = CapFrameHandoff([start, end])
    moved = replace(end, origin=end.origin.translated(Vector3(1, 0, 0), delta))
    with pytest.raises(ValueError, match="fixed native guide"):
        handoff.adopt((replace(start), moved))
    assert handoff.frames[0] is start and handoff.frames[-1] is end


def test_handoff_banks_once_and_rejects_unbound_adoption(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep fixture preparation unchanged and prohibit accidental repeated binding.
    """
    case = reversal_case()
    frames = tuple(analytic_guide_frame(case, at_start) for at_start in (True, False))
    calls: list[tuple[object, ...]] = []

    def bank(
        nodes: tuple[RibbonFrame, ...], lines: int, diameter: float
    ) -> tuple[RibbonFrame, ...]:
        """
        Capture the unchanged banking arguments without executing bank search.
        """
        calls.append((nodes, lines, diameter))
        return nodes

    monkeypatch.setattr(
        "experiments.experiment_ribbon_cap_transition.cap_handoff.bank_ribbon_frames", bank
    )
    handoff = CapFrameHandoff()
    with pytest.raises(ValueError, match="bound"):
        handoff.adopt(frames)
    container = handoff.bank(frames, case.lines, case.diameter_mm)
    with pytest.raises(RuntimeError, match="already bound"):
        handoff.bank(frames, case.lines, case.diameter_mm)
    handoff.adopt(frames)
    assert container is handoff.frames
    assert calls == [(frames, case.lines, case.diameter_mm)]
