"""
Check endpoint-nullspace shortening and fail-closed contact acceptance.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_contraction.contract import Trial, cap_error, contract
from experiments.experiment_ribbon_contraction.linear import shortening_direction
from experiments.experiment_ribbon_contraction.runner import restore, snapshot
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold


def _route() -> FoldRoute:
    """
    Author an analytical return-run fixture, without claiming native geometry coverage.
    """
    pose = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    geometries = (
        Straight(10),
        fold(1, 1.2, math.pi, 0, 0),
        Straight(8),
        fold(1, 1.2, math.pi, 0, 0),
        Straight(5),
    )
    pieces = []
    for index, geometry in enumerate(geometries):
        piece = PlacedPiece(pose, geometry, str(index))
        pieces.append(piece)
        pose = piece.end_pose()
    targets = Targets(
        "analytical return run",
        Vector3(0, 0, 0),
        pose.origin,
        Vector3(1, 0, 0),
        pose.tangent,
        Vector3(0, 1, 0),
        pose.width,
        1,
        1.0,
    )
    return FoldRoute(targets, tuple(pieces), 1)


@pytest.mark.parametrize(
    "directions,expected_sum",
    [
        ((), 0),
        ((Vector3(1, 0, 0),), 0),
        ((Vector3(1, 0, 0), Vector3(1, 0, 0)), 0),
        ((Vector3(1, 0, 0), Vector3(-1, 0, 0)), -2),
        ((Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)), 0),
        ((Vector3(0.6, 0.8, 0), Vector3(-0.6, -0.8, 0)), -2),
    ],
)
def test_descent_preserves_displacement(
    directions: tuple[Vector3, ...], expected_sum: float
) -> None:
    """
    Rank-deficient and rotated direction sets retain their endpoint displacement.
    """
    delta = shortening_direction(directions)
    assert math.fsum(delta) == pytest.approx(expected_sum, abs=1e-12)
    for coordinate in "xyz":
        assert math.fsum(
            getattr(axis, coordinate) * value for axis, value in zip(directions, delta)
        ) == pytest.approx(0, abs=1e-12)


def test_shortening_preserves_caps_and_fold_objects(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Exercise descent mechanics with an explicitly mocked external contact decision.
    """
    monkeypatch.setattr(
        "experiments.experiment_ribbon_contraction.contract.inspect_contact",
        lambda *args, **kwargs: ContactResult("separated", 0),
    )
    original = _route()
    trials: list[Trial] = []
    result, reason = contract(original, record=trials.append)
    assert result.material_length_mm < original.material_length_mm - 9
    assert cap_error(result) < 1e-12
    assert result.targets == original.targets
    assert all(
        before.geometry is after.geometry
        for before, after in zip(original.pieces, result.pieces)
        if not isinstance(before.geometry, Straight)
    )
    assert all(t.accepted and t.gain_mm > 0 for t in trials)
    assert reason == "no_linear_descent"
    assert contract(original) == (result, reason)


@pytest.mark.parametrize("status", ["penetration", "unresolved"])
def test_unaccepted_contact_never_changes_route(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """
    Refuse both contact rejection classes without treating exhaustion as improvement.
    """
    monkeypatch.setattr(
        "experiments.experiment_ribbon_contraction.contract.inspect_contact",
        lambda *args, **kwargs: ContactResult(status, 1),
    )
    original = _route()
    trials: list[Trial] = []
    result, reason = contract(original, record=trials.append)
    assert result is original
    assert reason == "contact_step_budget"
    assert len(trials) == 8
    assert not any(t.accepted for t in trials)


def test_resource_stop_propagates() -> None:
    """
    Never turn a resource interruption into a successful unchanged result.
    """

    def stop() -> None:
        """
        Model the runner's independent budget checkpoint.
        """
        raise TimeoutError("test budget")

    with pytest.raises(TimeoutError, match="test budget"):
        contract(_route(), checkpoint=stop)


def test_archived_radius_names_restore_the_same_geometry() -> None:
    """
    Preserve explicit radii in both previously written frozen-route schemas.
    """
    route = _route()
    payload = snapshot(route)
    assert restore(payload) == route
    payload["policy_radius_mm"] = payload.pop("radius_mm")
    assert restore(payload) == route
    payload.pop("policy_radius_mm")
    with pytest.raises(ValueError, match="declared construction radius"):
        restore(payload)


def test_spatial_descent_is_not_limited_to_opposite_pairs() -> None:
    """
    Shorten a genuinely spatial linear closure with no opposite direction pair.
    """
    root = math.sqrt(3)
    directions = (
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 0, 1),
        Vector3(-1 / root, -1 / root, -1 / root),
    )
    delta = shortening_direction(directions)
    assert sum(delta) < 0
    assert sum(delta) == pytest.approx(-sum(value**2 for value in delta))
    for coordinate in "xyz":
        assert sum(
            getattr(axis, coordinate) * value for axis, value in zip(directions, delta)
        ) == pytest.approx(0, abs=1e-12)


def test_contact_backtracking_preserves_only_verified_gains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Halve a rejected full step and retain only a subsequently separated route.
    """
    original = _route()

    def inspect(candidate: FoldRoute, *, checkpoint: object = None) -> ContactResult:
        """
        Model an explicit contact boundary after a four-millimeter length saving.
        """
        del checkpoint
        gain = original.material_length_mm - candidate.material_length_mm
        return ContactResult("separated" if gain < 4 else "penetration", 1)

    monkeypatch.setattr(
        "experiments.experiment_ribbon_contraction.contract.inspect_contact", inspect
    )
    trials: list[Trial] = []
    result, reason = contract(original, maximum_iterations=1, record=trials.append)
    assert not trials[0].accepted
    assert trials[-1].accepted
    assert 0 < original.material_length_mm - result.material_length_mm < 4
    assert cap_error(result) < 1e-12
    assert reason == "iteration_budget"
