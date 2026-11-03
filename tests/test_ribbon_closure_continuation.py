"""
Verify unfinished closure continues deterministically without altering successful constructions.
"""

from __future__ import annotations

from typing import Any

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_locked_solver.solver_v2 import solve


def test_closest_unfinished_branch_closes_before_smoothing_without_new_roots() -> None:
    """
    Reproduce numerical closure and1%smoothing; native fidelity is verified separately in Fusion.
    """
    scene = Scene(Config(1283296667, 3, 0.75, 300, 300), Goal(22, 5, 2), Goal(12, 3, 0))
    rows: list[dict[str, Any]] = []
    result = solve(scene.targets, Settings(1), lambda: None, rows.append)
    assert result.route is not None and result.first_pass is not None
    assert result.detail["status"] == "numerically_accepted"
    assert result.detail["contact"] == "separated" and not result.detail["contact_warning"]
    assert result.detail["cap_error_mm"] < 1e-7
    assert result.detail["material_metric_error"] < 1e-10
    continuation = [row for row in rows if row.get("stage") == "feature_closure_continuation"]
    assert len(continuation) == 1 and continuation[0]["roots"] == (0, 0)
    corrections = [
        row for row in rows if row.get("stage") == "feature_reclosure" and row["roots"] == (0, 0)
    ]
    assert [row["iteration"] for row in corrections] == [0, 1, 2, 3]
    assert corrections[-1]["position_error_diameters"] < 1e-7 / 0.75
    assert result.detail["construction"]["contacts"] <= 2


def test_original_successful_construction_never_launches_extra_corrections() -> None:
    """
    Preserve the compact route and first-pass work policy once any original branch closes.
    """
    scene = Scene(Config(4033669276, 3, 0.75, 300, 300), Goal(10, 6, 0), Goal(2, 6, 1))
    rows: list[dict[str, Any]] = []
    result = solve(scene.targets, Settings(0), lambda: None, rows.append)
    assert result.route is not None
    assert abs(result.route.material_length_mm - 20.057442613744374) < 1e-7
    assert not any(row.get("stage") == "feature_closure_continuation" for row in rows)
    assert all(row["iteration"] < 2 for row in rows if row.get("stage") == "feature_reclosure")
