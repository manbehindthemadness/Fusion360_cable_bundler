"""
Preserve signed material-boundary evidence and spend only the original initial restoration allocation.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation import model as retraction
from experiments.experiment_ribbon_bend_relocation.solve import Result as Recovered
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_feature_insertion import reclosure
from experiments.experiment_ribbon_feature_insertion import solve as construction
from experiments.experiment_ribbon_feature_insertion.continuation import BranchPolicy
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.reclosure import Unclosed
from experiments.experiment_ribbon_feature_insertion.repair import Closure
from experiments.experiment_ribbon_feature_insertion.selection import Policy
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight, pose_error
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import initial_closure as runner
from experiments.experiment_ribbon_terminal_hardware import alias_refinement
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_construction import Roots
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_initial_closure import _controller, _missing_direction


@pytest.mark.parametrize("scale", (0.2, 1.0, 8.0))
@pytest.mark.parametrize("sign,bank", ((-1, -0.5), (-1, 0.0), (1, 0.5)))
def test_split_preserves_combined_orientation_and_material(
    scale: float, sign: int, bank: float
) -> None:
    """
    Splitting either signed near-halfturn preserves ordered orientation, dimensions and material metric.
    """
    geometry = fold(scale, 2 * (scale / 2 + scale * 0.1), sign * math.radians(179), bank, 0)
    source = _route((Straight(2 * scale), geometry, Straight(scale)))
    source = replace(source, targets=replace(source.targets, diameter_mm=scale), radius_mm=scale)
    refined = alias_refinement.split(source, 0)
    assert refined.targets is source.targets and refined.radius_mm == source.radius_mm
    assert pose_error(refined.pieces[-1].end_pose(), source.pieces[-1].end_pose())[1] < 1e-12
    halves = [
        piece.geometry for piece in refined.pieces if not isinstance(piece.geometry, Straight)
    ]
    assert len(halves) == 2
    assert all(
        member == replace(geometry, angle_radians=geometry.angle_radians / 2) for member in halves
    )
    assert material_error(refined) < 1e-12
    assert refined.material_length_mm >= source.material_length_mm - 1e-12


def test_split_has_no_parent_six_event_limit() -> None:
    """
    A local refinement does not impose a global event count restriction.
    """
    source = _route(tuple(fold(1, 1.2, 0.2, 0.1, 0) for _ in range(8)))
    refined = alias_refinement.split(source, 7)
    assert len(refined.pieces) == 9
    with pytest.raises(ValueError, match="existing"):
        alias_refinement.split(source, 8)


@pytest.mark.parametrize("remaining", (0, 1, 2))
def test_failed_closure_charges_started_work_without_roots_or_retry(
    monkeypatch: pytest.MonkeyPatch, remaining: int
) -> None:
    """
    A projection decline consumes its started Newton even when no geometry can be returned.
    """
    boundary, pending = _missing_direction()
    pending = replace(pending, alias_folds=(0,))
    roots = Roots(newton_limit=remaining)
    projection = Mock(return_value=None)
    monkeypatch.setitem(vars(retraction), "projected", projection)
    assert alias_refinement.construct(boundary, pending, 3e-5, roots, Mock(), Mock()) is None
    assert roots.attempted == 0 and roots.reclosures == 1
    assert roots.newton_steps == min(remaining, 1)
    assert projection.call_count == min(remaining, 1)


def test_no_alias_and_outer_cancellation_cannot_start_a_refinement() -> None:
    """
    Missing event evidence spends no geometry; external cancellation propagates intact.
    """
    boundary, pending = _missing_direction()
    roots = Roots()
    record = Mock()
    assert alias_refinement.construct(boundary, pending, 3e-5, roots, Mock(), record) is None
    assert roots.newton_steps == roots.reclosures == roots.attempted == 0
    record.assert_not_called()
    with pytest.raises(TimeoutError, match="outer"):
        alias_refinement.construct(
            boundary,
            replace(pending, alias_folds=(0,)),
            3e-5,
            roots,
            Mock(side_effect=TimeoutError("outer")),
            record,
        )
    assert roots.newton_steps == roots.reclosures == roots.attempted == 0


@pytest.mark.parametrize("policy", (BranchPolicy.CONTINUOUS, BranchPolicy.INDEX))
def test_rejected_halfturn_trial_evidence_survives_accepted_halfstep(
    monkeypatch: pytest.MonkeyPatch, policy: BranchPolicy
) -> None:
    """
    Record an actual continuous-factor alias without another trial or changing legacy root-index semantics.
    """
    boundary, original = _missing_direction()
    geometries = (fold(1, 1.2, math.radians(179), 0.2, 0), *original.chain.topology.folds[1:])
    chain = replace(original.chain, topology=replace(original.chain.topology, folds=geometries))
    pending = replace(
        original,
        chain=chain,
        closure=Closure(original.closure.values, (3, 0, 0), 3),
        branch_policy=policy,
    )
    wrapped = replace(
        chain,
        topology=replace(
            chain.topology,
            folds=(replace(geometries[0], angle_radians=-math.radians(179)), *geometries[1:]),
        ),
    )
    nearby = replace(
        chain,
        topology=replace(
            chain.topology,
            folds=(replace(geometries[0], angle_radians=math.radians(178)), *geometries[1:]),
        ),
    )
    changes = Mock(side_effect=(wrapped, nearby))
    measured = Mock(
        side_effect=(
            Closure(pending.closure.values, (4, 0, 0), 4),
            Closure(pending.closure.values, (2, 0, 0), 2),
        )
    )
    monkeypatch.setitem(vars(reclosure), "correction", Mock(return_value=[0.1, 0, 0]))
    monkeypatch.setitem(vars(reclosure), "reframed", changes)
    monkeypatch.setitem(vars(reclosure), "nearest", measured)
    result = reclosure.refine(boundary, pending, 3e-5, 1, Mock(), Mock())
    assert isinstance(result, Unclosed)
    assert result.chain is nearby and result.closure.error == 2
    assert result.alias_folds == ((0,) if policy is BranchPolicy.CONTINUOUS else ())
    assert changes.call_count == measured.call_count == 2


@pytest.mark.parametrize("indices", ((-1,), (2,), (0, 0), (1, 0), (True,)))
def test_alias_evidence_requires_distinct_ordered_existing_folds(indices: tuple[int, ...]) -> None:
    """
    Malformed or stale identities cannot request a new material event.
    """
    _, pending = _missing_direction()
    with pytest.raises(ValueError, match="existing aliased"):
        replace(pending, alias_folds=indices)


def test_construction_keeps_best_completed_refinement_without_another_solve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Initial recovery receives the actual continuation progress and its event evidence.
    """
    boundary, pending = _missing_direction()
    first = replace(pending, closure=replace(pending.closure, error=1.0), iteration=2)
    best = replace(first, closure=replace(first.closure, error=0.8), iteration=6, alias_folds=(1,))
    measured = Mock(return_value=pending.closure)
    corrections = Mock(side_effect=(first, best))
    monkeypatch.setitem(vars(construction), "chains", Mock(return_value=(pending.chain,)))
    monkeypatch.setitem(vars(construction), "fit", Mock(return_value=None))
    monkeypatch.setitem(vars(construction), "nearest", measured)
    monkeypatch.setitem(vars(construction), "refine", corrections)
    result = construction.construct(
        boundary, Frames.create(boundary.targets), (0.5,), 3e-5, Mock(), Mock()
    )
    assert result.route is None
    assert min(result.closure_candidates, key=lambda value: value.closure.error) is best
    measured.assert_called_once()
    assert corrections.call_count == 2


