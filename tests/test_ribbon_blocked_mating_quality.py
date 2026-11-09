"""
Restore a measured blocked fallback without confusing a quality goal with physical feasibility.
"""

from __future__ import annotations

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_locked_solver.solver_v2 import solve
from experiments.experiment_ribbon_terminal_hardware.check import inspect
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware


def test_blocked_mating_restoration_reports_released_length_without_renewing_work() -> None:
    """
    Keep fixed case88 poses, material radii and physical proofs while restoring its invalid fallback.
    """
    targets = Targets(
        diameter_mm=0.75,
        end=Vector3(-1.9560506685547054, 6.131159522869335, 7.450795297407157),
        end_tangent=Vector3(0.8506508083520399, 0.5257311121191338, 3.5384235359389174e-16),
        end_width=Vector3(0.3015469777681651, -0.48791325923370027, 0.8191520442889914),
        lines=4,
        name="Rubik gym preview",
        start=Vector3(-8.06681731255114, 1.7849031176477712, -9.661946507388635),
        start_tangent=Vector3(0.0, 0.8506508083520399, -0.5257311121191337),
        start_width=Vector3(0.8910065241883676, 0.2386769303195933, 0.38618738558759247),
    )
    result = solve(targets, Settings(1, False, True, True), lambda: None, lambda event: None)
    assert result.route is not None and result.route.targets == targets
    route = result.route
    recovery = result.detail["construction"]["recovery"]
    assert recovery["accepted_feasibility_restoration"] and not recovery["accepted_improvement"]
    assert recovery["length_ceiling_released"]
    assert recovery["length_goal_excess_mm"] > 0
    assert recovery["length_goal_mm"] == recovery["baseline_length_mm"]
    assert recovery["iterations"] <= 4 and recovery["newton_steps"] <= 24
    assert recovery["cpu_seconds"] < 0.35 and recovery["elapsed_seconds"] < 2
    assert result.detail["construction"]["contact_pairs"] <= 2048
    assert result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    assert cap_error(route) < 1e-7 and material_error(route) < 1e-10
    assert result.first_pass is not None
    assert all(
        piece.geometry.radius_mm == result.first_pass.radius_mm
        for piece in result.first_pass.pieces
        if isinstance(piece.geometry, CylindricalFold)
    )
    assert inspect(route, Hardware.create(targets, Dimensions.scaled(targets))).status == "clear"
