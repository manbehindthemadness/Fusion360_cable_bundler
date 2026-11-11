"""
Keep requested mating precision inside the original bounded feature reclosure action.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_feature_insertion import reclosure
from experiments.experiment_ribbon_feature_insertion.allocation import Allocation
from experiments.experiment_ribbon_feature_insertion.features import Chain
from experiments.experiment_ribbon_feature_insertion.reclosure import Unclosed
from experiments.experiment_ribbon_feature_insertion.repair import Closure
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Straight
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from tests.test_ribbon_aesthetic import _route


def _system(diameter: float) -> tuple[Boundary, Chain, Allocation, Allocation]:
    """
    Author fixed targets and two independently specified endpoints, without a saved case or solver call.
    """
    route = _route((Straight(10 * diameter),))
    targets = replace(route.targets, diameter_mm=diameter)
    exact = FoldRoute(targets, route.pieces, diameter)
    displaced = FoldRoute(
        targets,
        (PlacedPiece(route.pieces[0].pose, Straight(10 * diameter + 6e-10), "authored endpoint"),),
        diameter,
    )
    chain = Mock(spec=Chain, roots=(0, 0), targets=(), topology=())
    return (
        Boundary(targets, diameter),
        chain,
        Allocation(exact, chain, (10.0,), 0.0, 1),
        Allocation(displaced, chain, (10.0 + 6e-10 / diameter,), 0.0, 1),
    )


def _math(monkeypatch: pytest.MonkeyPatch, chain: Chain, trials: list[Closure]) -> Mock:
    """
    Control only angular/placement dispositions to isolate stopping policy and original step accounting.
    """
    correction = Mock(return_value=[0.001])
    replacements: dict[str, Any] = {
        "correction": correction,
        "changed": Mock(return_value=chain.targets),
        "reframed": Mock(return_value=chain),
        "Model": Mock(),
        "nearest": Mock(side_effect=trials),
    }
    for name, replacement in replacements.items():
        monkeypatch.setitem(vars(reclosure), name, replacement)
    return correction


@pytest.mark.parametrize("diameter", (0.75, 1.0, 10.0, 1000.0))
def test_mating_goal_spends_one_original_step_instead_of_returning_loose_closure(
    monkeypatch: pytest.MonkeyPatch,
    diameter: float,
) -> None:
    """
    Small normalized residuals cannot bypass actual caps or become blocked by a dimensionless gain floor.
    """
    from experiments.experiment_ribbon_feature_insertion.closure_goal import ClosureGoal

    boundary, chain, exact, displaced = _system(diameter)
    initial = Closure(displaced.values, (6e-10 / diameter, 0, 0), 6e-10 / diameter)
    trial = Closure(exact.values, (0, 0, 0), 0.0)
    correction = _math(monkeypatch, chain, [trial])
    allocation = Mock(return_value=displaced)
    monkeypatch.setitem(vars(reclosure), "closure_allocation", allocation)
    monkeypatch.setitem(vars(reclosure), "fit", Mock(return_value=exact))
    legacy = reclosure.refine(
        boundary, Unclosed(chain, initial), 1e-5, 4, lambda: None, lambda e: None
    )
    assert legacy is displaced and correction.call_count == 0
    requested = Unclosed(chain, initial, goal=ClosureGoal.MATING)
    result = reclosure.refine(boundary, requested, 1e-5, 4, lambda: None, lambda e: None)
    assert result is exact and correction.call_count == 1
    assert isinstance(result, Allocation)
    assert result.route.targets is displaced.route.targets


def test_guide_fit_cannot_lose_mating_precision_of_already_computed_closure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Use only the existing feasible coordinates when an optional guide optimum misses the requested proof goal.
    """
    from experiments.experiment_ribbon_feature_insertion.closure_goal import ClosureGoal

    boundary, chain, exact, displaced = _system(1.0)
    initial = Closure((9.0,), (1e-3, 0, 0), 1e-3)
    trial = Closure(exact.values, (0, 0, 0), 0.0)
    correction = _math(monkeypatch, chain, [trial])
    monkeypatch.setitem(vars(reclosure), "fit", Mock(return_value=displaced))
    retained = Mock(return_value=exact)
    monkeypatch.setitem(vars(reclosure), "closure_allocation", retained)
    result = reclosure.refine(
        boundary,
        Unclosed(chain, initial, goal=ClosureGoal.MATING),
        1e-5,
        4,
        lambda: None,
        lambda e: None,
        maximum_straight_mm=20,
    )
    assert result is exact and correction.call_count == 1 and retained.call_count == 1
    assert retained.call_args.args[2] is trial.values
    assert retained.call_args.kwargs["maximum_straight_mm"] == 20


