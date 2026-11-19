"""
Test soft-region guidance and bounded complete-route kinematic motion analytically.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

import pytest

from cable_bundler.routing.geometry import Vector3, magnitude
from experiments.experiment_ribbon_constrained_construction.waypoint_solve import Work, run
from experiments.experiment_ribbon_constrained_construction.waypoints import (
    Hinges,
    Objective,
    Waypoint,
    approaches,
)
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_spatial_inspection.landmarks import Landmark
from tests.test_ribbon_aesthetic import _route


def checkpoint() -> None:
    """
    Supply a deterministic analytical checkpoint without external geometry work.
    """


def objective() -> Objective:
    """
    Author one asymmetric four-hinge mechanism with exact measured terminal frames.
    """
    route = _route(
        (
            Straight(5),
            fold(1, 1.2, 0.8, 0.1, 0),
            Straight(5),
            fold(1, 1.2, -0.7, -0.2, 0),
            Straight(5),
            fold(1, 1.2, 0.6, 0.3, 0),
            Straight(5),
            fold(1, 1.2, -0.5, -0.1, 0),
            Straight(5),
        )
    )
    return Objective(Hinges(route), approaches(route, 2))


def test_angle_and_crease_are_free_without_radius_or_order_changes() -> None:
    """
    Kinematic coordinates allow sign changes and new crease directions without free swivels.
    """
    model = objective().model
    values = list(model.initial)
    low, high = model.bounds(1)
    assert low < 0 < high
    values[1] *= -1
    values[2] += 0.1
    route = model.route(tuple(values))
    assert route is not None
    folds = Hinges(route).folds
    assert folds[0].angle_radians == -model.folds[0].angle_radians
    assert folds[0].bank_radians == pytest.approx(model.folds[0].bank_radians + 0.1)
    assert [(g.radius_mm, g.width_mm) for g in folds] == [
        (g.radius_mm, g.width_mm) for g in model.folds
    ]
    assert route.targets == model.original.targets


def test_half_turn_terminal_mismatch_cannot_have_zero_rotation_error() -> None:
    """
    Full ordered-frame residuals expose the half-turn missed by a skew-only residual.
    """
    route = objective().model.original
    target = route.targets
    reversed_target = replace(
        target,
        end_tangent=target.end_tangent.translated(target.end_tangent, -2),
        end_width=target.end_width.translated(target.end_width, -2),
    )
    model = Hinges(replace(route, targets=reversed_target))
    assert math.hypot(*model.residual(model.initial)[3:]) == pytest.approx(math.pi)


def test_region_has_no_position_penalty_inside_and_keeps_ordered_identity() -> None:
    """
    A waypoint is a flexible region, never an exact pose or a nearest-point substitution.
    """
    landmark = Landmark("fold", 1, 1.0, 4)
    waypoint = Waypoint(landmark, Vector3(1, 2, 3), 2)
    assert magnitude(waypoint.excess(Vector3(1, 3, 3))) == 0
    assert waypoint.excess(Vector3(1, 6, 3)) == Vector3(0, 2, 0)
    shorter = _route((Straight(5), fold(1, 1.2, 0.5, 0.1, 0)))
    with pytest.raises(ValueError, match="landmark disappeared"):
        waypoint.point(shorter)


def test_observation_gradient_matches_squared_distance_to_region_derivative() -> None:
    """
    Landmark sensitivities combine with radial excesses to differentiate the actual objective.
    """
    problem = objective()
    values = problem.model.initial
    errors = problem.errors(values)
    for index in (0, 1, 2, 5, 7, 12):
        a, b = list(values), list(values)
        a[index] -= 1e-6
        b[index] += 1e-6
        first, last = problem.observations(tuple(a)), problem.observations(tuple(b))
        expected = math.fsum((y - x) * e / 2e-6 for x, y, e in zip(first, last, errors))
        actual = (problem.score(tuple(b)) - problem.score(tuple(a))) / 2e-6
        assert actual == pytest.approx(expected, abs=1e-7)


@pytest.mark.parametrize("permit", (True, False))
def test_only_closed_improving_certified_proposals_advance(permit: bool) -> None:
    """
    Actual kinematics restores both caps; an external clearance veto leaves the baseline intact.

    The stub tests certificate control flow only, not physical separation.
    """
    problem = objective()
    work = Work()
    checked: list[FoldRoute] = []
    events: list[dict[str, Any]] = []

    def certify(route: FoldRoute) -> bool:
        """
        Require actual closed frames before returning the test's explicit certificate disposition.
        """
        assert ordered_mating_caps(route.pieces, route.targets)
        checked.append(route)
        return permit

    run(problem, work, certify, checkpoint, events.append)
    assert checked
    assert work.actions <= 4 and work.newton <= 24 and work.proposals <= 8
    assert work.values is not None
    if permit:
        assert work.accepted > 0
        assert problem.score(work.values) < problem.score(problem.model.initial)
        assert any(a != b for a, b in zip(work.values, problem.model.initial))
    else:
        assert work.accepted == 0 and work.values == problem.model.initial
    assert all(
        event["score"] < problem.score(problem.model.initial)
        for event in events
        if "score" in event
    )
    with pytest.raises(RuntimeError, match="replayed"):
        run(problem, work, certify, checkpoint, events.append)
