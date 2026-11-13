"""
Keep bounded mask rejection conservative while preserving actual authored feature allocations.
"""

from __future__ import annotations

import math
import random
from typing import Any
from unittest.mock import Mock, patch

import pytest

from experiments.experiment_ribbon_feature_insertion import allocation
from experiments.experiment_ribbon_feature_insertion.allocation_bounds import StraightReach
from experiments.experiment_ribbon_feature_insertion.features import chains
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from tests.test_ribbon_feature_insertion import _targets


@pytest.mark.parametrize("sign", (-1, 1))
def test_strict_coordinate_exclusion_never_accepts_a_feasible_mask(sign: int) -> None:
    """
    Reject travel in the wrong direction or beyond the sum budget while leaving boundary cases unresolved.
    """
    row = [sign * 2.0, sign * 0.5, -sign * 1.0]
    assert StraightReach([row], [sign * 3.0], 1.0).excludes((0, 1))
    assert StraightReach([row], [-sign * 0.1], 1.0).excludes((0, 1))
    assert not StraightReach([row], [sign * 2.0], 1.0).excludes((0, 1))
    assert not StraightReach([row], [sign * 2.0 + sign * 1e-8], 1.0).excludes((0, 1))
    assert not StraightReach([row], [-sign * 0.1], 1.0).excludes((0, 1, 2))
    assert not StraightReach([row], [sign * 3.0], None).excludes((0, 1))


@pytest.mark.parametrize("scale", (1e-200, 1e-9, 1.0, 1e8, 1e100))
def test_outward_bounds_preserve_actual_nonnegative_allocations_and_original_residual_slack(
    scale: float,
) -> None:
    """
    Exercise finite floating ranges and one-ulp perturbations without treating overlap as a certificate.
    """
    generator = random.Random(2155)
    for size in range(1, 8):
        for _ in range(12):
            rows = [[generator.uniform(-2, 2) for _ in range(size)] for _ in range(3)]
            values = [generator.random() * scale for _ in range(size)]
            budget = math.fsum(values)
            right = [math.fsum(a * b for a, b in zip(row, values)) for row in rows]
            right = [math.nextafter(value, math.inf) for value in right]
            assert not StraightReach(rows, right, budget).excludes(tuple(range(size)))


def test_empty_zero_budget_overflow_and_roundoff_are_conservative() -> None:
    """
    Preserve zero-support residual allowances and decline acceleration when finite bounds overflow.
    """
    assert not StraightReach([[1.0]], [1e-8], 0.0).excludes(())
    assert StraightReach([[1.0]], [1e-4], 0.0).excludes(())
    assert not StraightReach([[1e308]], [-1e308], 1e308).excludes((0,))
    for value in (1.0, 1e8, 1e100):
        assert not StraightReach([[1.0]], [math.nextafter(value, math.inf)], value).excludes((0,))


@pytest.mark.parametrize("budget", (-1, True, math.nan, math.inf))
def test_invalid_existing_budget_cannot_become_a_reachability_claim(budget: Any) -> None:
    """
    Reject malformed external-domain data rather than pruning with guessed limits.
    """
    with pytest.raises(ValueError, match="budget"):
        StraightReach([[1.0]], [1.0], budget)


@pytest.mark.parametrize("scale", (0.1, 1.0, 20.0))
@pytest.mark.parametrize("fraction", (0.4, 1.0, 2.0))
def test_actual_allocations_and_mask_order_match_with_impossible_fit_work_removed(
    scale: float,
    fraction: float,
) -> None:
    """
    Compare exact routes, values, scores and root choices with the same negative-only bound disabled.

    These are independently authored analytical frames, not complete-ribbon
    qualification, historical layout replays or an end-to-end solver benchmark.
    """
    frames = Frames.create(_targets(scale))
    boundary = Boundary(frames.targets, 0.101 * scale)
    options = chains(boundary, frames, (0.5,), lambda: None, lambda event: None)
    budget = frames.guide.distances[-1] * fraction
    saved_calls = 0
    for chain in options:
        baseline_calls = Mock(wraps=allocation.least_squares)
        before: list[dict[str, Any]] = []
        with patch.dict(vars(allocation), least_squares=baseline_calls, separate=lambda *_: None):
            with patch.object(StraightReach, "excludes", return_value=False):
                baseline = allocation.fit(
                    boundary,
                    chain,
                    1e-5 * scale,
                    lambda: None,
                    before.append,
                    maximum_straight_mm=budget,
                )
        calls = Mock(wraps=allocation.least_squares)
        after: list[dict[str, Any]] = []
        with patch.dict(vars(allocation), least_squares=calls):
            measured = allocation.fit(
                boundary,
                chain,
                1e-5 * scale,
                lambda: None,
                after.append,
                maximum_straight_mm=budget,
            )
        assert measured == baseline
        if any(e["status"] == "whole_travel_excluded" for e in after):
            assert baseline is None and calls.call_count == 0
            saved_calls += baseline_calls.call_count
            continue
        assert [e["mask"] for e in after if "mask" in e] == [
            e["mask"] for e in before if "mask" in e
        ]
        excluded = {e["mask"] for e in after if e["status"] == "straight_reach_excluded"}
        assert all(e["status"] != "closed" for e in before if e.get("mask") in excluded)
        assert baseline_calls.call_count - calls.call_count == len(excluded)
        saved_calls += len(excluded)
    assert saved_calls > 0


def test_original_checkpoint_runs_before_a_skipped_mask() -> None:
    """
    A fast rejection cannot bypass the caller's source, cancellation or resource guard.
    """
    frames = Frames.create(_targets())
    boundary = Boundary(frames.targets, 0.101)
    chain = chains(boundary, frames, (0.5,), lambda: None, lambda event: None)[0]
    with pytest.raises(TimeoutError, match="original clock"):
        allocation.fit(
            boundary,
            chain,
            1e-5,
            Mock(side_effect=TimeoutError("original clock")),
            Mock(),
            maximum_straight_mm=1,
        )


@pytest.mark.parametrize("scale", (0.1, 1.0, 20.0))
def test_unreachable_roots_do_not_prepare_unused_guide_geometry(scale: float) -> None:
    """
    An entirely excluded root records its unattempted masks and skips guide placements.
    """
    frames = Frames.create(_targets(scale))
    boundary = Boundary(frames.targets, 0.101 * scale)
    chain = chains(boundary, frames, (0.5,), lambda: None, lambda event: None)[0]
    placements = Mock(wraps=allocation.sites)
    events: list[dict[str, Any]] = []
    guard = Mock()
    with patch.dict(vars(allocation), sites=placements):
        result = allocation.fit(
            boundary, chain, 1e-5 * scale, guard, events.append, maximum_straight_mm=0.0
        )
    masks = 1 << (len(chain.topology.folds) + 1)
    assert result is None
    assert guard.call_count > 0
    if events[0]["status"] == "whole_travel_excluded":
        assert len(events) == 1 and events[0]["unattempted_masks"] == masks
    else:
        assert len(events) == masks and guard.call_count >= masks
        assert [event["mask"] for event in events] == list(range(masks))
        assert all(event["status"] == "straight_reach_excluded" for event in events)
    placements.assert_not_called()
