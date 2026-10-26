"""
Check boundary-first arrival and independent material-map derivatives.
"""

from __future__ import annotations

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_ribbon_cap_transition import edge_first, edge_optimization
from experiments.experiment_ribbon_cap_transition.edge_first import (
    boundary,
    construct,
    edge_gate,
    frame,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase


def _case() -> EndpointCase:
    """
    Provide a synthetic spatial pose with distinct permanent terminal widths.
    """
    return EndpointCase(
        "synthetic_edge",
        Vector3(0, 0, 0),
        Vector3(80, 20, 10),
        Vector3(1, 0, 0),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 0, 1),
    )


@pytest.mark.parametrize(
    "ratio,speed", [(None, 1.0), (0.2, 1.0), (0.4, 1.5), (0.6, 2.0), (0.4, 2.5)]
)
def test_boundary_reaches_both_targets_and_ordered_terminal_frames(
    ratio: float | None, speed: float
) -> None:
    """
    Establish exact polynomial boundary conditions before inspecting its interior.
    """
    case = _case()
    curve = boundary(case, ratio, speed)
    first, last = frame(curve, 0), frame(curve, 1)
    half_width = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    for observed, point, width, tangent in (
        (first, case.start, case.start_width, case.start_tangent),
        (last, case.end, case.end_width, case.end_tangent),
    ):
        assert magnitude(difference(observed.position, point.translated(width, half_width))) < 1e-10
        assert magnitude(difference(observed.tangent, tangent)) < 1e-10
        assert magnitude(difference(observed.width, width)) < 1e-10
        assert abs(observed.slope) < 1e-10
        assert magnitude(difference(observed.lane(-half_width)[0], point)) < 1e-8


def test_companion_velocity_and_ruling_rate_match_finite_differences() -> None:
    """
    Independently differentiate the position map rather than restating its formula.
    """
    curve = boundary(_case())
    u, step, offset = 0.23, 1e-6, -2.5
    middle, left, right = frame(curve, u), frame(curve, u - step), frame(curve, u + step)
    numerical = difference(right.lane(offset)[0], left.lane(offset)[0])
    numerical = Vector3(
        numerical.x / (2 * step), numerical.y / (2 * step), numerical.z / (2 * step)
    )
    assert magnitude(difference(numerical, middle.lane(offset)[1])) < 1e-5
    assert middle.slope_rate == pytest.approx((right.slope - left.slope) / (2 * step), rel=1e-7)


def test_arrival_alone_does_not_authorize_companions(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Retain a successful edge arrival when its full-width compatibility is rejected.
    """
    result = construct(_case())
    assert result.metrics["edge_gate_passed"]
    assert result.metrics["compatibility_stations"] <= 257
    assert not result.companion_allowed
    assert result.metrics["findings"]
    failed = edge_gate(
        _case(), Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(1, 0, 0), Vector3(1, 0, 0)
    )
    assert not failed["edge_gate_passed"]

    def reject_arrival(*_args: object) -> dict[str, object]:
        """
        Simulate an arrival failure before any interior frame is requested.
        """
        return {"edge_gate_passed": False}

    def forbidden_frame(*_args: object) -> None:
        """
        Fail the test if compatibility runs after a rejected arrival.
        """
        raise AssertionError("Compatibility must wait for edge arrival.")

    monkeypatch.setattr(edge_first, "edge_gate", reject_arrival)
    monkeypatch.setattr(edge_first, "frame", forbidden_frame)
    rejected = construct(_case())
    assert not rejected.companion_allowed
    assert rejected.metrics["compatibility_stations"] == 0


@pytest.mark.parametrize("free_controls", [2, 4])
def test_interior_deformation_preserves_boundary_derivatives(free_controls: int) -> None:
    """
    Verify degree elevation and free controls leave all cap constraints unchanged.
    """
    curve = boundary(_case(), 0.4, 2.5)
    elevated = edge_optimization.elevate(curve, free_controls)
    values = (0.1, -0.2, 0.15, -0.2, 0.1, -0.1) * (free_controls // 2)
    altered = edge_optimization.deform(elevated, values, 80)
    for fraction in (0.0, 0.2, 0.5, 0.9, 1.0):
        assert magnitude(difference(curve.jet(fraction)[0], elevated.jet(fraction)[0])) < 1e-10
    for fraction in (0.0, 1.0):
        for original, changed in zip(elevated.jet(fraction)[:4], altered.jet(fraction)[:4]):
            assert magnitude(difference(original, changed)) < 1e-10
    measured = construct(_case(), reference_curve=altered)
    assert measured.metrics["edge_gate_passed"]


@pytest.mark.parametrize(
    "interior_policy",
    [edge_optimization.STANDARD, edge_optimization.EXPANDED, edge_optimization.PRECISION],
)
def test_interior_refinement_counts_probes_and_preserves_final_gate(
    monkeypatch: pytest.MonkeyPatch,
    interior_policy: edge_optimization.InteriorPolicy,
) -> None:
    """
    Exercise bounded updates with a surrogate while retaining the real final audit.
    """
    calls = []

    def residual(
        case: EndpointCase,
        curve: edge_first.BoundaryCurve,
        coordinates: tuple[float, ...],
        *,
        policy: edge_optimization.InteriorPolicy = edge_optimization.STANDARD,
    ) -> tuple[float, ...]:
        """
        Substitute a predictable objective without claiming geometry convergence.
        """
        assert case == _case()
        assert policy == interior_policy
        assert len(curve.points) == 8 + policy.free_controls
        calls.append(coordinates)
        return tuple(value - 0.01 for value in coordinates) + (1.0,)

    checkpoints = []

    def checkpoint() -> None:
        """
        Record every scheduled screening and the independent final audit.
        """
        checkpoints.append(True)

    monkeypatch.setattr(edge_optimization, "residuals", residual)
    result, counters = edge_optimization.improve(
        _case(), boundary(_case()), checkpoint, policy=interior_policy
    )
    evaluations = counters["evaluations"]
    assert isinstance(evaluations, int)
    maximum_evaluations = 1 + interior_policy.rounds * (3 * interior_policy.free_controls + 2)
    assert len(calls) == evaluations <= maximum_evaluations
    assert len(checkpoints) == evaluations + 1
    history = result.metrics["objective_history"]
    assert history[-1] < history[0]
    assert all(b <= a for a, b in zip(history, history[1:]))
    assert result.metrics["edge_gate_passed"]
    assert result.metrics["compatibility_stations"] <= 257


def test_all_lane_objective_detects_radius_failure_missed_by_center(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Penalize tight B curvature even when the center alone meets its radius budget.
    """
    case = _case()
    half_width = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    observed = edge_first.BoundaryFrame(
        Vector3(40, 10, 5),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        0,
        0.95 / (2 * half_width),
        1.0,
        0.02,
    )

    def fixed_frame(_curve: edge_first.BoundaryCurve, _u: float) -> edge_first.BoundaryFrame:
        """
        Supply a known positive-Jacobian reference with excessive B-edge curvature.
        """
        return observed

    monkeypatch.setitem(vars(edge_optimization), "frame", fixed_frame)
    values = edge_optimization.residuals(case, boundary(case), (0.0,) * 6)
    assert len(values) == 65 * 4 + 6
    assert values[1] == 0
    assert values[2] > 0