@pytest.mark.parametrize("root_count", (8, 9))
def test_alias_refinement_and_adaptive_child_share_actions_newton_pairs_and_roots(
    monkeypatch: pytest.MonkeyPatch, root_count: int
) -> None:
    """
    A three-correction split leaves exactly three updates,21Newton and the unused pair/root pool.
    """
    result, boundary, route, terminal = _controller()
    pending = replace(result.closure_candidates[0], alias_folds=(0,))
    result = replace(result, closure_candidates=(pending,))
    planner = Mock()
    monkeypatch.setitem(vars(runner), "plan", planner)

    def construct(*args: Any) -> FoldRoute:
        """
        Account already-started cap restoration before returning its candidate.
        """
        args[3].newton_steps = 3
        args[3].reclosures = 1
        return route

    monkeypatch.setitem(vars(runner), "refine_alias", construct)
    monkeypatch.setitem(
        vars(runner), "inspect_contact", Mock(return_value=ContactResult("unresolved", 105))
    )
    child = Mock(
        return_value=Recovered(
            route,
            ContactResult("separated", 262),
            {
                "iterations": 2,
                "newton_steps": 8,
                "contacts": 1,
                "contact_pairs": 262,
                "contact_seconds": 0.01,
                "roots_attempted": root_count,
                "declined_roots": 7,
                "local_reclosures": 1,
                "stop_reason": "accepted",
            },
        )
    )
    monkeypatch.setitem(vars(runner), "continue_events", child)
    if root_count > 8:
        with pytest.raises(ArithmeticError, match="remaining roots"):
            runner.recover(
                result,
                boundary,
                terminal,
                3e-5,
                30,
                Mock(),
                Mock(),
                selection_policy=Policy.MONOTONIC,
            )
    else:
        updated, detail = runner.recover(
            result, boundary, terminal, 3e-5, 30, Mock(), Mock(), selection_policy=Policy.MONOTONIC
        )
        assert updated.route is route and detail is not None
        assert detail["iterations"] == 3 and detail["newton_steps"] == 11
        assert detail["pairs"] == 367 and detail["roots_attempted"] == 8
        assert detail["local_reclosures"] == 2
        work = child.call_args.kwargs["work"]
        assert work.updates == 3 and work.newton_steps == 21 and work.pairs == 1943
        assert 0 < work.cpu_seconds < 0.4 and 0 < work.wall_seconds < 2
    planner.assert_not_called()


