"""
Keep released-quality radius restoration within the original caller allocation and physical gates.
"""

from __future__ import annotations

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_locked_solver.solver_v2 import solve
from experiments.experiment_ribbon_terminal_hardware.check import inspect
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware

pytestmark = pytest.mark.skip(
    reason="Archived gym layout retired under fresh-input validation policy"
)


def test_released_quality_stall_uses_only_remaining_incident_radius_work() -> None:
    """
    Preserve failed reflection and quality work while restoring frozen eligible case78.
    """
    targets = Targets(
        diameter_mm=0.75,
        end=Vector3(-4.101536482317046, 4.828072964634091, 6.003633687089858),
        end_tangent=Vector3(-0.85065080835204, 0.5257311121191336, 0.0),
        end_width=Vector3(0.27077153990616065, 0.4381175547543164, 0.8571673007021122),
        lines=3,
        name="Rubik gym preview",
        start=Vector3(-7.271391745884296, 6.067340479663777, -8.015536352605924),
        start_tangent=Vector3(-0.5257311121191338, 0.0, -0.8506508083520398),
        start_width=Vector3(0.48791325923369955, 0.8191520442889919, -0.30154697776816514),
    )
    result = solve(targets, Settings(1, False, True, True), lambda: None, lambda event: None)
    assert result.route is not None and result.route.targets == targets
    route = result.route
    recovery = result.detail["construction"]["recovery"]
    prior = recovery["before_radius"]
    assert prior["stop_reason"] == "joint_no_descent" and prior["length_ceiling_released"]
    assert prior["fixed_reversal_declined"]["stop_reason"] == "linear_trust_budget"
    assert recovery["iterations"] <= 4 and recovery["newton_steps"] <= 24
    assert recovery["iterations"] > prior["iterations"]
    assert recovery["cpu_seconds"] < 0.35 and recovery["elapsed_seconds"] < 2
    assert result.detail["construction"]["contact_pairs"] <= 2048
    assert result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    assert cap_error(route) < 1e-7 and material_error(route) < 1e-10
    folds = [
        piece.geometry for piece in route.pieces if isinstance(piece.geometry, CylindricalFold)
    ]
    selected = recovery["selected_fold"]
    assert folds[selected].radius_mm > route.radius_mm
    assert all(part.radius_mm == route.radius_mm for i, part in enumerate(folds) if i != selected)
    assert inspect(route, Hardware.create(targets, Dimensions.scaled(targets))).status == "clear"
