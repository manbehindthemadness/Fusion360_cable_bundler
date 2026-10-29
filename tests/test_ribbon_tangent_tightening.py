"""
Check optional local terminal bending and bounded fitting without native geometry.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude
from experiments.experiment_ribbon_bend_redistribution.refinement import redistribute
from experiments.experiment_ribbon_cap_transition.compatible_strip import (
    BendMapping,
    CompatibleField,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery import box_fit, broad_chart
from experiments.experiment_ribbon_route_discovery.families import Seed
from experiments.experiment_ribbon_route_discovery.solver import errors_for
from experiments.experiment_ribbon_tangent_tightening.chart import TangentFitChart
from experiments.experiment_ribbon_tangent_tightening.field import (
    TangentTightening,
    TerminalRoutingField,
)
from experiments.experiment_ribbon_tangent_tightening.refinement import tighten


def _case() -> EndpointCase:
    """
    Supply fixed ordered terminal frames without historical fitted coordinates.
    """
    tangent, width = Vector3(1, 0, 0), Vector3(0, 1, 0)
    return EndpointCase(
        "terminal control",
        Vector3(0, 0, 0),
        Vector3(80, 0, 0),
        tangent,
        tangent,
        width,
        width,
        7,
        1,
    )


@pytest.mark.parametrize("end", ("start", "end"))
@pytest.mark.parametrize("sign", (-1, 1))
def test_local_turn_changes_only_its_own_window_and_preserves_cap_geometry(
    end: str,
    sign: int,
) -> None:
    """
    Add signed bend inside one terminal region without changing ruling or cap turn.
    """
    chart = TangentFitChart(TangentTightening())
    values = chart.lift((0.0,) * 9 + (1.0,))
    values = values[:10] + ((2.0 * sign, 0.0) if end == "start" else (0.0, 2.0 * sign))
    original = broad_chart.integrate(_case(), values[:10], 64, lambda: None)
    changed = chart.integrate(_case(), values, 512, lambda: None)
    for i in range(33):
        u = i / 32
        before, after = original.field.carrier(u), changed.field.carrier(u)
        inside = 0 < u < 0.25 if end == "start" else 0.75 < u < 1
        if inside:
            assert after.turn * sign > 0
        else:
            assert after == before
    assert changed.states[0] == original.states[0]
    assert changed.field.sample(0)[1:] == changed.field.sample(1)[1:] == (0.0, 0.0)
    for state, rate in zip(changed.states, changed.rates):
        assert dot(Vector3(*rate[3:6]), Vector3(*state[6:9])) == pytest.approx(0, abs=1e-12)
    assert magnitude(difference(Vector3(*changed.states[-1][:3]), _case().end)) > 0.1


@pytest.mark.parametrize("length", (0.5, 150.0, 1000.0))
def test_extreme_terminal_turns_retain_full_width_material_and_bend_limits(length: float) -> None:
    """
    Exercise opposing local turns alongside extreme global bending and ruling.
    """
    raw = TerminalRoutingField(
        "extreme terminal",
        length,
        (4 * math.pi,) * 4,
        (3, -3, -3, 3),
        19,
        1.5,
        -4 * math.pi,
        -3,
        TangentTightening(1 / 16, 1 / 4),
        4 * math.pi,
        -4 * math.pi,
    )
    field = CompatibleField(raw, BendMapping.NEAR_LIMIT)
    reach = math.hypot(field.half_width_mm, field.diameter_mm / 2)
    for i in range(513):
        sample = field.carrier(i / 512)
        minimum_speed = sample.progress_mm - field.half_width_mm * abs(sample.eta_u)
        assert minimum_speed > 0.1 * sample.progress_mm
        assert abs(sample.turn) * reach < 0.78 * sample.progress_mm
        assert 3.1 * field.diameter_mm * abs(sample.turn) < minimum_speed


@pytest.mark.parametrize(
    "policy",
    (
        TangentTightening(0, 0),
        TangentTightening(0.125, 0),
        TangentTightening(0, 0.25),
        TangentTightening(),
    ),
)
def test_zero_amplitudes_replay_baseline_exactly_and_disabled_ends_have_no_coordinate(
    policy: TangentTightening,
) -> None:
    """
    Keep the original chart and both cap states bit-for-bit when adjustments are zero.
    """
    case = _case()
    values = (0.5, -0.1, 0.2, 0.0, 0.0, 0.2, -0.1, 0.0, 0.0, 1.5)
    chart = TangentFitChart(policy)
    lifted = chart.lift(values)
    baseline = broad_chart.integrate(case, values, 64, lambda: None)
    replay = chart.integrate(case, lifted, 64, lambda: None)
    assert replay == baseline
    assert len(lifted) == policy.dimensions
    assert chart.bounds(case)[0][:10] == broad_chart.bounds(case)[0]
    assert chart.bounds(case)[1][:10] == broad_chart.bounds(case)[1]


def test_disabled_fitting_matches_original_fitter_and_two_end_fit_counts_extra_probes() -> None:
    """
    Preserve default behavior, then measure a real enabled fit with fixed target frames.
    """
    case = replace(_case(), end=Vector3(80, 0, 8))
    coordinates = (0.0,) * 9 + (1.2,)
    seed = Seed(0, coordinates, 0.0, ())
    baseline, old = box_fit.refine(case, seed, lambda: None, box_fit.FitWork(10, 3, 158))
    disabled, off = tighten(case, coordinates, lambda: None)
    assert disabled == baseline
    for key in ("coordinates", "score", "evaluations", "stages", "qp_steps"):
        assert off[key] == old[key]
    chart = TangentFitChart(TangentTightening())
    initial = chart.integrate(case, chart.lift(coordinates), 512, lambda: None)
    initial_score = sum(v * v for v in errors_for(case, initial))
    enabled, metrics = tighten(case, coordinates, lambda: None, tightening=chart.tightening)
    assert metrics["score"] < initial_score
    assert len(metrics["coordinates"]) == 12
    assert any(v != 0 for v in metrics["coordinates"][10:])
    assert 2 < metrics["evaluations"] <= 158
    assert len(enabled.states) == 513
    assert enabled.states[0] == initial.states[0]
    assert metrics["tangent_tightening"]["work"] == {"coarse": 8, "fine": 3, "transports": 158}
    trials = [trial for stage in metrics["stages"] for trial in stage["trials"]]
    assert all(trial["accepted"] == (trial["after"] < trial["before"]) for trial in trials)


def test_redistribution_composes_with_tightening_without_a_second_warm_fit() -> None:
    """
    Share the optional terminal fit and its cap instead of spending two work budgets.
    """
    case, coordinates = _case(), (0.0,) * 9 + (1.0,)
    original = broad_chart.integrate(case, coordinates, 512, lambda: None)
    policy = TangentTightening(0, 0.125)
    combined, metrics = redistribute(case, original, coordinates, lambda: None, tightening=policy)
    direct, expected = tighten(case, coordinates, lambda: None, tightening=policy)
    assert combined == direct == original
    assert metrics["allocation"] is None
    assert metrics["evaluations"] == expected["evaluations"] == 2
    assert metrics["tangent_tightening"]["dimensions"] == 11


def test_terminal_probes_and_trials_stay_inside_the_existing_step_and_coordinate_boxes() -> None:
    """
    Include both new coordinates in the joint norm and use inward differences at caps.
    """
    case, chart = _case(), TangentFitChart(TangentTightening())
    lower, upper = chart.bounds(case)
    for index in range(12):
        probe = chart.probe(case, upper, index)
        assert probe[index] < upper[index]
        assert all(lo <= v <= hi for lo, v, hi in zip(lower, probe, upper))
    values = chart.lift((0.0,) * 9 + (2.0,))
    trial = chart.trial(case, values, (100.0,) * 12, 1.0)
    assert math.sqrt(sum((a - b) ** 2 for a, b in zip(values, trial))) <= 1.5 + 1e-12
    assert all(lo <= v <= hi for lo, v, hi in zip(lower, trial, upper))
    with pytest.raises(ValueError, match="chart"):
        chart.integrate(case, values[:10], 64, lambda: None)
    with pytest.raises(ValueError, match="chart"):
        chart.integrate(case, values[:-1] + (math.nan,), 64, lambda: None)
    with pytest.raises(ValueError, match="finite original"):
        chart.lift(values)


@pytest.mark.parametrize("fraction", (-0.1, 0.01, 0.5, math.nan, math.inf, True))
def test_unresolved_or_invalid_windows_are_rejected(fraction: float) -> None:
    """
    Keep search support resolved by the coarse grid and away from the other end.
    """
    with pytest.raises(ValueError, match="windows"):
        TangentTightening(fraction, 0.25)


def test_tightening_propagates_resource_stops_without_retry() -> None:
    """
    Preserve caller-owned stop gates before optional fitting begins.
    """

    def stopped() -> None:
        """
        Simulate the caller's source or resource guard.
        """
        raise RuntimeError("resource stop")

    with pytest.raises(RuntimeError, match="resource stop"):
        tighten(_case(), (0.0,) * 9 + (1.0,), stopped, tightening=TangentTightening())
