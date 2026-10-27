"""
Check generalized chart invariants,deterministic initialization and interrupted ledgers.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Callable

import pytest

from cable_bundler.routing.geometry import Vector3, cross, dot, magnitude
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery import (
    box_fit,
    broad_chart,
    broad_search,
    projected_clearance,
    solver,
)
from experiments.experiment_ribbon_route_discovery.active_clearance import sample
from experiments.experiment_ribbon_route_discovery.families import Seed
from experiments.experiment_ribbon_route_discovery.generalization_cases import fresh, reserved


def _case() -> EndpointCase:
    """
    Supply a simple fixed boundary pair without a cached fitted path.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    return EndpointCase("test boundary", Vector3(0, 0, 0), Vector3(80, 0, 0), x, x, y, y)


def test_seed_bank_is_generic_deterministic_and_bounded() -> None:
    """
    Case renaming must not select a different chart branch or fitted initialization.
    """
    case = _case()
    bank = broad_chart.screen(case, lambda: None)
    renamed = broad_chart.screen(replace(case, name="unrelated identity"), lambda: None)
    assert bank == renamed and len(bank) == 110
    assert tuple(seed.index for seed in bank) == tuple(range(110))
    lower, upper = broad_chart.bounds(case)
    assert all(
        all(lo <= v <= hi for lo, v, hi in zip(lower, seed.coordinates, upper)) for seed in bank
    )


@pytest.mark.parametrize("scale", [0.1, 1.0, 100.0])
def test_chart_transport_scales_with_width_thickness_and_endpoint_distance(scale: float) -> None:
    """
    Preserve dimensionless material fields rather than imposing millimeter restrictions.
    """
    case = _case()
    other = replace(case, end=Vector3(80 * scale, 0, 0), diameter_mm=case.diameter_mm * scale)
    values = (1.0, -0.2, 0.1, 0.0, 0.1, 0.1, -0.2, 0.1, 0.0, 2.0)
    path = broad_chart.integrate(case, values, 64, lambda: None)
    scaled = broad_chart.integrate(other, values, 64, lambda: None)
    assert broad_chart.carrier_maximum(case) == pytest.approx(broad_chart.carrier_maximum(other))
    for left, right in zip(path.states, scaled.states):
        assert right[:3] == pytest.approx(tuple(scale * v for v in left[:3]), abs=1e-9)
        assert right[3:] == pytest.approx(left[3:], abs=1e-12)


def test_chart_transport_respects_arbitrary_initial_pose() -> None:
    """
    Rotate and translate the complete boundary problem without changing intrinsic coordinates.
    """
    case = _case()

    def rotate(vector: Vector3) -> Vector3:
        """
        Rotate by90degrees about worldZ without a floating trigonometric approximation.
        """
        return Vector3(-vector.y, vector.x, vector.z)

    origin = Vector3(12, -8, 4)
    other = replace(
        case,
        start=origin,
        end=origin.translated(rotate(case.end), 1.0),
        start_tangent=rotate(case.start_tangent),
        end_tangent=rotate(case.end_tangent),
        start_width=rotate(case.start_width),
        end_width=rotate(case.end_width),
    )
    values = (1.0, -0.2, 0.1, 0.0, 0.1, 0.1, -0.2, 0.1, 0.0, 2.0)
    path = broad_chart.integrate(case, values, 64, lambda: None)
    moved = broad_chart.integrate(other, values, 64, lambda: None)
    for left, right in zip(path.states, moved.states):
        position = origin.translated(rotate(Vector3(*left[:3])), 1.0)
        assert right[:3] == pytest.approx((position.x, position.y, position.z), abs=1e-10)
        for index in (3, 6):
            direction = rotate(Vector3(*left[index : index + 3]))
            assert right[index : index + 3] == pytest.approx(
                (direction.x, direction.y, direction.z)
            )


