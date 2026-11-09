"""
Keep grouped hardware restoration on independently constrained occupied members.
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


def test_internal_runway_can_clear_different_box_faces_without_spending_more_work() -> None:
    """
    Restore frozen eligible case74 with separate member halfspaces and unchanged physical limits.
    """
    targets = Targets(
        diameter_mm=0.75,
        end=Vector3(-0.8046003991488245, 8.202831261981384, -14.357123247571337),
        end_tangent=Vector3(0.0, 0.8506508083520399, 0.5257311121191338),
        end_width=Vector3(-0.37460659341591235, -0.48744939900030193, 0.788709695378198),
        lines=6,
        name="Rubik gym preview",
        start=Vector3(-13.118845416585248, -11.150763948313415, -7.966341240020791),
        start_tangent=Vector3(-0.5257311121191337, 0.0, 0.85065080835204),
        start_width=Vector3(-0.2909397113926607, 0.9396926207859084, -0.17981063031774913),
    )
    result = solve(targets, Settings(1, False, True, True), lambda: None, lambda event: None)
    assert result.route is not None and result.route.targets == targets
    route = result.route
    recovery = result.detail["construction"]["recovery"]
    assert recovery["radius_restoration"] and recovery["selected_fold"] == 1
    assert recovery["before_radius"]["stop_reason"] == "linear_closure_infeasible"
    assert recovery["scalar_feature_constraints"] > recovery["feature_constraints"]
    assert recovery["iterations"] <= 4 and recovery["newton_steps"] <= 24
    assert recovery["cpu_seconds"] < 0.35 and recovery["elapsed_seconds"] < 2
    assert result.detail["construction"]["contact_pairs"] <= 2048
    assert result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    assert cap_error(route) < 1e-7 and material_error(route) < 1e-10
    folds = [
        piece.geometry for piece in route.pieces if isinstance(piece.geometry, CylindricalFold)
    ]
    assert folds[1].radius_mm >= route.radius_mm
    assert all(part.radius_mm == route.radius_mm for i, part in enumerate(folds) if i != 1)
    assert inspect(route, Hardware.create(targets, Dimensions.scaled(targets))).status == "clear"
