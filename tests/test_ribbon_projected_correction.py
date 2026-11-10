"""
Use available positive straight motion to finish angular closure within its existing step budget.
"""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_feature_insertion import reclosure
from experiments.experiment_ribbon_feature_insertion.features import chains
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.repair import (
    StraightMotion,
    changed,
    correction,
    nearest,
    reframed,
)
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings

pytestmark = pytest.mark.skip(
    reason="Historical layout retired; fresh unique layouts and analytical projection controls replace replay"
)


def _problem(scale: float = 1.0) -> tuple[Boundary, Frames]:
    """
    Scale the complete gym regression while preserving endpoint-frame and conductor identities.
    """
    scene = Scene(Config(3889213147, 6, 0.75 * scale, 300, 300), Goal(8, 10, 1), Goal(12, 9, 1))
    frames = Frames.create(scene.targets)
    radius = scene.targets.diameter_mm / 2 / PinchLimit().fraction * (1 + 1e-9)
    return Boundary(frames.targets, radius), frames


@pytest.mark.parametrize("scale", (0.25, 1.0, 4.0))
def test_coupled_step_uses_less_rotation_and_recloses_after_actual_reallocation(
    scale: float,
) -> None:
    """
    Eliminate free straight motion instead of spending rotation on its endpoint directions.
    """
    boundary, frames = _problem(scale)
    chain = next(
        c
        for c in chains(boundary, frames, (0.5,), lambda: None, lambda e: None)
        if c.roots == (1, 1)
    )
    closure = nearest(Model(boundary, chain.topology), lambda: None)
    fixed = correction(boundary, chain, closure, lambda: None)
    assert fixed == correction(
        boundary, chain, closure, lambda: None, straight_motion=StraightMotion.FIXED
    )
    coupled = correction(
        boundary, chain, closure, lambda: None, straight_motion=StraightMotion.REALLOCATABLE
    )
    assert fixed is not None and coupled is not None
    assert math.fsum(v * v for v in coupled) < math.fsum(v * v for v in fixed)
    probe = reframed(boundary, chain, changed(chain.targets, coupled, 1.0))
    assert probe is not None and probe.roots == chain.roots
    after = nearest(Model(boundary, probe.topology), lambda: None)
    assert after.error < 1e-7 and after.error < closure.error * 1e-6
    assert all(f.radius_mm == boundary.radius_mm for f in probe.topology.folds)


def test_only_last_continuation_step_uses_coupled_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Finish the failed gym without extra iterations, weaker contact or a looser cap gate.
    """
    boundary, _ = _problem()
    observed = Mock(wraps=correction)
    monkeypatch.setitem(vars(reclosure), "correction", observed)
    rows: list[dict[str, Any]] = []
    result = solver_v2.solve(boundary.targets, Settings(0, False, False), lambda: None, rows.append)
    assert result.route is not None
    policies = [call.kwargs["straight_motion"] for call in observed.call_args_list]
    assert policies.count(StraightMotion.REALLOCATABLE) == 1
    assert policies[-1] is StraightMotion.REALLOCATABLE
    assert all(policy is StraightMotion.FIXED for policy in policies[:-1])
    coupled_rows = [
        row for row in rows if row.get("straight_motion") == StraightMotion.REALLOCATABLE.value
    ]
    assert len(coupled_rows) == 1 and coupled_rows[0]["iteration"] == 5
    assert coupled_rows[0]["status"] == "residual_reduced"
    assert result.detail["construction"]["contact_pairs"] == 945 < 2048
    assert result.detail["contact"] == "separated"
    assert cap_error(result.route) < 1e-7 and material_error(result.route) < 1e-10
