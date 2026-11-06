"""
Distinguish confirmed attached-sheet crossings from undecided fold boxes during bounded recovery.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Literal

import pytest

from cable_bundler.routing.geometry import cross, unit
from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_feature_insertion.contact_recovery import recover
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.selection import Branch
from experiments.experiment_ribbon_feature_insertion.separation import Separation, Side, regions
from experiments.experiment_ribbon_feature_insertion.solve import construct
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_locked_solver import recovery_evidence
from experiments.experiment_ribbon_locked_solver.recovery_evidence import adjacent_straight_contact
from experiments.experiment_ribbon_locked_solver.recovery_selection import select_recovery
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_locked_solver.solver_v2 import solve
from experiments.experiment_ribbon_regression.corpus import load, targets


@pytest.fixture(scope="module")
def missed_crossing() -> tuple[Branch, ContactResult]:
    """
    Recreate the current ten-conductor gym input whose depth-first audit masks a straight crossing.
    """
    scene = Scene(
        Config(884004928, 10, 0.75, 300, 300),
        Goal.from_degrees(22, 10, 19),
        Goal.from_degrees(1, 6, 52),
    )
    frames = Frames.create(scene.targets)
    radius = scene.targets.diameter_mm / 2 / PinchLimit().fraction * (1 + 1e-9)
    result = construct(
        Boundary(frames.targets, radius), frames, (0.5,), 1e-5, lambda: None, lambda e: None
    )
    return next(item for item in result.rejected if item[0].roots == (1, 0))


def test_actual_interiors_strengthen_depth_evidence_without_claiming_clearance(
    missed_crossing: tuple[Branch, ContactResult],
) -> None:
    """
    Retain the original undecided result while confirming both inverse maps at one shared point.
    """
    branch, contact = missed_crossing
    events: list[dict[str, Any]] = []
    stronger, plane = adjacent_straight_contact(branch.route, contact, lambda: None, events.append)
    assert contact.status == "unresolved" and contact.limit == "depth"
    assert stronger.status == "penetration" and stronger.witness is not None
    witness = stronger.witness
    assert witness.pieces == (3, 6) and stronger.pairs_checked == contact.pairs_checked
    assert plane is not None
    assert plane == regions(branch.route)[3]
    for index in witness.pieces:
        assert occupied_coordinates(branch.route.pieces[index], witness.point, 10, 0.75) is not None
    assert events[-1]["status"] == "confirmed_attached_straight"


@pytest.mark.parametrize("limit", ("pairs", None))
def test_other_unresolved_results_never_invent_a_crossing(
    missed_crossing: tuple[Branch, ContactResult], limit: Literal["pairs"] | None
) -> None:
    """
    Keep unsupported evidence unchanged instead of applying the depth-only initialization rule.
    """
    branch, contact = missed_crossing
    altered = replace(contact, limit=limit)
    result, plane = adjacent_straight_contact(branch.route, altered, lambda: None, lambda e: None)
    assert result is altered and plane is None


def test_prediction_retains_the_material_plane_through_motion(
    missed_crossing: tuple[Branch, ContactResult],
) -> None:
    """
    Match the full moving-sheet projection and retain its identity in the cached first correction.
    """
    branch, contact = missed_crossing
    result = select_recovery(((branch, contact),), lambda: None, lambda e: None)
    assert result.choice is not None and len(result.initial_steps) == 1
    cached = result.initial_steps[0]
    assert cached.measurement is result.choice[1] and cached.plane is not None
    assert cached.source is branch.route
    model = MovableBends(branch.route)
    bound = Separation.from_measurement(model, branch.route, cached.measurement)
    assert bound is not None
    moving = replace(bound, plane=cached.plane)
    values = list(model.initial)
    values[1] -= 0.01
    changed = tuple(values)
    pieces = model.pieces(changed)
    changed_route = model.route(changed)
    assert changed_route is not None
    first_sheet = next(
        piece for region, piece in zip(regions(changed_route), pieces) if region == cached.plane
    )
    normal = unit(cross(first_sheet.pose.tangent, first_sheet.pose.width))
    frozen_at_changed_pose = replace(bound, axis=normal)
    for side in Side:
        assert moving.gap(changed, side) == pytest.approx(
            frozen_at_changed_pose.gap(changed, side), abs=1e-12
        )


def test_missing_exact_crossing_keeps_the_original_uncertainty(
    missed_crossing: tuple[Branch, ContactResult], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A missed analytic witness must not substitute either a correction target or clearance.
    """
    branch, contact = missed_crossing
    monkeypatch.setitem(vars(recovery_evidence), "straight_witness", lambda *_args: None)
    result, plane = adjacent_straight_contact(branch.route, contact, lambda: None, lambda e: None)
    assert result is contact and plane is None


def test_cached_plane_recovers_only_after_a_strict_complete_contact_certificate(
    missed_crossing: tuple[Branch, ContactResult],
) -> None:
    """
    Clear the original measured crossing within the existing shared update/time/pair allowance.
    """
    branch, contact = missed_crossing
    selection = select_recovery(((branch, contact),), lambda: None, lambda e: None)
    cached = selection.initial_steps[0]
    result = recover(
        cached.source,
        cached.measurement,
        1267,
        1e-5,
        lambda: None,
        lambda e: None,
        maximum_cpu_seconds=selection.maximum_cpu_seconds,
        maximum_seconds=selection.maximum_seconds,
        initial_step=cached,
    )
    assert result.route is not None and result.contact is not None
    assert result.contact.status == "separated" and result.pairs <= 1267
    assert result.detail["iterations"] <= 4 and result.detail["cpu_seconds"] <= 0.35
    assert cached.plane is not None
    invalid = replace(cached, plane=replace(cached.plane, straight=False))
    with pytest.raises(ValueError, match="first confirmed straight sheet"):
        recover(
            cached.source,
            cached.measurement,
            1267,
            1e-5,
            lambda: None,
            lambda e: None,
            initial_step=invalid,
        )


