"""
Preserve physical fold branches across quadratic ordering changes without removing legacy fallback.
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym import Config, Goal, Scene
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_feature_insertion import reclosure
from experiments.experiment_ribbon_feature_insertion.allocation import fit
from experiments.experiment_ribbon_feature_insertion.continuation import BranchPolicy, closest
from experiments.experiment_ribbon_feature_insertion.features import chains
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.repair import changed, nearest, reframed
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_locked_solver.solver_v2 import solve


def _trigger() -> Scene:
    """
    Recreate the recorded gym inputs without importing generated diagnostic artifacts.
    """
    return Scene(Config(2633163145, 2, 0.75, 300, 300), Goal(0, 1, 0), Goal(1, 0, 0))


def test_factor_choice_is_independent_of_root_order_and_dimensional_scale() -> None:
    """
    Match actual rotations while ignoring root numbering, radius and profile dimensions.
    """
    first = (fold(1, 1, 0.7, 0.2, 0), fold(1, 1, -0.8, -0.2, 0))
    other = (fold(1, 1, -1.5, 0.8, 0), fold(1, 1, 1.3, -0.8, 0))
    scaled = tuple(
        replace(
            piece,
            radius_mm=10,
            width_mm=10,
            before_mm=piece.before_mm * 10,
            after_mm=piece.after_mm * 10,
        )
        for piece in first
    )
    assert closest(first, (other, scaled)) is scaled
    assert closest(first, (scaled, other)) is scaled
    assert closest(first, (first, first)) is None
    assert closest(first, ((first[0],),)) is None


def test_small_frame_update_cannot_silently_reverse_first_bend_pair() -> None:
    """
    Reproduce the logged quadratic-order swap under a half-step orientation correction.
    """
    targets = _trigger().targets
    boundary = Boundary(targets, 0.3765060244728916)
    frames = Frames.create(targets)
    chain = next(
        c
        for c in chains(boundary, frames, (0.5,), lambda: None, lambda event: None)
        if c.roots == (1, 1)
    )
    references = changed(
        chain.targets, [0.10197677464498596, -0.15572554539760064, -0.19911865440782603], 0.5
    )
    legacy = reframed(boundary, chain, references)
    continuous = reframed(boundary, chain, references, branch_policy=BranchPolicy.CONTINUOUS)
    assert legacy is not None and continuous is not None
    assert legacy.factor_discontinuity and not continuous.factor_discontinuity
    assert legacy.topology.folds[0].angle_radians > 0
    assert continuous.topology.folds[0].angle_radians < 0
    assert continuous.roots == chain.roots
    assert continuous.targets == references


def test_failed_continuation_retains_legacy_reclosure_and_hard_errors_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve unresolved legacy progress and never mask caller cancellation as another attempt.
    """
    targets = _trigger().targets
    boundary = Boundary(targets, 0.3765060244728916)
    chain = chains(boundary, Frames.create(targets), (0.5,), lambda: None, lambda event: None)[-1]
    pending = reclosure.Unclosed(chain, nearest(Model(boundary, chain.topology), lambda: None))
    original = replace(pending, iteration=2)
    refine = Mock(side_effect=[original, None])
    monkeypatch.setattr(reclosure, "refine", refine)
    assert (
        reclosure.refine_preserving_legacy(
            boundary, pending, 1e-5, 2, lambda: None, lambda event: None
        )
        is original
    )
    assert refine.call_count == 2
    assert refine.call_args.kwargs["branch_policy"] is BranchPolicy.CONTINUOUS
    refine.reset_mock(side_effect=True)
    refine.side_effect = TimeoutError("caller limit")
    with pytest.raises(TimeoutError, match="caller limit"):
        reclosure.refine_preserving_legacy(
            boundary, pending, 1e-5, 2, lambda: None, lambda event: None
        )
    assert refine.call_count == 1


@pytest.mark.parametrize("variant", ("continuous_legacy", "worse_site", "improved_site"))
def test_closed_legacy_requires_detected_jump_and_nonworsening_replacement(
    monkeypatch: pytest.MonkeyPatch, variant: str
) -> None:
    """
    Avoid extra refinement for stable factors and retain better existing closed allocations.
    """
    targets = _trigger().targets
    boundary = Boundary(targets, 0.3765060244728916)
    chain = chains(boundary, Frames.create(targets), (0.5,), lambda: None, lambda event: None)[0]
    allocation = fit(boundary, chain, 1e-5, lambda: None, lambda event: None)
    assert allocation is not None
    legacy = replace(
        allocation, chain=replace(chain, factor_discontinuity=variant != "continuous_legacy")
    )
    continuous = replace(
        legacy, score=legacy.score + 1 if variant == "worse_site" else legacy.score / 2
    )
    refine = Mock(side_effect=[legacy, continuous])
    monkeypatch.setattr(reclosure, "refine", refine)
    pending = reclosure.Unclosed(chain, nearest(Model(boundary, chain.topology), lambda: None))
    result = reclosure.refine_preserving_legacy(
        boundary, pending, 1e-5, 2, lambda: None, lambda event: None
    )
    assert result is (continuous if variant == "improved_site" else legacy)
    assert refine.call_count == (1 if variant == "continuous_legacy" else 2)


@pytest.mark.parametrize("source", ("trigger", "legacy_control"))
def test_corrected_routing_closes_and_preserves_material_with_fixed_contact_budget(
    source: str,
) -> None:
    """
    Cover the failing gym input and the control that rejects continuity-only replacement.
    """
    targets = (
        _trigger().targets
        if source == "trigger"
        else Scene(Config(1689995010, 2, 0.75, 300, 300), Goal(3, 9, 1), Goal(9, 6, 1)).targets
    )
    result = solve(targets, Settings(0, False, True), lambda: None, lambda event: None)
    assert result.route is not None
    assert cap_error(result.route) < 1e-7 and material_error(result.route) < 1e-10
    assert result.detail["construction"]["contact_pairs"] <= 2048
    assert result.detail["construction"]["status"] == "separated"