@pytest.mark.parametrize("observed_alias", (False, True))
def test_retained_progress_preserves_original_cone_entry_without_an_alias(
    monkeypatch: pytest.MonkeyPatch, observed_alias: bool
) -> None:
    """
    Better unfinished progress cannot replace the established cone domain unless it carries alias evidence.
    """
    from experiments.experiment_ribbon_feature_insertion.solve import Result
    from experiments.experiment_ribbon_terminal_hardware import cone_escape
    from experiments.experiment_ribbon_terminal_hardware.gate import Gate

    boundary, original = _missing_direction()
    progressed = replace(
        original,
        closure=replace(original.closure, residual=(-0.1, 0.0, 0.0), error=0.1),
        iteration=2,
        alias_folds=(0,) if observed_alias else (),
    )
    assert cone_escape.plan(boundary, original, Mock()) is not None
    assert cone_escape.plan(boundary, progressed, Mock()) is None
    result = Result(
        None,
        None,
        "no_fixed_radius_closure",
        0,
        0.0,
        0,
        0,
        closure_candidates=(original, progressed),
    )
    terminal = Mock(spec=Gate)
    terminal.hardware = Mock(targets=boundary.targets)
    planner = Mock(wraps=cone_escape.plan)
    alias = Mock(return_value=None)
    constructor = Mock(return_value=None)
    monkeypatch.setitem(vars(runner), "plan", planner)
    monkeypatch.setitem(vars(runner), "refine_alias", alias)
    monkeypatch.setitem(vars(runner), "construct", constructor)
    updated, detail = runner.recover(
        result,
        boundary,
        terminal,
        3e-5,
        30,
        Mock(),
        Mock(),
        selection_policy=Policy.MONOTONIC,
    )
    assert updated.route is None and detail is not None
    if observed_alias:
        planner.assert_not_called()
        constructor.assert_not_called()
        assert alias.call_args.args[1] is progressed
    else:
        alias.assert_not_called()
        assert planner.call_args.args[1] is original
        constructor.assert_called_once()
