"""
Check coupled straight/fold descent, ordered closure and conservative acceptance.
"""

from __future__ import annotations

import math
from typing import Callable

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_relaxation.model import Model
from experiments.experiment_ribbon_fold_relaxation.relax import Trial, relax
from experiments.experiment_ribbon_fold_relaxation.steps import advance, projected, step_limit
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import Piece, fold


def _route() -> FoldRoute:
    """
    Author a planar shallow S with slack that admits angle/straight compensation.
    """
    start = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    pose = start
    pieces = []
    geometries: tuple[Piece, ...] = (
        Straight(10),
        fold(1, 1.2, math.pi / 4, 0, 0),
        Straight(12),
        fold(1, 1.2, -math.pi / 4, 0, 0),
        Straight(8),
    )
    for index, geometry in enumerate(geometries):
        piece = PlacedPiece(pose, geometry, str(index))
        pieces.append(piece)
        pose = piece.end_pose()
    target = Targets(
        "analytical shallow S",
        start.origin,
        pose.origin,
        start.tangent,
        pose.tangent,
        start.width,
        pose.width,
        1,
        1.0,
    )
    return FoldRoute(target, tuple(pieces), 1.0)


def test_initial_parameters_reproduce_material_route_and_straight_jacobian() -> None:
    """
    Preserve the starting material map and known endpoint derivatives.
    """
    source = _route()
    model = Model(source)
    restored = model.route(model.initial)
    assert restored is not None
    assert cap_error(restored) < 1e-12
    assert restored.material_length_mm == source.material_length_mm
    rows = model.jacobian(model.initial)
    for index in model.straight_indices:
        assert tuple(row[index] for row in rows[:3]) == pytest.approx(
            tuple(getattr(source.pieces[index].pose.tangent, a) for a in "xyz"), abs=1e-8
        )
        assert tuple(row[index] for row in rows[3:]) == pytest.approx((0, 0, 0), abs=1e-8)


def test_fold_relaxation_shortens_runs_and_whole_path_with_actual_contact_gate() -> None:
    """
    Demonstrate coupled movement while retaining endpoint frames and local metric.
    """
    source = _route()
    trials: list[Trial] = []
    result, reason = relax(source, record=trials.append)
    assert result.material_length_mm < source.material_length_mm - 0.01
    assert cap_error(result) < 1e-7
    assert material_error(result) < 1e-10
    initial_folds = [p.geometry for p in source.pieces if isinstance(p.geometry, CylindricalFold)]
    final_folds = [p.geometry for p in result.pieces if isinstance(p.geometry, CylindricalFold)]
    assert len(final_folds) == len(initial_folds)
    assert any(
        abs(a.angle_radians - b.angle_radians) > 1e-4 for a, b in zip(initial_folds, final_folds)
    )
    assert all(
        (a.radius_mm, a.bank_radians, a.before_mm, a.after_mm)
        == (b.radius_mm, b.bank_radians, b.before_mm, b.after_mm)
        for a, b in zip(initial_folds, final_folds)
    )
    accepted = [t for t in trials if t.status == "accepted"]
    assert accepted
    previous = source.material_length_mm
    for trial in accepted:
        assert trial.route is not None and trial.contact is not None
        assert trial.route.material_length_mm < previous
        assert trial.contact.status == "separated"
        previous = trial.route.material_length_mm
    assert reason in {
        "iteration_budget",
        "proposal_step_budget",
        "no_projected_straight_descent",
        "parameter_step_floor",
    }


@pytest.mark.parametrize("status", ["penetration", "unresolved"])
def test_contact_rejection_preserves_last_accepted_route(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """
    Treat unresolved and penetrating trial geometry as unaccepted contraction.
    """

    def inspect(route: FoldRoute, *, checkpoint: Callable[[], None] | None = None) -> ContactResult:
        """
        Supply an explicitly mocked nonpassing volume-contact decision.
        """
        del route, checkpoint
        return ContactResult(status, 1)

    monkeypatch.setattr(
        "experiments.experiment_ribbon_fold_relaxation.relax.inspect_contact", inspect
    )
    source = _route()
    trials: list[Trial] = []
    result, reason = relax(source, record=trials.append)
    assert result is source
    assert reason == "proposal_step_budget"
    assert any(t.status == status for t in trials)
    assert not any(t.status == "accepted" for t in trials)


def test_projection_and_step_respect_active_material_bounds() -> None:
    """
    Never turn a zero straight into backward material or exceed a half-turn.
    """
    model = Model(_route())
    values = list(model.initial)
    values[0] = 0
    values[1] = math.pi
    current = tuple(values)
    direction = projected(
        model, current, [[0.0] * len(values)] * 6, [0.0] * 6, [-1.0, 1.0, 0.0, 0.0, 0.0]
    )
    assert direction is not None
    assert direction[0] == 0 and direction[1] == 0
    step = step_limit(model, current, (0.0, -1.0, -2.0, 1.0, 0.0))
    moved = advance(model, current, (0.0, -1.0, -2.0, 1.0, 0.0), step)
    assert moved[0] >= 0
    assert all(model.bounds(i)[0] <= value <= model.bounds(i)[1] for i, value in enumerate(moved))


def test_half_turn_frame_cannot_masquerade_as_closed_rotation() -> None:
    """
    Keep the complete cap-vector gate beyond the local rotational residual.
    """
    model = Model(_route())
    values = list(model.initial)
    values[1] += math.pi / 2
    values[3] += math.pi / 2
    candidate = model.route(tuple(values))
    assert candidate is not None
    assert cap_error(candidate) > 1


@pytest.mark.parametrize("angle", (3e-6, -3e-6, 1e-6, -1e-6))
def test_aesthetic_jacobian_keeps_tiny_angle_probes_inside_bounds(angle: float) -> None:
    """
    Keep a one-sided difference from rounding past the signed nonzero-angle floor.
    """
    from experiments.experiment_ribbon_aesthetic.layout_model import Model as LayoutModel

    model = LayoutModel(_route())
    values = list(model.initial)
    index = 1 if angle > 0 else 5
    values[index] = angle
    rows = model.jacobian(tuple(values))
    assert len(rows) == 6 and all(len(row) == len(values) for row in rows)
    assert all(math.isfinite(value) for row in rows for value in row)
