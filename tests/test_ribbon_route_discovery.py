"""
Verify isolated discovery work accounting and preservation of prescribed controls.
"""

from __future__ import annotations

from dataclasses import replace

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery.contact import audit
from experiments.experiment_ribbon_route_discovery.solver import (
    refine,
    refine_full,
    refine_guided,
    screen_seeds,
)


def test_straight_control_retains_targets_and_separates_screening_from_fitting() -> None:
    """
    Preserve exact straight closure while recording all46 starts and bounded rounds.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    case = EndpointCase("synthetic-control", Vector3(0, 0, 0), Vector3(80, 0, 0), x, x, y, y)
    bank, selected, seconds = screen_seeds(case, lambda: None)
    assert len(bank) == 46 and 1 <= len(selected) <= 3 and seconds >= 0
    renamed, chosen, _ = screen_seeds(replace(case, name="unrelated-name"), lambda: None)
    assert renamed == bank and chosen == selected
    path, metrics = refine(case, selected[0], lambda: None)
    assert metrics["strict_endpoint_gate"] and metrics["evaluations"] <= 74
    assert tuple(stage["grid"] for stage in metrics["stages"]) == (64, 512)
    result, rulings = audit(case, path, lambda: None)
    assert result["position_connected"] and result["strict_frame_gate"]
    assert not result["contact_detected"] and len(rulings) == 129
    assert rulings[-1].flat_start.x == 80


def test_off_plane_control_preserves_monotone_steps_and_final_fine_grid() -> None:
    """
    Exercise actual updates without assuming short refinement must close every case.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    case = EndpointCase("synthetic-oblique", Vector3(0, 0, 0), Vector3(80, 0, 12), x, x, y, y)
    _, selected, _ = screen_seeds(case, lambda: None)
    path, metrics = refine(case, selected[0], lambda: None)
    assert len(path.states) == 513 and metrics["evaluations"] <= 74
    trials = [trial for stage in metrics["stages"] for trial in stage["trials"]]
    assert trials
    for stage in metrics["stages"]:
        assert all(b <= a for a, b in zip(stage["history"], stage["history"][1:]))
    assert all(trial["accepted"] == (trial["after"] < trial["before"]) for trial in trials)


def test_guided_straight_control_preserves_closure_without_spurious_planes() -> None:
    """
    Couple guidance into fitting without inventing collisions or altering a straight route.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    case = EndpointCase("guided-control", Vector3(0, 0, 0), Vector3(80, 0, 0), x, x, y, y)
    _, selected, _ = screen_seeds(case, lambda: None)
    path, metrics, guide = refine_guided(case, selected[0], lambda: None)
    assert metrics["strict_endpoint_gate"] and metrics["evaluations"] <= 254
    assert not guide.constraints and guide.observations > 0
    assert guide.residuals(path) == (0.0,) * 8


def test_full_family_fit_improves_oblique_closure_within_recorded_work() -> None:
    """
    Distinguish insufficient short-fit depth from a completed endpoint refinement.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    case = EndpointCase("full-family", Vector3(0, 0, 0), Vector3(80, 0, 12), x, x, y, y)
    _, selected, _ = screen_seeds(case, lambda: None)
    _, short = refine(case, selected[0], lambda: None)
    path, full = refine_full(case, selected[0], lambda: None)
    assert full["score"] <= short["score"] and full["strict_endpoint_gate"]
    assert full["evaluations"] <= 254 and len(path.states) == 513
    assert full["work_policy"] == dict(coarse_rounds=18, fine_rounds=3, maximum_evaluations=254)