def test_unfinished_precision_survives_explicit_bounded_continuation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Retain the requested proof goal and total accepted-step count rather than reverting to ordinary closure.
    """
    from experiments.experiment_ribbon_feature_insertion.closure_goal import ClosureGoal

    boundary, chain, exact, displaced = _system(1.0)
    initial = Closure((9.0,), (1e-3, 0, 0), 1e-3)
    middle = Closure((9.5,), (6e-10, 0, 0), 6e-10)
    final = Closure(exact.values, (0, 0, 0), 0.0)
    correction = _math(monkeypatch, chain, [middle, final])
    monkeypatch.setitem(vars(reclosure), "fit", Mock(side_effect=[displaced, exact]))
    monkeypatch.setitem(vars(reclosure), "closure_allocation", Mock(return_value=displaced))
    first = reclosure.refine(
        boundary,
        Unclosed(chain, initial, goal=ClosureGoal.MATING),
        1e-5,
        1,
        lambda: None,
        lambda e: None,
    )
    assert isinstance(first, Unclosed) and first.iteration == 1 and first.goal is ClosureGoal.MATING
    second = reclosure.refine(boundary, first, 1e-5, 1, lambda: None, lambda e: None)
    assert second is exact and correction.call_count == 2


def test_four_steps_cannot_become_an_extra_precision_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep a progressing near-closed result unfinished at its original cap without trying a fifth step.
    """
    from experiments.experiment_ribbon_feature_insertion.closure_goal import ClosureGoal

    boundary, chain, _, displaced = _system(1.0)
    monkeypatch.setitem(vars(reclosure), "fit", Mock(return_value=displaced))
    monkeypatch.setitem(vars(reclosure), "closure_allocation", Mock(return_value=displaced))
    initial = Closure((9.0,), (1e-2, 0, 0), 1e-2)
    trials = [Closure((9.0,), (v, 0, 0), v) for v in (1e-3, 1e-4, 1e-5, 6e-10)]
    correction = _math(monkeypatch, chain, trials)
    result = reclosure.refine(
        boundary,
        Unclosed(chain, initial, goal=ClosureGoal.MATING),
        1e-5,
        4,
        lambda: None,
        lambda e: None,
    )
    assert isinstance(result, Unclosed) and result.iteration == 4
    assert result.goal is ClosureGoal.MATING and correction.call_count == 4


def test_stall_and_original_source_failure_cannot_return_loose_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve original failures instead of treating a legacy-closed route as mating-ready fallback.
    """
    from experiments.experiment_ribbon_feature_insertion.closure_goal import ClosureGoal

    boundary, chain, _, displaced = _system(1.0)
    initial = Closure(displaced.values, (6e-10, 0, 0), 6e-10)
    correction = _math(monkeypatch, chain, [])
    correction.return_value = None
    monkeypatch.setitem(vars(reclosure), "closure_allocation", Mock(return_value=displaced))
    pending = Unclosed(chain, initial, goal=ClosureGoal.MATING)
    assert reclosure.refine(boundary, pending, 1e-5, 4, lambda: None, lambda e: None) is None
    with pytest.raises(TimeoutError, match="original source"):
        reclosure.refine(
            boundary,
            pending,
            1e-5,
            4,
            Mock(side_effect=TimeoutError("original source")),
            lambda e: None,
        )


def test_actual_mating_ready_allocation_can_pass_before_tighter_progress_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep original fit opportunities: a stricter normalized residual cannot veto verified real cap frames.
    """
    from experiments.experiment_ribbon_feature_insertion.closure_goal import ClosureGoal

    boundary, chain, exact, displaced = _system(1.0)
    initial = Closure((9.0,), (1e-3, 0, 0), 1e-3)
    trial = Closure(displaced.values, (6e-10, 0, 0), 6e-10)
    correction = _math(monkeypatch, chain, [trial])
    monkeypatch.setitem(vars(reclosure), "fit", Mock(return_value=exact))
    result = reclosure.refine(
        boundary,
        Unclosed(chain, initial, goal=ClosureGoal.MATING),
        1e-5,
        4,
        lambda: None,
        lambda e: None,
    )
    assert result is exact and correction.call_count == 1