@pytest.fixture(scope="module")
def proven_crossings() -> tuple[tuple[Branch, ContactResult], ...]:
    """
    Use the frozen N4case164target directly, retaining its three original rejected orientation branches.
    """
    case = next(case for case in load()["cases"] if case["id"] == "range-fe65-case-164")
    source = targets(case["targets"])
    frames = Frames.create(source)
    radius = source.diameter_mm / 2 / PinchLimit().fraction * (1 + 1e-9)
    result = construct(
        Boundary(source, radius),
        frames,
        (0.5,),
        1e-5,
        lambda: None,
        lambda event: None,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
    )
    assert result.route is None and len(result.rejected) == 3
    return result.rejected


@pytest.mark.parametrize("roots, expected_pair", (((0, 1), (0, 3)), ((1, 0), (2, 6))))
def test_proven_crossings_prepare_initial_sheet_without_mutating_raw_contact(
    proven_crossings: tuple[tuple[Branch, ContactResult], ...],
    roots: tuple[int, int],
    expected_pair: tuple[int, int],
) -> None:
    """
    Confirm both actual interiors for direct and fold-attached crossings; retain historical preparation.
    """
    branch, original = next(item for item in proven_crossings if item[0].roots == roots)
    raw_witness = original.witness
    assert original.status == "penetration" and raw_witness is not None
    unchanged, plane = adjacent_straight_contact(
        branch.route, original, lambda: None, lambda e: None
    )
    assert unchanged is original and plane is None
    events: list[dict[str, Any]] = []
    stronger, plane = adjacent_straight_contact(
        branch.route,
        original,
        lambda: None,
        events.append,
        policy=recovery_evidence.EvidencePolicy.CONFIRMED_SHEETS,
    )
    assert original.witness is raw_witness and stronger.status == "penetration"
    assert stronger.pairs_checked == original.pairs_checked and stronger.witness is not None
    witness = stronger.witness
    assert witness.pieces == expected_pair and plane == regions(branch.route)[expected_pair[0]]
    assert plane is not None and plane.straight
    for index in witness.pieces:
        assert occupied_coordinates(branch.route.pieces[index], witness.point, 4, 0.75) is not None
    assert events[-1]["status"] == (
        "confirmed_attached_straight" if roots == (0, 1) else "confirmed_straight_pair"
    )


def test_missing_core_witness_does_not_reinterpret_proven_fold_penetration(
    proven_crossings: tuple[tuple[Branch, ContactResult], ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Failure to strengthen evidence preserves penetration instead of granting a different plane or clearance.
    """
    branch, original = next(item for item in proven_crossings if item[0].roots == (0, 1))
    monkeypatch.setitem(vars(recovery_evidence), "straight_witness", lambda *_args: None)
    unchanged, plane = adjacent_straight_contact(
        branch.route,
        original,
        lambda: None,
        lambda e: None,
        policy=recovery_evidence.EvidencePolicy.CONFIRMED_SHEETS,
    )
    assert unchanged is original and plane is None


def test_case164_selects_and_certifies_existing_sheet_correction_with_original_budget() -> None:
    """
    Clear the confirmed intersection without extra roots, updates, shared pairs or changed fixed targets.
    """
    case = next(case for case in load()["cases"] if case["id"] == "range-fe65-case-164")
    source = targets(case["targets"])
    events: list[dict[str, Any]] = []
    result = solve(
        source,
        Settings.parse(case["settings"]),
        lambda: None,
        events.append,
        native_point_tolerance_mm=case["native_point_tolerance_mm"],
    )
    assert result.route is not None and result.route.targets == source
    assert result.detail["contact"] == "separated"
    assert result.detail["cap_error_mm"] < 1e-7 and result.detail["material_metric_error"] < 1e-10
    construction = result.detail["construction"]
    recovery = construction["recovery"]
    assert recovery["selection"]["roots"] == (1, 0)
    assert recovery["status"] == "separated" and 1 <= recovery["iterations"] <= 4
    assert recovery["cpu_seconds"] <= 0.35 and recovery["elapsed_seconds"] <= 2
    assert construction["contact_pairs"] <= 2048
    predicted = {tuple(row["roots"]): row for row in recovery["selection"]["predictions"]}
    assert predicted[(1, 0)]["initial_trust_steps"] == 3
    assert predicted[(0, 1)]["initial_trust_steps"] == 1
    replacement = next(
        event for event in events if event.get("stage") == "recovery_prediction_replaced"
    )
    assert replacement["roots"] == (1, 0) and replacement["original_roots"] == (0, 1)
    assert replacement["actual_gap_mm"] > 0
    first_motion = next(
        event
        for event in events
        if event.get("stage") == "joint_separation_recovery"
        and event.get("status") == "gap_improved"
    )
    assert replacement["actual_gap_mm"] == pytest.approx(first_motion["gap_mm"], abs=1e-12)
    assert any(event.get("status") == "confirmed_straight_pair" for event in events)
