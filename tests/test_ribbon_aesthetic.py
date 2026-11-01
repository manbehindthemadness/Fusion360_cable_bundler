"""
Check genuine curvature easing, affine cap closure and conservative contact handling.
"""

from __future__ import annotations

import math
from typing import Any, Callable

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_aesthetic.model import Model, curvature_score, peak_curvature
from experiments.experiment_ribbon_aesthetic.solve import ease
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import Piece, fold


def _route(geometries: tuple[Piece, ...]) -> FoldRoute:
    """
    Construct an analytical route with terminal poses measured from the actual pieces.
    """
    first = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    pose = first
    pieces = []
    for geometry in geometries:
        placed = PlacedPiece(pose, geometry, "analytical aesthetic fixture")
        pieces.append(placed)
        pose = placed.end_pose()
    targets = Targets(
        "aesthetic analytical",
        first.origin,
        pose.origin,
        first.tangent,
        pose.tangent,
        first.width,
        pose.width,
        1,
        1.0,
    )
    return FoldRoute(targets, tuple(pieces), 1.0)


def _checkpoint() -> None:
    """
    Run finite analytical tests without an external resource controller.
    """


def test_exact_score_matches_material_acceleration_integral() -> None:
    """
    Verify the curvature objective from independently evaluated material derivatives.
    """
    source = _route((fold(2, 1.2, 1.1, 0.3, 0),))
    geometry = source.pieces[0].geometry
    total = 0.0
    count = 20000
    for index in range(count):
        _, _, _, acceleration = geometry.surface((index + 0.5) / count, 0.0)
        squared = acceleration.x**2 + acceleration.y**2 + acceleration.z**2
        total += squared / geometry.material_length_mm**3 / count
    assert curvature_score(source) == pytest.approx(total, rel=2e-4)


def test_eases_quarter_turn_without_moving_caps_or_increasing_peak() -> None:
    """
    A longer straight margin can be absorbed into a genuinely broader existing fold.
    """
    source = _route((Straight(6), fold(1, 1.2, math.pi / 2, 0, 0), Straight(8)))
    events: list[dict[str, Any]] = []
    result, _ = ease(source, 0.05, _checkpoint, events.append)
    assert result is not source
    assert curvature_score(result) < curvature_score(source) * 0.5
    assert peak_curvature(result) < peak_curvature(source)
    assert result.material_length_mm <= source.material_length_mm * 1.05 + 1e-8
    assert cap_error(result) < 1e-10
    assert material_error(result) < 1e-12
    assert result.targets == source.targets
    assert any(row["status"] == "accepted" for row in events)


def test_model_reconstructs_staggered_folds_and_missing_straight_slots() -> None:
    """
    Keep the complete initial material geometry and affine orientation for diagonal folds.
    """
    source = _route((fold(2, 1.2, 1.0, 0.3, 0), Straight(3), fold(1, 1.2, -0.8, -0.2, 0)))
    model = Model.create(source, 0.05)
    result = model.route(model.initial)
    assert result.material_length_mm == pytest.approx(source.material_length_mm)
    assert cap_error(result) < 1e-12
    assert curvature_score(result) == pytest.approx(curvature_score(source))
    assert model.initial[0] == model.initial[-1] == 0


@pytest.mark.parametrize("allowance", [0.0, 0.05])
def test_length_allowance_enables_broadening_a_closed_three_quarter_turn(allowance: float) -> None:
    """
    Ease a fixed-endpoint return only when the explicitly declared material slack permits it.
    """
    source = _route(tuple(fold(2, 1.2, math.pi / 2, 0, 0) for _ in range(3)))
    result, _ = ease(source, allowance, _checkpoint, lambda _: None)
    assert cap_error(result) < 1e-10
    assert result.material_length_mm <= source.material_length_mm * (1 + allowance) + 1e-8
    if allowance:
        assert curvature_score(result) < curvature_score(source)
        assert result.material_length_mm > source.material_length_mm
    else:
        assert result is source


@pytest.mark.parametrize("status", ["penetration", "unresolved"])
def test_unaccepted_contact_never_becomes_an_aesthetic_success(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """
    Retain the original valid route and every rejected proposal within the fixed budget.
    """

    def inspect(route: FoldRoute, *, checkpoint: Callable[[], None] | None = None) -> ContactResult:
        """
        Supply an explicitly nonpassing contact result at the external acceptance boundary.
        """
        del route, checkpoint
        return ContactResult(status, 1)

    monkeypatch.setattr("experiments.experiment_ribbon_aesthetic.solve.inspect_contact", inspect)
    source = _route((Straight(6), fold(1, 1.2, math.pi / 2, 0, 0), Straight(8)))
    events: list[dict[str, Any]] = []
    result, _ = ease(source, 0.05, _checkpoint, events.append)
    assert result is source
    completed = [row for row in events if row["status"] != "contact_started"]
    assert 0 < len(completed) <= 8
    assert all(row["status"] == status for row in completed)


def test_straight_control_is_unchanged_and_resource_errors_propagate() -> None:
    """
    Do not bend an already straight route or silently swallow a resource interruption.
    """
    source = _route((Straight(10),))
    result, reason = ease(source, 0.05, _checkpoint, lambda _: None)
    assert result is source and reason == "no_projected_curvature_descent"

    def stop() -> None:
        """
        Represent the independent run controller's scheduling limit.
        """
        raise TimeoutError("aesthetic unit budget")

    with pytest.raises(TimeoutError, match="aesthetic unit budget"):
        ease(source, 0.05, stop, lambda _: None)
