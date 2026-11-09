"""
Recognize occupied mating leads without treating curved or internal material as terminal flats.
"""

from __future__ import annotations

from typing import Any

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact import Penetration
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware.flat_separation import mating_lead_crossing
from tests.test_ribbon_aesthetic import _route


def _mating_route() -> FoldRoute:
    """
    Keep three distinct folds and all four straight slots for region classification.
    """
    return _route(
        (
            Straight(2),
            fold(2, 1.2, 1, 0.2, 0.1),
            Straight(3),
            fold(2, 1.2, -1, -0.3, 0.1),
            Straight(4),
            fold(2, 1.2, 0.7, 0.3, 0.1),
            Straight(2),
        )
    )


def _region_witness(route: FoldRoute, index: int, phase: FlatPhase | None) -> Penetration:
    """
    Isolate region classification with synthetic coordinates, without claiming an actual crossing.
    """
    geometry = route.pieces[index].geometry
    u = 0.5
    if isinstance(geometry, CylindricalFold):
        low, high = geometry.bend_interval(0.0)
        if phase is FlatPhase.BEFORE:
            u = low / 2
        elif phase is FlatPhase.AFTER:
            u = (high + 1) / 2
    other = 2 if index == 3 else 3
    first, second = sorted((index, other))
    pieces = (first, second)
    coordinates = tuple((u, 0.0, 0.0) if i == index else (0.5, 0.0, 0.0) for i in pieces)
    return Penetration(pieces, coordinates[0], coordinates[1], Vector3(0, 0, 0))


@pytest.mark.parametrize(
    "index,phase,expected",
    (
        (0, FlatPhase.STRAIGHT, True),
        (6, FlatPhase.STRAIGHT, True),
        (2, FlatPhase.STRAIGHT, False),
        (4, FlatPhase.STRAIGHT, False),
        (1, FlatPhase.BEFORE, True),
        (1, FlatPhase.AFTER, False),
        (1, None, False),
        (5, FlatPhase.AFTER, True),
        (5, FlatPhase.BEFORE, False),
        (5, None, False),
        (3, FlatPhase.BEFORE, False),
        (3, FlatPhase.AFTER, False),
    ),
)
def test_only_terminal_straights_and_outward_fold_flats_are_mating_leads(
    index: int, phase: FlatPhase | None, expected: bool
) -> None:
    """
    Include both actual lead representations while excluding opposite phases, curves and internal slots.
    """
    route = _mating_route()
    assert mating_lead_crossing(route, _region_witness(route, index, phase)) is expected


@pytest.mark.parametrize("pieces", ((-1, 2), (2, 1), (0, 99)))
def test_mating_classification_rejects_invalid_material_identity(pieces: tuple[int, int]) -> None:
    """
    Never classify negative, reversed or missing material indices as terminal leads.
    """
    witness = Penetration(pieces, (0.5, 0.0, 0.0), (0.5, 0.0, 0.0), Vector3(0, 0, 0))
    with pytest.raises(ValueError, match="ordered existing"):
        mating_lead_crossing(_mating_route(), witness)


def _targets() -> Targets:
    """
    Replay exact Fusion-authored N8/995783115 poses, A4/2/284 and B23/3/333.
    """
    return Targets(
        name="Rubik gym preview",
        start=Vector3(-15.554612103960505, -7.049612481860061, -4.363139848398933),
        end=Vector3(12.267684854502274, 14.911297434056243, -10.633842427251137),
        start_tangent=Vector3(0.0, -0.8506508083520399, -0.5257311121191336),
        end_tangent=Vector3(0.5257311121191337, 3.5326131518707186e-16, -0.8506508083520398),
        start_width=Vector3(0.9271838545667874, 0.1969423409637076, -0.3186594015032497),
        end_width=Vector3(0.13307110414059167, 0.9876883405951377, 0.08224246527936244),
        lines=8,
        diameter_mm=0.75,
    )


def test_fold_mating_lead_uses_original_coupled_feasibility_work() -> None:
    """
    Retain real first-fold flat evidence before contact-only recovery consumes the shared allowance.
    """
    targets = _targets()
    events: list[dict[str, Any]] = []
    result = solver_v2.solve(targets, Settings(1, False, True, True), lambda: None, events.append)
    assert result.route is not None and result.route.targets == targets
    assert result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    recovery = result.detail["construction"]["recovery"]
    assert recovery["purpose"] == "restore_blocked_fallback"
    assert (
        recovery["accepted_feasibility_restoration"]
        and recovery["method"] == "fallback_mating_feasibility"
    )
    assert recovery["iterations"] <= 4 and recovery["newton_steps"] <= 24
    assert recovery["cpu_seconds"] < 0.35 and recovery["elapsed_seconds"] < 2
    assert result.detail["construction"]["contact_pairs"] <= 2048
    assert result.route.material_length_mm <= recovery["baseline_length_mm"]
    assert result.detail["cap_error_mm"] < 1e-7 and result.detail["material_metric_error"] < 1e-10