def test_zero_position_residual_cannot_hide_an_incorrect_ordered_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Actual frame matching remains independent of the scalar endpoint residual used for progress.
    """
    from cable_bundler.routing.geometry import Vector3
    from experiments.experiment_ribbon_feature_insertion.closure_goal import ClosureGoal
    from experiments.experiment_ribbon_fold_route.geometry import Pose

    boundary, chain, exact, _ = _system(1.0)
    pose = Pose(boundary.targets.start, boundary.targets.start_tangent, Vector3(0, 1, 2e-10))
    incorrect = replace(
        exact,
        route=FoldRoute(
            exact.route.targets,
            (PlacedPiece(pose, Straight(10), "authored frame control"),),
            1.0,
        ),
    )
    initial = Closure(exact.values, (0, 0, 0), 0.0)
    correction = _math(monkeypatch, chain, [])
    correction.return_value = None
    monkeypatch.setitem(vars(reclosure), "closure_allocation", Mock(return_value=incorrect))
    result = reclosure.refine(
        boundary,
        Unclosed(chain, initial, goal=ClosureGoal.MATING),
        1e-5,
        4,
        lambda: None,
        lambda e: None,
    )
    assert result is None and correction.call_count == 1


@pytest.mark.parametrize("rate_mm", (1e3, 1e4, 1e5))
def test_real_angular_correction_and_motion_preserve_needed_subfloor_precision(
    monkeypatch: pytest.MonkeyPatch,
    rate_mm: float,
) -> None:
    """
    An independently defined endpoint map needs a tiny angle to remove a fixed millimeter error.

    Actual finite differentiation, affine correction and Rodrigues frame motion
    run. Only topology reconstruction is an analytical boundary double; no
    complete ribbon or native acceptance is claimed.
    """
    from types import SimpleNamespace

    from cable_bundler.routing.geometry import Vector3
    from experiments.experiment_ribbon_feature_insertion import repair
    from experiments.experiment_ribbon_feature_insertion.closure_goal import ClosureGoal
    from experiments.experiment_ribbon_fold_route.geometry import Pose

    boundary, _, _, _ = _system(1.0)
    target = replace(boundary.targets, end=Vector3(1, 1, 6e-10))
    boundary = Boundary(target, 1.0)
    frame = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    chain = Mock(spec=Chain, targets=(frame,), topology=frame)
    probes: list[Pose] = []

    def model(_source: Any, current: Pose) -> Any:
        """
        Evaluate a fixed-rate endpoint map from the actual rotated frame, not a supplied Jacobian.
        """

        def endpoint(values: tuple[float, ...]) -> Pose:
            """
            Keep fixed X/Y coordinates and derive Z from the real frame's width direction.
            """
            probes.append(current)
            return Pose(
                Vector3(values[0], values[2], rate_mm * current.width.z), frame.tangent, frame.width
            )

        return SimpleNamespace(endpoint=endpoint)

    monkeypatch.setitem(vars(repair), "Model", model)
    monkeypatch.setitem(
        vars(repair),
        "reframed",
        lambda source, original, references, **kwargs: SimpleNamespace(topology=references[0]),
    )
    closure = Closure((1, 0, 1), (0, 0, -6e-10), 6e-10)
    assert repair.correction(boundary, chain, closure, lambda: None) is None
    delta = repair.correction(boundary, chain, closure, lambda: None, goal=ClosureGoal.MATING)
    assert delta is not None and 0 < max(map(abs, delta)) < 1e-12 and len(probes) == 12
    assert repair.changed(chain.targets, delta, 1.0) == chain.targets
    changed = repair.changed(chain.targets, delta, 1.0, goal=ClosureGoal.MATING)
    actual = model(boundary, changed[0]).endpoint(closure.values)
    assert abs(actual.origin.z - target.end.z) < 1e-10
