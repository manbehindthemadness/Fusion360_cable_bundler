"""
Check genuine curvature easing, affine cap closure and conservative contact handling.
"""

from __future__ import annotations

import math
from typing import Any, Callable

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_aesthetic.layout_model import Model as LayoutModel
from experiments.experiment_ribbon_aesthetic.layout_model import surface_score
from experiments.experiment_ribbon_aesthetic.layout_solve import ease as ease_layout
from experiments.experiment_ribbon_aesthetic.layout_solve import retract as retract_layout
from experiments.experiment_ribbon_aesthetic.merge import merge, proposals
from experiments.experiment_ribbon_aesthetic.model import Model, curvature_score, peak_curvature
from experiments.experiment_ribbon_aesthetic.solve import ease
from experiments.experiment_ribbon_bend_reduction.rewrite import fold_count
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


def test_layout_coordinates_preserve_diagonal_material_geometry_and_complete_caps() -> None:
    """
    Reconstruct the existing route while retaining bank-dependent flat end profiles.
    """
    source = _route(
        (Straight(8), fold(2, 1.2, 1.0, 0.3, 0.2), Straight(5), fold(3, 1.2, -0.8, -0.2, 0.1))
    )
    model = LayoutModel(source)
    restored = model.route(model.initial)
    assert restored is not None
    assert cap_error(restored) < 1e-11
    assert material_error(restored) < 1e-12
    assert restored.material_length_mm == pytest.approx(source.material_length_mm)
    assert model.score(model.initial) == pytest.approx(surface_score(source, model.scale))


def test_layout_retraction_stays_on_predicted_zero_runway_faces() -> None:
    """
    Correct a perturbed terminal pose without introducing microscopic straight slivers.
    """
    source = _route(
        (
            fold(2, 1.2, 0.8, 0.3, 0),
            fold(3, 1.2, -0.9, -0.2, 0),
            Straight(8),
            fold(2, 1.2, 0.6, 0.2, 0),
            fold(4, 1.2, -1.2, -0.3, 0),
        )
    )
    model = LayoutModel(source)
    values = list(model.initial)
    values[1] += 1e-4
    values[3] *= 1.0001
    corrected = retract_layout(model, tuple(values), 1.05, _checkpoint)
    assert corrected is not None
    assert max(abs(v) for v in model.residual(corrected)) < 1e-10
    assert all(corrected[i] == 0.0 for i in model.straight_indices if model.initial[i] == 0.0)


def test_layout_relaxation_scales_with_runway_at_fixed_conductor_diameter() -> None:
    """
    A ten-times-longer planar layout gets proportional easing without a thicker conductor.
    """
    results = []
    for scale in (1.0, 10.0):
        source = _route(
            (Straight(6 * scale), fold(2 * scale, 1.2, math.pi / 2, 0, 0), Straight(8 * scale))
        )
        result, _ = ease_layout(
            source, source.material_length_mm * 1.05, _checkpoint, lambda _: None
        )
        assert result is not source
        assert cap_error(result) < 1e-7
        assert material_error(result) < 1e-12
        assert surface_score(result, source.material_length_mm) < surface_score(
            source, source.material_length_mm
        )
        assert result.material_length_mm <= source.material_length_mm * 1.05 + 1e-8
        results.append(result)
    assert results[0].targets.diameter_mm == results[1].targets.diameter_mm == 1.0
    assert results[1].material_length_mm / 10 == pytest.approx(
        results[0].material_length_mm, rel=1e-6
    )
    first = [
        p.geometry.radius_mm for p in results[0].pieces if isinstance(p.geometry, CylindricalFold)
    ]
    second = [
        p.geometry.radius_mm / 10
        for p in results[1].pieces
        if isinstance(p.geometry, CylindricalFold)
    ]
    assert second == pytest.approx(first, rel=1e-6)


def test_different_radius_common_crease_turns_merge_with_actual_contact_acceptance() -> None:
    """
    Replace two compatible turns with one material-compatible broader turn and fixed caps.
    """
    source = _route(
        (
            Straight(10),
            fold(2, 1.2, math.pi / 4, 0, 0),
            Straight(2),
            fold(3, 1.2, math.pi / 4, 0, 0),
            Straight(12),
        )
    )
    assert proposals(source)
    result, _ = merge(source, source.material_length_mm * 1.05, _checkpoint, lambda _: None)
    assert fold_count(result) == 1
    assert cap_error(result) < 1e-10
    assert material_error(result) < 1e-12
    assert result.targets == source.targets


@pytest.mark.parametrize("bank,angle", [(0.2, math.pi / 4), (0.0, -math.pi / 4)])
def test_turn_merging_rejects_different_axes_and_reversed_turns(bank: float, angle: float) -> None:
    """
    Do not interpret unlike crease rotations or reversed turns as one same-direction arc.
    """
    source = _route((fold(2, 1.2, math.pi / 4, 0, 0), Straight(5), fold(3, 1.2, angle, bank, 0)))
    assert not proposals(source)


@pytest.mark.parametrize("status", ["penetration", "unresolved"])
def test_layout_relaxation_preserves_the_original_when_contact_is_unaccepted(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """
    A layout-scaled improvement cannot bypass full-volume contact acceptance.
    """

    def inspect(route: FoldRoute, *, checkpoint: Callable[[], None] | None = None) -> ContactResult:
        """
        Represent a bounded nonpassing external contact certificate.
        """
        del route, checkpoint
        return ContactResult(status, 1)

    monkeypatch.setattr(
        "experiments.experiment_ribbon_aesthetic.layout_solve.inspect_contact", inspect
    )
    source = _route((Straight(6), fold(2, 1.2, math.pi / 2, 0, 0), Straight(8)))
    events: list[dict[str, Any]] = []
    result, _ = ease_layout(source, source.material_length_mm * 1.05, _checkpoint, events.append)
    assert result is source
    assert any(row["status"] == status for row in events)
    assert not any(row["status"] == "accepted" for row in events)


@pytest.mark.parametrize("status", ["penetration", "unresolved"])
def test_turn_merging_requires_separated_full_profile_contact(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """
    Fewer folds and exact cap closure do not turn unresolved or penetrating contact into success.
    """

    def inspect(route: FoldRoute, *, checkpoint: Callable[[], None] | None = None) -> ContactResult:
        """
        Represent a bounded nonpassing external contact certificate.
        """
        del route, checkpoint
        return ContactResult(status, 1)

    monkeypatch.setattr("experiments.experiment_ribbon_aesthetic.merge.inspect_contact", inspect)
    source = _route(
        (
            Straight(10),
            fold(2, 1.2, math.pi / 4, 0, 0),
            Straight(2),
            fold(3, 1.2, math.pi / 4, 0, 0),
            Straight(12),
        )
    )
    events: list[dict[str, Any]] = []
    result, _ = merge(source, source.material_length_mm * 1.05, _checkpoint, events.append)
    assert result is source
    assert any(row["status"] == status for row in events)