def test_fit_preserves_work_bounds_and_actual_monotone_acceptance() -> None:
    """
    Check transported fit evidence rather than echoing a synthetic optimizer result.
    """
    case = _case()
    values = (0.3, 0.0, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 1.2)
    seed = Seed(0, values, 1.0, (0.0, 0.0, 0.0))
    path, metrics = box_fit.refine(case, seed, lambda: None, box_fit.SHORT)
    assert len(path.states) == 513 and metrics["evaluations"] <= 74
    assert metrics["qp_steps"] and all(row["iterations"] <= 32 for row in metrics["qp_steps"])
    trials = [row for stage in metrics["stages"] for row in stage["trials"]]
    assert any(row["accepted"] for row in trials)
    lower, upper = broad_chart.bounds(case)
    for row in trials:
        assert row["accepted"] == (row["after"] < row["before"])
        assert all(lo <= v <= hi for lo, v, hi in zip(lower, row["proposed"], upper))


def test_final_checkpoint_failure_retains_trial_but_exposes_no_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A resource stop after fitting must not appear as a completed successful solve.
    """
    seed = Seed(0, (0.0,) * 9 + (1.0,), 0.0, (0.0, 0.0, 0.0))

    def screen(case: EndpointCase, checkpoint: Callable[[], None]) -> tuple[Seed, ...]:
        """
        Isolate interruption semantics from the unrelated110seed workload.
        """
        del case, checkpoint
        return (seed,)

    monkeypatch.setattr(broad_chart, "screen", screen)
    ledger = broad_search.SearchLedger()

    def checkpoint() -> None:
        """
        Simulate a resource guard expiring immediately after the completed trial.
        """
        if ledger.trials:
            raise RuntimeError("test resource cap")

    with pytest.raises(RuntimeError, match="test resource cap"):
        broad_search.solve(_case(), checkpoint, ledger)
    assert len(ledger.trials) == 1 and ledger.trials[0].ready_for_analysis
    assert ledger.candidate is None and ledger.seconds is not None
    with pytest.raises(ValueError, match="one-use"):
        broad_search.solve(_case(), lambda: None, ledger)


def test_projected_width_steps_restore_pose_before_accepting_actual_clearance() -> None:
    """
    Exercise nonlinear projection on an actual closed crossing without stored coordinates.
    """
    case = replace(
        _case(),
        start=Vector3(-40, 0, 0),
        end=Vector3(35, -16, 12),
        end_width=Vector3(0, 0, -1),
    )
    _, selected, _ = solver.screen_seeds(case, lambda: None)
    path, base = solver.refine_full(case, selected[0], lambda: None)
    assert (
        base["strict_endpoint_gate"]
        and sample(case, path, lambda: None).contacts["contact_detected"]
    )
    _, metrics = projected_clearance.refine(case, selected[0], base, lambda: None)
    accepted = [trial for trial in metrics["projection_trials"] if trial["accepted"]]
    assert accepted and metrics["projection_transports"] <= 700 and metrics["evaluations"] <= 750
    for trial in accepted:
        assert trial["pose_error"] <= 1e-7 and trial["after"] < trial["before"]


def test_fresh_and_reserved_boundaries_are_distinct_valid_ordered_frames() -> None:
    """
    Freeze target geometry without solving or consuming the reserved validation inputs.
    """
    cases = fresh() + reserved()
    assert len(cases) == len({case.name for case in cases}) == 12
    assert (
        len(
            {
                (case.end, case.end_tangent, case.end_width, case.lines, case.diameter_mm)
                for case in cases
            }
        )
        == 12
    )
    for case in cases:
        assert math.isfinite(magnitude(case.end)) and magnitude(case.end) > 0
        assert magnitude(case.end_tangent) == pytest.approx(1)
        assert magnitude(case.end_width) == pytest.approx(1)
        assert dot(case.end_tangent, case.end_width) == pytest.approx(0, abs=1e-15)
        assert magnitude(cross(case.end_tangent, case.end_width)) == pytest.approx(1)
