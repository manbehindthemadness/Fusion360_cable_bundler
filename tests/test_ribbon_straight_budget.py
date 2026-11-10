"""
Bound nearly cancelling straight allocations without clipping coefficients or moving physical targets.
"""

from __future__ import annotations

import math
from dataclasses import replace
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_feature_insertion import reclosure
from experiments.experiment_ribbon_feature_insertion.features import chains
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.linear_fit import least_squares
from experiments.experiment_ribbon_feature_insertion.reclosure import Unclosed
from experiments.experiment_ribbon_feature_insertion.repair import nearest
from experiments.experiment_ribbon_feature_insertion.solve import construct
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Pose, Straight
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from tests.test_ribbon_feature_insertion import _targets


@pytest.mark.parametrize("epsilon", (1e-3, 1e-4))
def test_nearly_cancelling_rays_use_exact_budget_face_instead_of_huge_travel(
    epsilon: float,
) -> None:
    """
    Retain endpoint equality while minimizing a missed transverse objective inside finite travel.
    """
    old = least_squares([[1.0, -1.0]], [0.0], [[0.0, epsilon]], [1.0], 2)
    assert old is not None and math.fsum(old) > 1000
    bounded = least_squares([[1.0, -1.0]], [0.0], [[0.0, epsilon]], [1.0], 2, maximum_sum=10.0)
    assert bounded == pytest.approx([5.0, 5.0])
    assert bounded[0] - bounded[1] == pytest.approx(0.0, abs=1e-12)
    assert 1.0 - epsilon * bounded[1] > 0.99


def test_interior_optimum_is_unchanged_and_over_budget_hard_closure_is_unresolved() -> None:
    """
    Do not snap an infeasible cap equation into a passing bounded allocation.
    """
    assert least_squares(
        [[1.0, 1.0]], [2.0], [[1.0, 0.0]], [0.5], 2, maximum_sum=5.0
    ) == pytest.approx([0.5, 1.5])
    assert least_squares([[1.0, 1.0]], [20.0], [], [], 2, maximum_sum=10.0) is None


@pytest.mark.parametrize("budget", (-1.0, math.inf, math.nan, True))
def test_invalid_budget_rejects_before_linear_work(budget: float) -> None:
    """
    Reject disabled or nonfinite budgets instead of treating them as an unbounded allocation.
    """
    with pytest.raises(ValueError, match="budget"):
        least_squares([], [], [[1.0]], [1.0], 1, maximum_sum=budget)


def _cone(epsilon: float) -> Model:
    """
    Model only a three-ray affine cone, without saved routes or geometry feasibility claims.
    """
    model = Mock(
        spec=Model,
        size=5,
        topology=SimpleNamespace(folds=(Mock(), Mock())),
        source=SimpleNamespace(targets=replace(_targets(), end=Vector3(0, 1, 0), diameter_mm=1.0)),
    )
    columns = ((1, 0, 0), (0, 0, 0), (-1, epsilon, 0), (0, 0, 0), (0, -1, 0))
    model.equations.return_value = columns, (0, 1, 0)

    def endpoint(values: tuple[float, ...]) -> Pose:
        """
        Recompute actual displacement from the same affine coefficients.
        """
        point = Vector3(values[0] - values[2], epsilon * values[2] - values[4], 0)
        return Pose(point, Vector3(1, 0, 0), Vector3(0, 1, 0))

    model.endpoint.side_effect = endpoint
    return model


def test_bounded_nearest_preserves_real_residual_until_the_cone_opens() -> None:
    """
    Keep angular correction necessary instead of declaring a huge cancelling endpoint closure.
    """
    narrow = _cone(1e-3)
    old = nearest(narrow, lambda: None)
    bounded = nearest(narrow, lambda: None, maximum_straight_mm=10)
    assert old.error < 1e-7 and math.fsum(old.values) > 1000
    assert math.fsum(bounded.values) <= 10 + 1e-8 and bounded.error > 0.99
    opened = nearest(_cone(0.5), lambda: None, maximum_straight_mm=10)
    assert opened.error < 1e-7 and math.fsum(opened.values) <= 10


