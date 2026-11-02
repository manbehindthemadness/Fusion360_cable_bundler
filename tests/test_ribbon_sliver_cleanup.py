"""
Verify bounded numerical sliver cleanup without native repair, target movement or tighter bends.
"""

from __future__ import annotations

from typing import Any

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import Settings, solve
from experiments.experiment_ribbon_locked_solver.cleanup import Cleanup, remove_slivers


def _route(travel: float, angle: float, turned: bool) -> FoldRoute:
    """
    Author a general spatially placed two-fold arch with one small terminal straight.
    """
    initial = Pose(
        Vector3(13, -7, 2),
        Vector3(0, 1, 0) if turned else Vector3(1, 0, 0),
        Vector3(0, 0, 1) if turned else Vector3(0, 1, 0),
    )
    pose = initial
    pieces = []
    for geometry in (
        Straight(2),
        fold(1.3, 2.4, angle, 0, 0),
        Straight(3),
        fold(1.3, 2.4, -angle, 0, 0),
        Straight(travel),
    ):
        piece = PlacedPiece(pose, geometry, "analytical cleanup")
        pieces.append(piece)
        pose = piece.end_pose()
    return FoldRoute(
        Targets(
            "analytical cleanup",
            initial.origin,
            pose.origin,
            initial.tangent,
            pose.tangent,
            initial.width,
            pose.width,
            3,
            0.75,
        ),
        tuple(pieces),
        0.3765060244728916,
    )


@pytest.mark.parametrize("travel", (1e-10, 8.6e-8, 1e-7))
@pytest.mark.parametrize("angle,turned", ((0.7, False), (-0.9, True)))
def test_cleanup_closes_same_caps_with_no_tighter_or_redirected_folds(
    travel: float, angle: float, turned: bool
) -> None:
    """
    Keep the material contract under sign and rigid-frame changes, with a fixed finite work bound.
    """
    source = _route(travel, angle, turned)
    checkpoints: list[None] = []
    result = remove_slivers(source, lambda: checkpoints.append(None))
    assert result.route is not None and result.status == "removed_and_reclosed"
    candidate = result.route
    assert result.removed_lengths_mm == (travel,)
    assert candidate.targets == source.targets and candidate.radius_mm == source.radius_mm
    assert cap_error(candidate) < 1e-7 and material_error(candidate) < 1e-10
    assert inspect_contact(candidate).status == "separated"
    assert (
        candidate.material_length_mm
        <= source.material_length_mm + 1e-8 * source.targets.diameter_mm
    )
    original_folds = [p.geometry for p in source.pieces if isinstance(p.geometry, CylindricalFold)]
    final_folds = [p.geometry for p in candidate.pieces if isinstance(p.geometry, CylindricalFold)]
    assert len(original_folds) == len(final_folds)
    for before, after in zip(original_folds, final_folds):
        assert (
            before.angle_radians,
            before.bank_radians,
            before.width_mm,
            before.before_mm,
            before.after_mm,
        ) == (
            after.angle_radians,
            after.bank_radians,
            after.width_mm,
            after.before_mm,
            after.after_mm,
        )
        assert after.radius_mm >= before.radius_mm
    assert all(
        not isinstance(p.geometry, Straight) or p.geometry.material_length_mm > 1e-7
        for p in candidate.pieces
    )
    assert result.projections == len(checkpoints) <= 2 * (2 * len(original_folds) + 2)


def test_ordinary_route_retains_identity_and_performs_no_projection() -> None:
    """
    Leave normal straight slots untouched rather than turning cleanup into another optimization pass.
    """
    source = _route(1.01e-7, 0.7, False)
    checkpoints: list[None] = []
    result = remove_slivers(source, lambda: checkpoints.append(None))
    assert result.route is source and result.status == "not_needed"
    assert result.projections == 0 and not checkpoints


def test_unresolved_cleanup_never_returns_the_original_sliver_as_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve a hard unresolved outcome and the removed-length diagnosis when closure fails.
    """

    def unresolved(*args: Any) -> tuple[None, int]:
        """
        Represent an exhausted deterministic projection without additional work.
        """
        del args
        return None, 3

    monkeypatch.setattr("experiments.experiment_ribbon_locked_solver.cleanup._project", unresolved)
    result = remove_slivers(_route(8.6e-8, 0.7, False), lambda: None)
    assert result.route is None and result.status == "closure_unresolved"
    assert result.removed_lengths_mm == (8.6e-8,) and result.projections == 3


def test_solver_records_unresolved_cleanup_and_skips_material_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep an unsuccessful plan in trial evidence without publishing it for native construction.
    """
    source = _route(8.6e-8, 0.7, False)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_locked_solver.solver.construct",
        lambda *args, **kwargs: (source, {}),
    )
    monkeypatch.setattr(
        "experiments.experiment_ribbon_locked_solver.solver.remove_slivers",
        lambda *args: Cleanup(None, "closure_unresolved", (8.6e-8,), 3),
    )
    events: list[dict[str, Any]] = []
    result = solve(source.targets, Settings(0, True), lambda: None, events.append)
    assert result.route is None and result.first_pass is source and result.material_uv is None
    assert result.detail["status"] == "unresolved"
    assert events[-1]["stage"] == "numerical_cleanup" and events[-1]["route"]["pieces"]