@pytest.mark.parametrize("scale", (1.0, 20.0))
def test_guide_budget_reaches_closed_material_before_contact_at_multiple_scales(
    scale: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Exercise real allocation/reclosure with frozen caps and the original certificate boundary.
    """
    frames = Frames.create(_targets(scale))
    budget = frames.guide.distances[-1]
    calls: list[FoldRoute] = []

    def certificate(
        route: FoldRoute,
        *,
        maximum_pairs: int,
        checkpoint: Callable[[], None],
        **options: Any,
    ) -> ContactResult:
        """
        Verify the actual geometry at the external contact boundary; do not claim physical clearance.
        """
        del options
        checkpoint()
        calls.append(route)
        assert cap_error(route) < 1e-7 and material_error(route) < 1e-10
        straight = math.fsum(
            p.geometry.material_length_mm for p in route.pieces if isinstance(p.geometry, Straight)
        )
        assert straight <= budget + 1e-8 * route.targets.diameter_mm
        return ContactResult("separated", maximum_pairs)

    monkeypatch.setattr(
        "experiments.experiment_ribbon_feature_insertion.solve.inspect_contact", certificate
    )
    result = construct(
        Boundary(frames.targets, 0.101 * scale),
        frames,
        (0.5,),
        1e-5 * scale,
        lambda: None,
        lambda e: None,
        maximum_straight_mm=budget,
    )
    assert result.route is not None and calls
    assert result.route.targets is frames.targets and result.contact_pairs <= 2048


def test_original_and_pending_branch_continuations_keep_the_same_straight_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Propagate the frozen domain through original refinement and the last pending-branch continuation.
    """
    frames = Frames.create(_targets())
    boundary = Boundary(frames.targets, 0.101)
    chain = chains(boundary, frames, (0.5,), lambda: None, lambda e: None)[0]
    budget = frames.guide.distances[-1]
    monkeypatch.setattr(
        "experiments.experiment_ribbon_feature_insertion.solve.chains", Mock(return_value=(chain,))
    )
    monkeypatch.setattr(
        "experiments.experiment_ribbon_feature_insertion.solve.fit", Mock(return_value=None)
    )
    closure = nearest(Model(boundary, chain.topology), lambda: None, maximum_straight_mm=budget)
    action = Mock(return_value=Unclosed(chain, closure))
    monkeypatch.setattr("experiments.experiment_ribbon_feature_insertion.solve.refine", action)
    result = construct(
        boundary, frames, (0.5,), 1e-5, lambda: None, lambda e: None, maximum_straight_mm=budget
    )
    assert result.route is None and result.contacts == 0
    assert [call.args[3] for call in action.call_args_list] == [2, 4]
    assert all(call.kwargs["maximum_straight_mm"] == budget for call in action.call_args_list)


def test_physical_factor_continuation_cannot_drop_the_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve the same domain when the existing alternative factor policy is consulted.
    """
    frames = Frames.create(_targets())
    boundary = Boundary(frames.targets, 0.101)
    chain = chains(boundary, frames, (0.5,), lambda: None, lambda e: None)[0]
    budget = frames.guide.distances[-1]
    pending = Unclosed(
        chain, nearest(Model(boundary, chain.topology), lambda: None, maximum_straight_mm=budget)
    )
    action = Mock(side_effect=(pending, None))
    monkeypatch.setattr(reclosure, "refine", action)
    answer = reclosure.refine_preserving_legacy(
        boundary, pending, 1e-5, 2, lambda: None, lambda e: None, maximum_straight_mm=budget
    )
    assert answer is pending and action.call_count == 2
    assert all(call.kwargs["maximum_straight_mm"] == budget for call in action.call_args_list)
